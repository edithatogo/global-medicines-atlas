"""Contract tests for binding the accepted MBS B1 lifecycle to M-112 identity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = (
    ROOT
    / "quality/qualifications/australian-m112-mbs-lifecycle-crosswalk-20261004.json"
)


def _read(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_mbs_lifecycle_joins_exact_m112_paths_without_promoting_federation() -> (
    None
):
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    deferred = _read(
        "quality/qualifications/australian-m112-additional-deferred-source-candidates-20261004.json"
    )
    inventory = _read(
        "quality/qualifications/australian-m112-current-tree-object-inventory-20261004.json"
    )
    source_qualification = _read(
        "quality/qualifications/australian-mbs-bronze-source-receipt-20261004.json"
    )
    group = next(
        row
        for row in deferred["additional_deferred_sources"]
        if row["group_id"] == "au-mbs-august-2026-raw-object-paths"
    )
    alias = group["path_alias_identity"]
    local = audit["canonical_bronze_lifecycle"]
    archive = audit["producer_archive_objects"]
    observed = [
        row
        for row in inventory["observations"]
        if row["dataset"] == group["dataset"] and row["path"] in alias["paths"]
    ]

    assert audit["scope"]["approved_m112_denominator_changed"] is False
    assert audit["scope"]["candidate_paths"] == 2
    assert set(audit["scope"]["paths"]) == set(alias["paths"])
    assert audit["scope"]["current_revision"] == group["current_revision"]
    assert len(observed) == 2
    assert {row["revision"] for row in observed} == {group["current_revision"]}
    assert {row["observed_git_blob_oid"] for row in observed} == {
        archive["path_alias_git_blob_oid"]
    }
    assert {row["observed_bytes"] for row in observed} == {
        archive["byte_count"]
    }
    assert (
        archive["path_alias_git_blob_oid"] == alias["same_current_git_blob_oid"]
    )
    assert archive["source_sha256"] == alias["same_source_sha256"]
    assert local["source_id"] == "au-mbs"
    assert local["source_version"] == "2026-08-01"
    assert local["effective_date"] == "2026-08-01"
    assert local["content_sha256"] == alias["same_source_sha256"]
    assert local["byte_count"] == alias["same_byte_count"]
    assert source_qualification["content_id"] == local["content_sha256"]
    assert source_qualification["admission_lifecycle"]["required_order"] == [
        "landed",
        "accepted",
    ]
    assert (
        source_qualification["admission_lifecycle"]["qualification_blocked"]
        is False
    )
    assert audit["reconciliation"]["source_identity_joined"] is True
    assert audit["reconciliation"]["local_b1_b2_lifecycle_complete"] is True
    assert (
        audit["reconciliation"]["producer_archive_projection_lineage_complete"]
        is False
    )
    assert audit["reconciliation"]["m112_v4_admission"] is False
    assert audit["reconciliation"]["m112_federation_accepted"] is False
    assert audit["boundaries"]["new_rights_or_licensing_conclusion"] is False
    assert audit["boundaries"]["source_archive_records_rewritten"] is False
    assert audit["boundaries"]["source_payload_bytes_read"] is False


def test_m112_mbs_lifecycle_audit_hash_binds_each_metadata_input() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    for reference in audit["evidence_inputs"]:
        path = ROOT / reference["path"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == reference["sha256"]
        )
