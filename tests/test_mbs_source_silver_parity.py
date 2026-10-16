from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from jsonschema import (
    Draft202012Validator,
)
from jsonschema import (
    ValidationError as JsonSchemaValidationError,
)
from pydantic import AnyUrl, ValidationError

from global_medicines_atlas import mbs_source_silver_parity as parity
from global_medicines_atlas.mbs_silver import mbs_silver_schema
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="synthetic:mbs-source-silver",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Synthetic",
            dataset_title="Synthetic MBS",
            catalog_version="2025-07-version-3",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://fixtures.invalid/mbs.xml"),
            retrieved_at=datetime(2026, 8, 30, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl("https://fixtures.invalid/rights"),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="fixture",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def _parquet(table: pa.Table) -> bytes:
    output = BytesIO()
    pq.write_table(table, output)  # pyright: ignore[reportUnknownMemberType]
    return output.getvalue()


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    source: bytes,
    silver: bytes,
    receipt: SourceReceipt,
) -> None:
    monkeypatch.setattr(parity, "SOURCE_OBJECT_BYTES", len(source))
    monkeypatch.setattr(
        parity,
        "SOURCE_OBJECT_SHA256",
        parity.hashlib.sha256(source).hexdigest(),
    )
    monkeypatch.setattr(parity, "SOURCE_RECEIPT_SHA256", receipt.digest())
    monkeypatch.setattr(parity, "SOURCE_URI", str(receipt.retrieval.uri))
    monkeypatch.setattr(parity, "SILVER_OBJECT_BYTES", len(silver))
    monkeypatch.setattr(
        parity,
        "SILVER_OBJECT_SHA256",
        parity.hashlib.sha256(silver).hexdigest(),
    )
    expected = pa.Table.from_batches(
        tuple(
            parity.iter_mbs_silver_batches(
                source, receipt, table="services", date_format="mbs-dmy"
            )
        )
    )
    monkeypatch.setattr(parity, "EXPECTED_ROWS", expected.num_rows)
    monkeypatch.setattr(parity, "EXPECTED_FIELDS", expected.num_columns)


def _six_table_fixture(
    source: bytes,
    receipt: SourceReceipt,
) -> dict[str, bytes]:
    return {
        table: _parquet(
            pa.Table.from_batches(
                tuple(
                    parity.iter_mbs_silver_batches(
                        source,
                        receipt,
                        table=table,
                        date_format="mbs-dmy",
                    )
                )
            )
        )
        for table in parity.MBS_SILVER_TABLES
    }


def _configure_six_table_fixture(
    monkeypatch: pytest.MonkeyPatch,
    source: bytes,
    silver: dict[str, bytes],
    receipt: SourceReceipt,
) -> None:
    monkeypatch.setattr(parity, "SOURCE_OBJECT_BYTES", len(source))
    monkeypatch.setattr(
        parity, "SOURCE_OBJECT_SHA256", hashlib.sha256(source).hexdigest()
    )
    monkeypatch.setattr(parity, "SOURCE_RECEIPT_SHA256", receipt.digest())
    monkeypatch.setattr(parity, "SOURCE_URI", str(receipt.retrieval.uri))
    monkeypatch.setattr(parity, "EXPECTED_ROWS", 1)
    objects = {
        table: parity.MbsSilverObject(
            path=f"silver/{table}.parquet",
            byte_count=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            source_field_count=len(mbs_silver_schema(table)) - 4,
        )
        for table in parity.MBS_SILVER_TABLES
        if (payload := silver.get(table)) is not None
    }
    monkeypatch.setattr(parity, "MBS_SILVER_OBJECTS", objects)


def test_verifies_all_source_to_silver_values_and_emits_value_free_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    generated = pa.Table.from_batches(
        tuple(
            parity.iter_mbs_silver_batches(
                source, receipt, table="services", date_format="mbs-dmy"
            )
        )
    )
    silver = _parquet(generated)
    _configure(monkeypatch, source, silver, receipt)

    result = parity.verify_mbs_source_silver_parity(source, receipt, silver)

    assert result.source_to_silver_value_parity_verified is True
    assert result.row_count == 1
    assert result.source_values_in_receipt is False
    assert "00123" not in result.model_dump_json()


def test_rejects_same_schema_same_row_count_value_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    generated = pa.Table.from_batches(
        tuple(
            parity.iter_mbs_silver_batches(
                source, receipt, table="services", date_format="mbs-dmy"
            )
        )
    )
    mutated = generated.set_column(
        0,
        pa.field("source_record_id", pa.string(), nullable=False),
        pa.array(["mutated"]),
    )
    silver = _parquet(mutated)
    _configure(monkeypatch, source, silver, receipt)

    with pytest.raises(ValueError, match="row values differ"):
        parity.verify_mbs_source_silver_parity(source, receipt, silver)


def test_rejects_wrong_b1_receipt_even_when_payload_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    generated = pa.Table.from_batches(
        tuple(
            parity.iter_mbs_silver_batches(
                source, receipt, table="services", date_format="mbs-dmy"
            )
        )
    )
    silver = _parquet(generated)
    _configure(monkeypatch, source, silver, receipt)
    wrong_receipt = receipt.model_copy(
        update={"rights_state": RightsState.UNKNOWN}
    )

    with pytest.raises(ValueError, match="B1 receipt"):
        parity.verify_mbs_source_silver_parity(source, wrong_receipt, silver)


def test_verifies_all_six_mbs_tables_with_one_value_free_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    silver = _six_table_fixture(source, receipt)
    _configure_six_table_fixture(monkeypatch, source, silver, receipt)

    result = parity.verify_mbs_source_silver_tables_parity(
        source, receipt, silver
    )

    assert result.source_to_silver_value_parity_verified is True
    assert tuple(table.table for table in result.tables) == (
        "services",
        "hierarchy",
        "descriptions",
        "fees",
        "benefits",
        "caps",
    )
    assert all(table.row_count == 1 for table in result.tables)
    assert result.source_values_in_receipt is False
    assert "00123" not in result.model_dump_json()
    assert result.silver_manifest_sha256 == parity.SILVER_MANIFEST_SHA256
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "schemas/mbs-source-silver-tables-parity-receipt-v1.json"
        ).read_text()
    )
    Draft202012Validator.check_schema(schema)  # pyright: ignore[reportUnknownMemberType]
    Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
        result.model_dump(mode="json")
    )
    incomplete = result.model_dump(mode="json")
    incomplete["tables"] = incomplete["tables"][:-1]
    with pytest.raises(ValidationError, match="all six tables"):
        parity.MbsSourceSilverTablesParityReceipt.model_validate(incomplete)
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
            incomplete
        )
    reordered = result.model_dump(mode="json")
    reordered["tables"][0], reordered["tables"][1] = (
        reordered["tables"][1],
        reordered["tables"][0],
    )
    with pytest.raises(ValidationError, match="all six tables"):
        parity.MbsSourceSilverTablesParityReceipt.model_validate(reordered)
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
            reordered
        )


def test_all_table_parity_rejects_nonmatching_b1_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    silver = _six_table_fixture(source, receipt)
    _configure_six_table_fixture(monkeypatch, source, silver, receipt)
    wrong_receipt = receipt.model_copy(
        update={"rights_state": RightsState.UNKNOWN}
    )

    with pytest.raises(ValueError, match="B1 receipt"):
        parity.verify_mbs_source_silver_tables_parity(
            source, wrong_receipt, silver
        )


def test_all_table_parity_rejects_changed_pinned_object_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    silver = _six_table_fixture(source, receipt)
    _configure_six_table_fixture(monkeypatch, source, silver, receipt)
    silver["fees"] += b" "

    with pytest.raises(ValueError, match="byte count"):
        parity.verify_mbs_source_silver_tables_parity(source, receipt, silver)


def test_all_table_parity_rejects_incomplete_pinned_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    silver = _six_table_fixture(source, receipt)
    _configure_six_table_fixture(monkeypatch, source, silver, receipt)
    monkeypatch.setattr(
        parity,
        "MBS_SILVER_OBJECTS",
        {
            table: item
            for table, item in parity.MBS_SILVER_OBJECTS.items()
            if table != "caps"
        },
    )

    with pytest.raises(ValueError, match="pinned MBS table identities"):
        parity.verify_mbs_source_silver_tables_parity(source, receipt, silver)


@pytest.mark.parametrize("table", parity.MBS_SILVER_TABLES)
def test_all_table_parity_rejects_same_shape_value_mutation(
    monkeypatch: pytest.MonkeyPatch,
    table: parity.MbsSilverTable,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    silver = _six_table_fixture(source, receipt)
    candidate: pa.Table = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        BytesIO(silver[table])
    )
    field = pa.field("source_record_id", pa.string(), nullable=False)
    mutated = candidate.set_column(0, field, pa.array(["mutated"]))
    silver[table] = _parquet(mutated)
    _configure_six_table_fixture(monkeypatch, source, silver, receipt)

    with pytest.raises(ValueError, match="row values differ"):
        parity.verify_mbs_source_silver_tables_parity(source, receipt, silver)


@pytest.mark.parametrize(
    ("missing", "extra"),
    [("caps", None), (None, "extra")],
)
def test_all_table_parity_requires_exact_table_set(
    monkeypatch: pytest.MonkeyPatch,
    missing: str | None,
    extra: str | None,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    silver = _six_table_fixture(source, receipt)
    _configure_six_table_fixture(monkeypatch, source, silver, receipt)
    if missing:
        silver.pop(missing)
    if extra:
        silver[extra] = silver["services"]

    with pytest.raises(ValueError, match="exact six-table set"):
        parity.verify_mbs_source_silver_tables_parity(source, receipt, silver)


def test_hosted_parity_receipt_is_durably_pinned_and_value_free() -> None:
    receipt_path = (
        Path(__file__).resolve().parents[1]
        / "quality/qualifications/mbs-source-silver-parity-2025-07-v3.json"
    )
    payload = receipt_path.read_bytes()
    receipt = parity.MbsSourceSilverParityReceipt.model_validate_json(payload)

    assert receipt.source_to_silver_value_parity_verified is True
    assert receipt.source_values_in_receipt is False
    assert receipt.row_count == 5_989
    assert receipt.field_count == 17
    assert receipt.source_object_sha256 == parity.SOURCE_OBJECT_SHA256
    assert receipt.silver_object_sha256 == parity.SILVER_OBJECT_SHA256
    assert "00123" not in receipt.model_dump_json()
    assert (
        hashlib.sha256(payload).hexdigest()
        == "009deabf772e91fedd7642f2b8f0e5a524abb76401620f8e93a8f3bd20189ded"
    )


def test_exact_main_six_table_receipt_is_durable_value_free_and_schema_valid() -> (
    None
):
    root = Path(__file__).resolve().parents[1]
    receipt_path = (
        root
        / "quality/qualifications/mbs-source-silver-tables-parity-2025-07-v3.json"
    )
    schema_path = (
        root / "schemas/mbs-source-silver-tables-parity-receipt-v1.json"
    )
    payload = receipt_path.read_bytes()
    receipt = parity.MbsSourceSilverTablesParityReceipt.model_validate_json(
        payload
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(json.loads(payload))

    assert hashlib.sha256(payload).hexdigest() == (
        "0743f6039e3da1d5bac05d013f3fd629d22da94df014033cdac66b0bb19ef5b6"
    )
    assert receipt.source_to_silver_value_parity_verified is True
    assert receipt.source_values_in_receipt is False
    assert [table.table for table in receipt.tables] == list(
        parity.MBS_SILVER_TABLES
    )
    assert [table.row_count for table in receipt.tables] == [5_989] * 6
    assert receipt.rights_conclusion is False
    assert receipt.production_admission is False
    assert receipt.public_data_mutation is False
    assert receipt.production_promotion is False


def test_six_table_identities_match_the_pinned_candidate_manifest() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = (
        root
        / "quality/qualifications/australian-mbs-v4-candidate-2025-07"
        / "manifest.json"
    )
    manifest_bytes = manifest_path.read_bytes()
    assert hashlib.sha256(manifest_bytes).hexdigest() == (
        parity.SILVER_MANIFEST_SHA256
    )
    manifest = json.loads(manifest_bytes)
    manifest_objects = {
        item["path"]: item
        for item in manifest["objects"]
        if item["role"] == "source_faithful_silver_table"
    }
    assert len(manifest_objects) == 6
    for table in parity.MBS_SILVER_TABLES:
        expected = parity.MBS_SILVER_OBJECTS[table]
        recorded = manifest_objects[expected.path]
        assert recorded["byte_count"] == expected.byte_count
        assert recorded["sha256"] == expected.sha256
        assert len(mbs_silver_schema(table)) - 4 == (
            expected.source_field_count
        )
