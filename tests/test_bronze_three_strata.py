"""End-to-end qualification tests for the three-strata Bronze substrate.

The immutable source payload and its content-addressed receipt remain
evidentiary truth; B0 Source Index, B1 Acquisition Metadata and B2 Raw
Evidence are rebuildable projections over that truth. These tests prove the
thirteen authority-boundary properties over the governed fixture corpus and
any already-approved live receipts present on ``main``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pytest
from jsonschema import Draft202012Validator
from pydantic import AnyUrl, ValidationError

from global_medicines_atlas.bronze_landing import (
    SourceRecordBatch,
    project_source_records_table,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceRecord,
    RawEvidenceState,
)
from global_medicines_atlas.bronze_three_strata import (
    PROPERTY_IDS,
    SCHEMA_RELATIVE,
    evaluate_repository,
)
from global_medicines_atlas.receipts import (
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    require_publication_permitted,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def report() -> dict[str, object]:
    return evaluate_repository(ROOT, git_commit="test-commit")


def test_schema_validates_report(report: dict[str, object]) -> None:
    schema = json.loads((ROOT / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)


def test_three_strata_qualified(report: dict[str, object]) -> None:
    assert report["three_strata_qualified"] is True
    assert report["qualification_state"] == "qualified"
    assert report["report_complete"] is True


def test_bronze_mature_remains_false_while_live_incomplete(
    report: dict[str, object],
) -> None:
    assert report["bronze_mature"] is False
    blockers = [item["blocker_id"] for item in report["blockers"]]
    assert "live-acquisition-completeness-blocked" in blockers


def test_all_thirteen_properties_evidenced(report: dict[str, object]) -> None:
    states = report["property_states"]
    assert [item["property_id"] for item in states] == list(PROPERTY_IDS)
    for item in states:
        assert item["state"] == "evidenced", item["property_id"]


def test_counts_by_evidence_class(report: dict[str, object]) -> None:
    b0 = report["b0"]
    assert b0["source_count"] >= 1
    assert b0["index_presence_implies_coverage"] is False
    assert b0["missing_source_is_negative_evidence"] is False
    b1 = report["b1"]
    assert b1["event_count"] >= 1
    assert b1["acquisitions_by_evidence_class"]
    assert report["b2"]["raw_evidence_count"] == b1["event_count"]


def test_migration_compatibility_and_deterministic_rebuild(
    report: dict[str, object],
) -> None:
    migration = report["migration_compatibility"]
    assert migration["stable"] is True
    assert migration["no_acquisition_id_changed"] is True
    assert migration["no_payload_digest_changed"] is True
    assert migration["no_receipt_digest_changed"] is True
    rebuild = report["deterministic_rebuild"]
    assert rebuild["rebuilt"] is True
    assert rebuild["match"] is True


def test_qualification_is_deterministic() -> None:
    first = evaluate_repository(ROOT, git_commit="deterministic")
    second = evaluate_repository(ROOT, git_commit="deterministic")
    assert first["b1"]["manifest_id"] == second["b1"]["manifest_id"]
    assert first["three_strata_qualified"] == second["three_strata_qualified"]


def test_b2_state_boundary_rejects_stored_bytes_when_external_only() -> None:
    with pytest.raises((ValueError, ValidationError)):
        RawEvidenceRecord(
            source_id="x",
            acquisition_id="0" * 64,
            content_id="0" * 64,
            state=RawEvidenceState.RETAINED,
            external_reference="https://example.org/external",
        )
    with pytest.raises((ValueError, ValidationError)):
        RawEvidenceRecord(
            source_id="x",
            acquisition_id="0" * 64,
            content_id="0" * 64,
            state=RawEvidenceState.EXTERNAL_REFERENCE_ONLY,
            raw_object_locator="file:///local/payload.bin",
            payload_sha256="0" * 64,
            byte_count=1,
        )


def test_source_native_records_preserve_binary_and_reject_silver() -> None:
    binary_values = [b"\x00\x01\x02\xff", b"plain text", b"\xfe\xff utf-16-ish"]
    table = pa.table({
        "native_id": pa.array(["a", "b", "c"]),
        "raw_bytes": pa.array(binary_values, type=pa.binary()),
        "label": pa.array(["x", "y", "z"]),
    })
    receipt = SourceReceipt(
        receipt_id="controlled:binary",
        source=SourceIdentity(
            catalog_id="us-fda-faers",
            source_id="us-fda-faers",
            jurisdiction="GLB",
            authority="controlled",
            dataset_title="controlled",
            catalog_version="v1",
        ),
        retrieval=RetrievalEvidence(
            uri="file:///controlled",
            retrieved_at=datetime(2026, 8, 20, tzinfo=UTC),
            acquisition_method="local_fixture",
            status="succeeded",
        ),
        payload=PayloadEvidence.from_bytes(b'{"placeholder": true}'),
        reuse=acquire_new_decision("us-fda-faers"),
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(
            "https://github.com/edithatogo/global-medicines-atlas/blob/main/DATA_LICENSE.md"
        ),
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation={
            "transformation_id": "controlled",
            "transformation_sha256": "0" * 64,
            "output_sha256": PayloadEvidence.from_bytes(
                b'{"placeholder": true}'
            ).sha256,
            "output_byte_count": 20,
        },
    )
    batch = SourceRecordBatch(
        table=table,
        parser_identity="controlled-parser-v1",
        record_id_column="native_id",
    )
    projected, _fingerprint = project_source_records_table(receipt, batch)
    assert projected.column("raw_bytes").to_pylist() == binary_values
    silver_table = pa.table({
        "native_id": pa.array(["a"]),
        "canonical_medicine": pa.array(["m"]),
    })
    with pytest.raises(ValueError, match="cannot contain Silver columns"):
        project_source_records_table(
            receipt,
            SourceRecordBatch(
                table=silver_table,
                parser_identity="controlled-parser-v1",
                record_id_column="native_id",
            ),
        )


def test_evidence_classes_remain_distinct_namespaces() -> None:
    assert EvidenceClass.FIXTURE != EvidenceClass.LIVE
    assert EvidenceClass.SYNTHETIC != EvidenceClass.LIVE
    assert EvidenceClass.FIXTURE != EvidenceClass.SYNTHETIC


def test_publication_permitted_fails_closed_under_restricted_rights() -> None:
    restricted = SourceReceipt(
        receipt_id="controlled:restricted",
        source=SourceIdentity(
            catalog_id="us-fda-faers",
            source_id="us-fda-faers",
            jurisdiction="GLB",
            authority="controlled",
            dataset_title="controlled",
            catalog_version="v1",
        ),
        retrieval=RetrievalEvidence(
            uri="file:///controlled",
            retrieved_at=datetime(2026, 8, 20, tzinfo=UTC),
            acquisition_method="local_fixture",
            status="succeeded",
        ),
        payload=PayloadEvidence.from_bytes(b'{"ok": true}'),
        reuse=acquire_new_decision("us-fda-faers"),
        rights_state=RightsState.RESTRICTED,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation={
            "transformation_id": "controlled",
            "transformation_sha256": "0" * 64,
            "output_sha256": PayloadEvidence.from_bytes(b'{"ok": true}').sha256,
            "output_byte_count": 11,
        },
    )
    with pytest.raises(ValueError, match="publication"):
        require_publication_permitted(restricted)
