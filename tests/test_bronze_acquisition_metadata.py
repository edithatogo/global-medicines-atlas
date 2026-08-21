"""B1 Acquisition Metadata is rebuilt from native append-only evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from jsonschema import Draft202012Validator
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_acquisition_metadata import (
    B1AcquisitionMetadataManifest,
    acquisition_metadata_parquet_bytes,
    reconstruct_b1_acquisition_metadata,
)
from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    land_bronze_payload,
)
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    HttpRetrievalEvidence,
    PayloadEvidence,
    RetrievalEvidence,
    SourceReceipt,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision
from global_medicines_atlas.rights_policy import (
    AccessRestriction,
    AcquisitionRightsPolicy,
    Permission,
    ReviewStatus,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/b1-acquisition-metadata-manifest-v1.json"
AUTHORITY_CONTEXT = (
    ROOT / "conductor/product.md",
    ROOT / "conductor/design.md",
    ROOT / "conductor/requirements.md",
    ROOT / "conductor/glossary.md",
    ROOT / "conductor/tracks/bronze_medallion_completion_20260819/spec.md",
    ROOT / "docs/data-sources/bronze-acquisition-metadata.md",
)
PAYLOAD = b"\x00\xffBINARY\x00PAYLOAD\n"
NOW = datetime(2026, 8, 22, 1, 0, tzinfo=UTC)


def _landable(
    *,
    retrieved_at: datetime = NOW,
    rights_policy: bool = False,
) -> SourceReceipt:
    receipt = source_receipt()
    payload = PayloadEvidence.from_bytes(PAYLOAD)
    original = (
        "https://reader:password@example.test/download?"
        "api_key=secret-value&year=2026"
    )
    final = "https://cdn.example.test/file.bin?token=secret-token&part=1"
    http = HttpRetrievalEvidence(
        original_uri=original,
        final_uri=final,
        redirect_history=(
            "https://example.test/redirect?signature=secret-signature&step=1",
        ),
        http_method="GET",
        http_status=200,
        etag='"immutable"',
        last_modified="Sat, 22 Aug 2026 00:00:00 GMT",
        content_type="application/octet-stream",
        content_encoding="identity",
        content_length=len(PAYLOAD),
        observed_byte_length=len(PAYLOAD),
        source_native_version="2026-08",
        acquisition_agent_version="gma-acquirer/1.4.0",
    )
    retrieval = RetrievalEvidence(
        uri=original,
        retrieved_at=retrieved_at,
        acquisition_method=AcquisitionMethod.DOWNLOAD,
        status=receipt.retrieval.status,
        http=http,
    )
    temporal = temporal_identity_from_source(
        retrieved_at=retrieved_at,
        source_id=receipt.source.source_id,
        payload_sha256=payload.sha256,
        source_version="2026-08",
        original_uri=original,
    )
    policy = None
    if rights_policy:
        policy = AcquisitionRightsPolicy(
            acquisition_id=temporal.acquisition_id,
            source_id=receipt.source.source_id,
            licence_evidence_uri="https://example.test/terms",
            licence_expression="Example public terms",
            retain_evidence=Permission.PERMITTED,
            publish_bytes=Permission.PROHIBITED,
            redistribute=Permission.PROHIBITED,
            transform=Permission.PERMITTED,
            access_restriction=AccessRestriction.NONE,
            review_status=ReviewStatus.REVIEWED,
            observed_at=NOW - timedelta(days=1),
            reviewed_at=NOW - timedelta(days=1),
        )
    return receipt.model_copy(
        update={
            "payload": payload,
            "retrieval": retrieval,
            "temporal": temporal,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "rights_policy": policy,
        }
    )


def _land(root: Path, receipt: SourceReceipt) -> BronzeLanding:
    outcome = land_bronze_payload(
        PAYLOAD,
        receipt,
        bronze_root=root,
        media_hint="bin",
        admission_decided_at=receipt.retrieval.retrieved_at,
        transformation_completed_at=receipt.retrieval.retrieved_at,
    )
    assert isinstance(outcome, BronzeLanding)
    return outcome


@pytest.mark.unit
def test_b1_reconstructs_one_row_per_append_only_acquisition_event(
    tmp_path: Path,
) -> None:
    bronze_root = tmp_path / "bronze"
    first = _land(bronze_root, _landable())
    second = _land(
        bronze_root,
        _landable(retrieved_at=NOW + timedelta(hours=1)),
    )

    manifest = reconstruct_b1_acquisition_metadata(bronze_root)

    assert manifest.authoritative_native_records is True
    assert manifest.query_manifest_is_authoritative is False
    assert manifest.openlineage_is_authoritative is False
    assert manifest.table_catalogues_are_authoritative is False
    assert len(manifest.rows) == 2
    assert len({row.acquisition_id for row in manifest.rows}) == 2
    assert {row.content_id for row in manifest.rows} == {
        first.receipt.payload.sha256
    }
    assert {row.payload_sha256 for row in manifest.rows} == {
        first.receipt.payload.sha256
    }
    assert first.payload_path == second.payload_path
    assert all(row.source_published_at is None for row in manifest.rows)
    assert all(row.source_effective_at is None for row in manifest.rows)
    assert all(row.valid_from is None for row in manifest.rows)
    assert all(row.valid_to is None for row in manifest.rows)
    assert all(row.raw_evidence_locator for row in manifest.rows)
    assert not {"payload", "payload_bytes", "payload_content"} & {
        field.casefold() for field in type(manifest.rows[0]).model_fields
    }


@pytest.mark.unit
def test_b1_relanding_same_acquisition_does_not_append_admission_events(
    tmp_path: Path,
) -> None:
    bronze_root = tmp_path / "bronze"
    receipt = _landable()
    first = _land(bronze_root, receipt)
    assert first.admission.path is not None
    admission_dir = first.admission.path.parent
    first_admissions = tuple(sorted(admission_dir.glob("*.json")))
    first_manifest = first.acquisition_manifest_path.read_bytes()

    second = _land(bronze_root, receipt)

    assert tuple(sorted(admission_dir.glob("*.json"))) == first_admissions
    assert second.admission.decision_id == first.admission.decision_id
    assert second.acquisition_manifest_path.read_bytes() == first_manifest


@pytest.mark.unit
def test_b1_redacts_sensitive_retrieval_locations_but_keeps_safe_query_keys(
    tmp_path: Path,
) -> None:
    bronze_root = tmp_path / "bronze"
    _land(bronze_root, _landable())

    row = reconstruct_b1_acquisition_metadata(bronze_root).rows[0]
    serialized = row.model_dump_json()

    assert "password" not in serialized
    assert "secret-value" not in serialized
    assert "secret-token" not in serialized
    assert "secret-signature" not in serialized
    assert "REDACTED" in serialized
    assert "year=2026" in row.original_retrieval_location
    assert "part=1" in row.final_retrieval_location
    assert row.http_method == "GET"
    assert row.http_status == 200
    assert row.etag == '"immutable"'
    assert row.declared_byte_length == len(PAYLOAD)
    assert row.observed_byte_length == len(PAYLOAD)


@pytest.mark.unit
def test_b1_links_rights_admission_raw_evidence_and_rebuildable_projections(
    tmp_path: Path,
) -> None:
    bronze_root = tmp_path / "bronze"
    landing = _land(bronze_root, _landable(rights_policy=True))

    row = reconstruct_b1_acquisition_metadata(bronze_root).rows[0]

    assert row.receipt_digest == landing.receipt.digest()
    assert row.evidence_class == landing.receipt.evidence_class.value
    assert row.retention_state == "permitted"
    assert row.transformation_state == "permitted"
    assert row.redistribution_state == "prohibited"
    assert row.rights_review_state == "reviewed"
    assert row.rights_compatibility == "policy_bound"
    assert row.admission_state == "accepted"
    assert row.admission_reviewer_state == "unreviewed"
    assert row.admission_decision_id == landing.admission.decision_id
    assert row.admission_reason_codes == landing.admission.reason_codes
    assert row.acquisition_event_locator.endswith(".json")
    assert row.source_receipt_locator.endswith(".json")
    assert row.admission_record_locators
    projection_kinds = {link.kind for link in row.projection_links}
    assert projection_kinds >= {
        "acquisition_manifest_parquet",
        "openlineage",
        "table_catalogue",
    }


@pytest.mark.unit
def test_b1_manifest_schema_and_parquet_are_deterministic_and_binary_safe(
    tmp_path: Path,
) -> None:
    bronze_root = tmp_path / "bronze"
    landing = _land(bronze_root, _landable())
    first = reconstruct_b1_acquisition_metadata(bronze_root)
    second = reconstruct_b1_acquisition_metadata(bronze_root)

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first.model_dump(mode="json"))
    assert first == second
    assert first.manifest_id == f"sha256:{first.manifest_sha256}"
    assert acquisition_metadata_parquet_bytes(first) == (
        acquisition_metadata_parquet_bytes(second)
    )
    table = pq.read_table(landing.acquisition_manifest_path)
    assert table.num_rows == 1
    assert "payload_bytes" not in table.column_names
    assert "payload_content" not in table.column_names
    assert table.column("payload_sha256")[0].as_py() == (
        landing.receipt.payload.sha256
    )
    assert table.column("payload_byte_count")[0].as_py() == len(PAYLOAD)


@pytest.mark.unit
def test_b1_reconstruction_fails_closed_on_rewritten_authoritative_event(
    tmp_path: Path,
) -> None:
    bronze_root = tmp_path / "bronze"
    landing = _land(bronze_root, _landable())
    landing.acquisition_receipt_path.write_text(
        '{"mutated":true}\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="authoritative acquisition event"):
        reconstruct_b1_acquisition_metadata(bronze_root)


@pytest.mark.unit
def test_b1_reconstructs_legacy_v2_event_without_rewriting_it(
    tmp_path: Path,
) -> None:
    bronze_root = tmp_path / "bronze"
    landing = _land(bronze_root, _landable())
    event = json.loads(landing.acquisition_receipt_path.read_bytes())
    event["schema_version"] = 2
    event.pop("sensitivity")
    legacy_bytes = (
        json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    landing.acquisition_receipt_path.write_bytes(legacy_bytes)

    manifest = reconstruct_b1_acquisition_metadata(bronze_root)

    assert manifest.event_count == 1
    assert manifest.rows[0].acquisition_id == event["acquisition_id"]
    assert landing.acquisition_receipt_path.read_bytes() == legacy_bytes


@pytest.mark.unit
def test_b1_model_has_no_field_for_source_payload_contents() -> None:
    row_schema = B1AcquisitionMetadataManifest.model_json_schema()["$defs"][
        "B1AcquisitionMetadataRow"
    ]
    fields = set(row_schema["properties"])
    assert "payload" not in fields
    assert "payload_bytes" not in fields
    assert "payload_content" not in fields
    assert {"payload_sha256", "payload_byte_count", "raw_evidence_locator"} <= (
        fields
    )


@pytest.mark.unit
def test_b1_authority_boundary_is_consistent_in_normative_context() -> None:
    for path in AUTHORITY_CONTEXT:
        context = path.read_text(encoding="utf-8").casefold().replace("-", " ")
        assert "authoritative" in context or "authority" in context, path
        assert "acquisition manifest" in context, path
        assert "openlineage" in context, path
        assert "table catalogue" in context, path
        assert "projection" in context, path
        assert "manifest is authoritative" not in context, path
