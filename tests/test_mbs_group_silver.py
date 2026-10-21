"""Group-level utilisation stays distinct from demographic observations."""

from hashlib import sha256
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from jsonschema import Draft202012Validator
from test_mbs_demographic_silver import source

from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceManifest,
    build_raw_evidence_reference_from_acquisition,
)
from global_medicines_atlas.mbs_group_silver import (
    GROUP_HEADERS,
    MbsGroupSource,
    iter_group_silver_batches,
)


def context(payload):
    base = source("csv", payload)
    event = base.acquisition.model_copy(
        update={"source_id": "au-data-gov-mbs-group"}
    )
    raw = build_raw_evidence_reference_from_acquisition(
        event,
        external_reference=f"https://fixtures.invalid/datasets/synthetic/mbs-group/resolve/{'1' * 40}/synthetic/group.csv",
    )
    return MbsGroupSource(
        acquisition=event,
        raw_manifest=RawEvidenceManifest.from_rows((raw,)),
        dataset="synthetic/mbs-group",
        source_format="csv",
        source_revision="1" * 40,
        source_path="synthetic/group.csv",
    )


def csv_payload(benefit="12.345", services="2"):
    return (
        ",".join(GROUP_HEADERS)
        + f"\r\n2016,7,SYNTHETIC-GROUP,03,00123,SYNTHETIC-STATE,{services},{benefit}\r\n"
    ).encode()


def test_group_rows_preserve_native_dimensions_and_lossless_numbers():
    payload = csv_payload()
    src = context(payload)
    batches = list(iter_group_silver_batches(payload, src, rows_per_batch=1))
    table = pa.Table.from_batches(batches)
    rows = table.to_pylist()
    assert [row["record_kind"] for row in rows] == ["header", "data"]
    assert rows[1]["group_native"] == "SYNTHETIC-GROUP"
    assert rows[1]["subgroup_native"] == "03"
    assert rows[1]["item_number_native"] == "00123"
    assert rows[1]["services_count"] == 2
    assert str(rows[1]["benefit_decimal"]) == "12.345000000"
    assert rows[1]["patient_rate_state"] == "unavailable"
    assert rows[1]["benefit_interpretation_state"] == "native_unresolved"
    assert "age_native" not in table.schema.names
    assert rows[1]["source_object_id"] == src.object_id
    assert src.benefit_semantics.source_object_id == src.object_id
    assert src.source_sha256 == sha256(payload).hexdigest()
    output = BytesIO()
    pq.write_table(table, output)
    assert pq.read_table(BytesIO(output.getvalue())).equals(
        table, check_metadata=True
    )


def test_group_payload_identity_is_checked_before_rows():
    payload = csv_payload()
    with pytest.raises(ValueError, match="identity"):
        next(iter_group_silver_batches(payload + b"changed", context(payload)))


def test_late_bad_record_fails_before_any_output():
    payload = csv_payload() + b"not,eight,columns\n"
    with pytest.raises(ValueError, match="shape"):
        next(
            iter_group_silver_batches(
                payload, context(payload), rows_per_batch=1
            )
        )


@pytest.mark.parametrize(
    ("benefit", "services", "benefit_status", "services_status"),
    [
        ("", "", "blank", "blank"),
        ("NaN", "1.5", "invalid", "non_integral"),
        ("1.0000000001", str(2**63), "unrepresentable", "unrepresentable"),
        ("-2.00", "-3", "converted", "converted"),
    ],
)
def test_numeric_exceptions_keep_exact_source_text(
    benefit, services, benefit_status, services_status
):
    payload = csv_payload(benefit, services)
    row = pa.Table.from_batches(
        iter_group_silver_batches(payload, context(payload))
    ).to_pylist()[1]
    assert row["native_cells"][7]["value"] == benefit
    assert row["native_cells"][6]["value"] == services
    assert row["benefit_conversion_status"] == benefit_status
    assert row["services_conversion_status"] == services_status
    assert row["evidence_class"] == "synthetic"


@pytest.mark.parametrize("batch_size", [0, 4097, True, "1"])
def test_batch_size_is_strict_and_bounded(batch_size):
    payload = csv_payload()
    with pytest.raises(ValueError, match="batch bound"):
        next(
            iter_group_silver_batches(
                payload, context(payload), rows_per_batch=batch_size
            )
        )


@pytest.mark.parametrize("change", ["header", "encoding", "field_length"])
def test_malformed_source_fails_before_any_output(change):
    payload = csv_payload()
    if change == "header":
        payload = payload.replace(b"Sub-Group", b"Subgroup")
    elif change == "encoding":
        payload += b"\xff\n"
    else:
        payload = csv_payload("1" * 65537)
    with pytest.raises(ValueError, match=r"header|encoding|text bound"):
        next(
            iter_group_silver_batches(
                payload, context(payload), rows_per_batch=1
            )
        )


def test_group_context_and_schema_reject_workbook_relabelling():
    payload = csv_payload()
    src = context(payload)
    record = src.model_dump(mode="json")
    validator = Draft202012Validator(MbsGroupSource.model_json_schema())
    assert validator.is_valid(record)
    record["source_format"] = "workbook"
    assert not validator.is_valid(record)
    raw = build_raw_evidence_reference_from_acquisition(
        src.acquisition,
        external_reference=f"https://fixtures.invalid/datasets/synthetic/mbs-group/resolve/{'1' * 40}/synthetic/group.xlsx",
    )
    with pytest.raises(ValueError, match="requires the CSV"):
        MbsGroupSource.model_validate({
            **src.model_dump(),
            "source_format": "workbook",
            "source_path": "synthetic/group.xlsx",
            "raw_manifest": RawEvidenceManifest.from_rows((raw,)),
        })


def test_single_record_over_byte_budget_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "global_medicines_atlas.mbs_group_silver.MAX_BATCH_BYTES", 10
    )
    payload = csv_payload()
    with pytest.raises(ValueError, match="byte bound"):
        next(iter_group_silver_batches(payload, context(payload)))


def test_logically_empty_csv_requires_native_header():
    payload = b"\xef\xbb\xbf"
    with pytest.raises(ValueError, match="header is unavailable"):
        next(iter_group_silver_batches(payload, context(payload)))
