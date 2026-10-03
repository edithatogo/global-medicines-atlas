"""Contract tests for the M-112 deferred source candidate register."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = (
    ROOT
    / "quality/qualifications/"
    / ("australian-m112-deferred-source-candidates-20261004.json")
)


def _read(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_deferred_source_register_preserves_the_approved_denominator() -> None:
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    denominator = _read(
        "quality/qualifications/australian-m112-denominator-decision-20260930.json"
    )
    crosswalk = _read(
        "quality/qualifications/australian-m112-source-rights-lineage-crosswalk-20260930.json"
    )
    source = register["deferred_sources"][0]
    crosswalk_source = next(
        row
        for row in crosswalk["candidate_rights_and_lineage"]
        if row["dataset"] == source["dataset"]
    )

    assert register["scope"]["approved_candidate_denominator"] == 1_759
    assert register["scope"]["approved_raw_paths"] == 1_736
    assert register["scope"]["approved_projection_paths"] == 23
    assert register["scope"]["denominator_changed"] is False
    assert (
        register["scope"]["candidate_paths_remain_in_approved_denominator"]
        is True
    )
    assert denominator["denominator"]["total_candidate_paths"] == 1_759

    assert source["dataset"] == "edithatogo/reimbursement-atlas"
    assert source["current_revision"] == (
        "8e062578f14e12cf3238700a93946339da9c5d88"
    )
    assert source["candidate_paths"] == 1_719
    assert source["raw_candidate_paths"] == 1_707
    assert source["projection_candidate_paths"] == 12
    assert source["rights_status"] == source["lineage_status"] == "unresolved"
    assert source["reason"] == crosswalk_source["lineage_state"]
    assert (
        source["rights_evidence"]
        == crosswalk_source["source_specific_evidence"]
    )
    assert source["admission_status"] == "deferred_not_admitted"
    assert source["retained_in_approved_denominator"] is True
    assert register["boundaries"]["new_rights_or_licensing_conclusion"] is False
    assert register["boundaries"]["v4_admission_performed"] is False
    assert register["boundaries"]["m112_federation_accepted"] is False


def test_deferred_path_selection_is_bound_to_current_tree_metadata() -> None:
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    source = register["deferred_sources"][0]
    metadata_ref = source["candidate_path_inventory"]
    metadata_path = ROOT / metadata_ref["path"]
    assert (
        hashlib.sha256(metadata_path.read_bytes()).hexdigest()
        == metadata_ref["sha256"]
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    candidates = [
        row
        for row in metadata["observations"]
        if row["dataset"] == source["dataset"]
        and row["revision"] == source["current_revision"]
    ]
    raw = [
        row
        for row in candidates
        if row["candidate_class"] == "raw_source_payload"
    ]
    projections = [
        row
        for row in candidates
        if row["candidate_class"] == "existing_data_projection"
    ]

    assert len(candidates) == source["candidate_paths"] == 1_719
    assert len(raw) == source["raw_candidate_paths"] == 1_707
    assert len(projections) == source["projection_candidate_paths"] == 12
    assert sum(not row["has_lfs_sha256"] for row in raw) == 92
    assert sum(not row["has_lfs_sha256"] for row in projections) == 12
    assert sum(row["has_lfs_sha256"] for row in raw) == 1_615
    assert sum(row["has_lfs_sha256"] for row in projections) == 0
    assert source["paths_without_direct_sha256_metadata"] == 104
    assert register["boundaries"]["source_payload_bytes_read"] is False
    assert register["boundaries"]["source_payload_values_read"] is False

    for evidence in register["evidence_inputs"]:
        path = ROOT / evidence["path"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == evidence["sha256"]
        )
