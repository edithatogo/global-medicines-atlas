"""Receipt-bound, loss-aware MBS Arrow projections with synthetic payloads."""

from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from io import BytesIO
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import AnyUrl

from global_medicines_atlas.australian_source_contracts import (
    TargetTable,
    mbs_field_contracts,
)
from global_medicines_atlas.mbs_silver import (
    iter_mbs_silver_batches,
    mbs_silver_schema,
)
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    HttpRetrievalEvidence,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)

TABLES: tuple[TargetTable, ...] = (
    "services",
    "hierarchy",
    "descriptions",
    "fees",
    "benefits",
    "caps",
)


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="synthetic:mbs-silver",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Synthetic",
            dataset_title="Synthetic MBS",
            catalog_version="synthetic-iso-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://fixtures.invalid/mbs"),
            retrieved_at=datetime(2026, 8, 30, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="synthetic",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def _xml(fields: str = "", count: int = 1) -> bytes:
    row = f"<Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum>{fields}</Data>"
    return f"<MBS_XML>{row * count}</MBS_XML>".encode()


def test_all_forty_fields_have_typed_source_addressed_schemas() -> None:
    names: list[str] = []
    for table in TABLES:
        schema = mbs_silver_schema(table)
        assert schema.metadata is not None
        assert schema.metadata[b"dimension"] == b"service_benefit"
        assert schema.metadata[b"absence_interpretation"] == b"unknown"
        for contract in mbs_field_contracts():
            if contract.target_table != table:
                continue
            field = cast(
                "pa.Field[pa.DataType]",
                schema.field(contract.native_name),  # pyright: ignore[reportUnknownMemberType]
            )
            assert field.metadata is not None
            assert (
                field.metadata[b"source_path"]
                == f"/MBS_XML/Data/{contract.native_name}".encode()
            )
            names.append(contract.native_name)
    assert sorted(names) == sorted(
        field.native_name for field in mbs_field_contracts()
    )
    assert len(names) == len(set(names)) == 40


def test_all_six_tables_preserve_the_complete_native_denominator() -> None:
    values = {
        field.native_name: "2026-08-30"
        if field.value_type == "source_date"
        else "42.125"
        if field.value_type in {"aud_decimal", "decimal", "percentage"}
        else "00123"
        for field in mbs_field_contracts()
    }
    payload = (
        "<MBS_XML><Data>"
        + "".join(f"<{name}>{value}</{name}>" for name, value in values.items())
        + "</Data></MBS_XML>"
    ).encode()
    for table in TABLES:
        with localcontext() as context:
            context.prec = 2
            batch = next(
                iter_mbs_silver_batches(
                    payload, _receipt(payload), table=table, date_format="iso"
                )
            )
        row = batch.to_pylist()[0]
        for field in mbs_field_contracts():
            if field.target_table == table:
                assert (
                    row[field.native_name]["native_value"]
                    == values[field.native_name]
                )
                assert row[field.native_name]["typed_value"] is not None
                assert row[field.native_name]["conversion_status"] in {
                    "preserved",
                    "converted",
                }


def test_unknown_table_and_date_profile_fail_closed() -> None:
    with pytest.raises(ValueError, match="table"):
        mbs_silver_schema(cast("TargetTable", "medicines"))
    payload = _xml()
    with pytest.raises(ValueError, match="date format"):
        next(
            iter_mbs_silver_batches(
                payload, _receipt(payload), table="fees", date_format="guess"
            )
        )


@pytest.mark.parametrize(
    ("native", "status"),
    [("  ", "blank"), ("NaN", "invalid"), ("0.123456789000", "converted")],
)
def test_numeric_quality_states_survive_arrow(native: str, status: str) -> None:
    payload = _xml(f"<ScheduleFee>{native}</ScheduleFee>")
    value = next(
        iter_mbs_silver_batches(payload, _receipt(payload), table="fees")
    ).to_pylist()[0]["ScheduleFee"]
    assert value["native_value"] == native
    assert value["conversion_status"] == status


def test_native_schema_drift_fails_before_any_table_is_yielded() -> None:
    payload = _xml("<UnknownField>1</UnknownField>")
    with pytest.raises(ValueError, match="unknown native field"):
        next(iter_mbs_silver_batches(payload, _receipt(payload), table="fees"))


def test_receipt_and_raw_identity_follow_every_batch() -> None:
    payload = _xml(count=3)
    receipt = _receipt(payload)
    batches = list(
        iter_mbs_silver_batches(
            payload, receipt, table="services", rows_per_batch=2
        )
    )
    assert [batch.num_rows for batch in batches] == [2, 1]
    table = pa.Table.from_batches(batches)
    rows = table.to_pylist()
    assert [row["source_ordinal"] for row in rows] == [0, 1, 2]
    assert len({row["source_record_id"] for row in rows}) == 3
    assert all(row["ItemNum"]["typed_value"] == "00123" for row in rows)
    assert all(row["source_sha256"] == receipt.payload.sha256 for row in rows)
    assert all(row["receipt_sha256"] == receipt.digest() for row in rows)
    assert table.schema.metadata is not None
    assert (
        table.schema.metadata[b"source_receipt_sha256"]
        == receipt.digest().encode()
    )
    assert (
        table.schema.metadata[b"source_receipt_locator"]
        == f"sha256:{receipt.digest()}".encode()
    )
    assert b"source_receipt" not in table.schema.metadata
    assert table.schema.metadata[b"schema_era"] == b"synthetic-iso-v1"


def test_null_missing_invalid_and_decimal_precision_are_not_collapsed() -> None:
    payload = _xml(
        "<ScheduleFee>42.500</ScheduleFee><FeeType/><DerivedFee>85% of item 00123</DerivedFee>"
    )
    rows = next(
        iter_mbs_silver_batches(payload, _receipt(payload), table="fees")
    ).to_pylist()
    assert rows[0]["ScheduleFee"]["typed_value"] == Decimal("42.500")
    assert rows[0]["ScheduleFee"]["native_value"] == "42.500"
    assert rows[0]["FeeType"]["native_state"] == "null"
    assert rows[0]["FeeChange"]["native_state"] == "missing_field"
    assert rows[0]["DerivedFee"]["typed_value"] == "85% of item 00123"


@pytest.mark.parametrize(
    "value", ["0.1234567891", "123456789012345678901234567890"]
)
def test_unrepresentable_decimal_retains_source_without_rounding(
    value: str,
) -> None:
    payload = _xml(f"<ScheduleFee>{value}</ScheduleFee>")
    result = next(
        iter_mbs_silver_batches(payload, _receipt(payload), table="fees")
    ).to_pylist()[0]["ScheduleFee"]
    assert result == {
        "native_value": value,
        "native_state": "value",
        "conversion_status": "unrepresentable",
        "typed_value": None,
    }


def test_dates_require_explicit_profile_and_keep_invalid_source() -> None:
    payload = _xml(
        "<ItemStartDate>2026-08-30</ItemStartDate><ItemEndDate>2026-02-30</ItemEndDate>"
    )
    receipt = _receipt(payload)
    without = next(
        iter_mbs_silver_batches(payload, receipt, table="services")
    ).to_pylist()[0]
    assert without["ItemStartDate"]["conversion_status"] == "unsupported_format"
    with_profile = next(
        iter_mbs_silver_batches(
            payload, receipt, table="services", date_format="iso"
        )
    ).to_pylist()[0]
    assert with_profile["ItemStartDate"]["typed_value"] == date(2026, 8, 30)
    assert with_profile["ItemEndDate"]["conversion_status"] == "invalid"


def test_parquet_round_trip_and_chunking_do_not_change_values() -> None:
    payload = _xml("<ScheduleFee>42.5</ScheduleFee>", 5)
    receipt = _receipt(payload)
    one = pa.Table.from_batches(
        list(
            iter_mbs_silver_batches(
                payload, receipt, table="fees", rows_per_batch=1
            )
        )
    )
    many = pa.Table.from_batches(
        list(
            iter_mbs_silver_batches(
                payload, receipt, table="fees", rows_per_batch=5
            )
        )
    )
    assert one.equals(many, check_metadata=True)
    first = BytesIO()
    second = BytesIO()
    for output in (first, second):
        pq.write_table(many, output, compression="zstd", use_dictionary=False)  # pyright: ignore[reportUnknownMemberType]
    assert first.getvalue() == second.getvalue()
    restored = pq.read_table(BytesIO(first.getvalue()))  # pyright: ignore[reportUnknownMemberType]
    assert restored.equals(many, check_metadata=True)


def test_reject_mismatched_source_bytes_before_output() -> None:
    with pytest.raises(ValueError, match="source bytes"):
        next(
            iter_mbs_silver_batches(
                _xml(), _receipt(_xml(count=2)), table="fees"
            )
        )


def test_receipt_credentials_never_enter_arrow_or_parquet_metadata() -> None:
    payload = _xml()
    receipt = _receipt(payload)
    uri = "https://synthetic-user:synthetic-password@fixtures.invalid/mbs?token=synthetic-token&year=2026#synthetic-fragment"
    receipt = receipt.model_copy(
        update={
            "retrieval": receipt.retrieval.model_copy(
                update={
                    "uri": AnyUrl(uri),
                    "http": HttpRetrievalEvidence(
                        original_uri=AnyUrl(uri),
                        final_uri=AnyUrl(
                            "https://fixtures.invalid/final?signature=synthetic-signature"
                        ),
                        redirect_history=(
                            AnyUrl(
                                "https://fixtures.invalid/hop?api_key=synthetic-key"
                            ),
                        ),
                    ),
                }
            ),
            "rights_reference": AnyUrl(
                "https://fixtures.invalid/rights?token=synthetic-rights"
            ),
        }
    )
    batch = next(iter_mbs_silver_batches(payload, receipt, table="services"))
    assert batch.schema.metadata is not None
    metadata = b"\n".join(batch.schema.metadata.values())
    for value in (
        b"synthetic-user",
        b"synthetic-password",
        b"synthetic-token",
        b"synthetic-fragment",
        b"synthetic-signature",
        b"synthetic-key",
        b"synthetic-rights",
    ):
        assert value not in metadata
    assert b"source_receipt" not in batch.schema.metadata
    assert (
        batch.schema.metadata[b"source_uri"]
        == b"https://fixtures.invalid/mbs?token=REDACTED&year=2026"
    )
    assert batch.to_pylist()[0]["receipt_sha256"] == receipt.digest()
    output = BytesIO()
    pq.write_table(pa.Table.from_batches([batch]), output)  # pyright: ignore[reportUnknownMemberType]
    assert b"synthetic-password" not in output.getvalue()


@pytest.mark.parametrize("size", [0, -1, 4097, True])
def test_reject_invalid_batch_bounds(size: int) -> None:
    payload = _xml()
    with pytest.raises(ValueError, match="batch"):
        next(
            iter_mbs_silver_batches(
                payload, _receipt(payload), table="fees", rows_per_batch=size
            )
        )


@given(st.integers(min_value=-1000000000, max_value=1000000000))
def test_decimal_arrow_property(value: int) -> None:
    payload = _xml(f"<Benefit75>{value}.012300</Benefit75>")
    result = next(
        iter_mbs_silver_batches(payload, _receipt(payload), table="benefits")
    ).to_pylist()[0]["Benefit75"]
    assert result["typed_value"] == Decimal(f"{value}.012300")
    assert result["native_value"] == f"{value}.012300"
