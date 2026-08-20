"""Bronze emits a manifest and optional adapter-native record product."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    SourceRecordBatch,
    land_bronze_payload,
    regenerate_parquet,
)
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    require_temporal,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

PDF = b"%PDF-1.7\n%\xff\xfe binary document\n%%EOF\n"
JSON = b'{"records":[{"native_id":"A-1","quantity":7,"listed":true}]}'


def _receipt(payload: bytes):
    receipt = source_receipt()
    evidence = PayloadEvidence.from_bytes(payload)
    return receipt.model_copy(
        update={
            "payload": evidence,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=receipt.retrieval.retrieved_at,
                source_id=receipt.source.source_id,
                payload_sha256=evidence.sha256,
                original_uri=str(receipt.retrieval.uri),
            ),
        }
    )


@pytest.mark.unit
def test_binary_payload_emits_manifest_without_replacement_decoding(
    tmp_path: Path,
) -> None:
    receipt = _receipt(PDF)
    outcome = land_bronze_payload(
        PDF,
        receipt,
        bronze_root=tmp_path / "bronze",
        media_hint="pdf",
    )

    assert isinstance(outcome, BronzeLanding)
    assert (
        outcome.acquisition_manifest_path.name == "acquisition_manifest.parquet"
    )
    assert outcome.source_records_path is None
    manifest = pq.read_table(outcome.acquisition_manifest_path)
    assert manifest.num_rows == 1
    assert "native_record" not in manifest.column_names
    assert manifest.column("source_id")[0].as_py() == receipt.source.source_id
    assert manifest.column("media_type")[0].as_py() == "application/pdf"
    assert manifest.column("payload_location")[0].as_py() == (
        outcome.payload_path.as_uri()
    )
    assert (
        manifest.column("payload_sha256")[0].as_py() == receipt.payload.sha256
    )
    assert manifest.column("parser_available")[0].as_py() is False
    assert outcome.payload_path.read_bytes() == PDF


@pytest.mark.unit
def test_adapter_records_preserve_native_schema_and_have_independent_evidence(
    tmp_path: Path,
) -> None:
    native = pa.table({
        "native_id": pa.array(["A-1", "A-2"], type=pa.string()),
        "quantity": pa.array([7, 11], type=pa.int64()),
        "listed": pa.array([True, False], type=pa.bool_()),
    })
    batch = SourceRecordBatch(
        table=native,
        parser_identity="tests.native-json.v1",
        record_id_column="native_id",
    )
    outcome = land_bronze_payload(
        JSON,
        _receipt(JSON),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        source_records=batch,
    )

    assert isinstance(outcome, BronzeLanding)
    assert outcome.source_records_path is not None
    assert outcome.source_records_path.name == "source_records.parquet"
    records = pq.read_table(outcome.source_records_path)
    assert records.num_rows == 2
    assert records.schema.field("quantity").type == pa.int64()
    assert records.schema.field("listed").type == pa.bool_()
    assert records.column("native_id").to_pylist() == ["A-1", "A-2"]
    assert records.column("gma_source_record_id").to_pylist() == ["A-1", "A-2"]
    temporal = require_temporal(outcome.receipt.temporal)
    assert records.column("gma_acquisition_id").to_pylist() == [
        temporal.acquisition_id,
        temporal.acquisition_id,
    ]
    fingerprints = records.column("gma_schema_fingerprint").to_pylist()
    assert len(set(fingerprints)) == 1
    assert len(fingerprints[0]) == 64
    assert "canonical_medicine" not in records.column_names
    assert "normalized_product" not in records.column_names

    assert outcome.source_records_transformation_run is not None
    assert outcome.source_records_transformation_receipt_path is not None
    assert outcome.source_records_transformation_receipt_path.is_file()
    assert (
        outcome.source_records_transformation_run.output.sha256
        == sha256(outcome.source_records_path.read_bytes()).hexdigest()
    )
    assert (
        outcome.source_records_transformation_run.output.sha256
        != outcome.acquisition_manifest_transformation_run.output.sha256
    )
    assert outcome.source_records_table is not None
    assert outcome.source_records_table.identifier.endswith("_source_records")
    assert outcome.acquisition_manifest_table.identifier.endswith(
        "_acquisition_manifest"
    )

    assert outcome.source_records_lineage_path is not None
    lineage = json.loads(outcome.source_records_lineage_path.read_bytes())
    projected = {item["namespace"] for item in lineage["outputs"]}
    assert "gma.source_records" in projected


@pytest.mark.unit
def test_source_record_projection_requires_native_record_identifier(
    tmp_path: Path,
) -> None:
    batch = SourceRecordBatch(
        table=pa.table({"name": ["example"]}),
        parser_identity="tests.missing-id.v1",
        record_id_column="native_id",
    )

    with pytest.raises(ValueError, match="record identifier column"):
        land_bronze_payload(
            JSON,
            _receipt(JSON),
            bronze_root=tmp_path / "bronze",
            media_hint="json",
            source_records=batch,
        )


@pytest.mark.unit
def test_two_product_layout_rebuilds_deterministically(tmp_path: Path) -> None:
    batch = SourceRecordBatch(
        table=pa.table({
            "native_id": pa.array(["A-1"], type=pa.string()),
            "quantity": pa.array([7], type=pa.int64()),
        }),
        parser_identity="tests.native-json.v1",
        record_id_column="native_id",
    )
    outcome = land_bronze_payload(
        JSON,
        _receipt(JSON),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        source_records=batch,
    )
    assert isinstance(outcome, BronzeLanding)
    assert outcome.source_records_path is not None
    expected_manifest = sha256(
        outcome.acquisition_manifest_path.read_bytes()
    ).hexdigest()
    expected_records = sha256(
        outcome.source_records_path.read_bytes()
    ).hexdigest()
    outcome.acquisition_manifest_path.unlink()
    outcome.source_records_path.unlink()

    regenerate_parquet(outcome, source_records=batch)

    assert sha256(
        outcome.acquisition_manifest_path.read_bytes()
    ).hexdigest() == (expected_manifest)
    assert sha256(outcome.source_records_path.read_bytes()).hexdigest() == (
        expected_records
    )
