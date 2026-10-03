"""Contract tests for exact-revision M-112 tree identity evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT
    / "quality/qualifications/"
    / (
        "australian-m112-current-tree-object-identity-reconciliation-20261004.json"
    )
)


def _read(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_current_tree_identity_reconciliation_covers_exact_denominator() -> (
    None
):
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    inventory = _read(
        "quality/qualifications/australian-m112-object-inventory-20260930.json"
    )
    tree_readback = _read(
        "quality/qualifications/australian-m112-public-tree-readback-20261003.json"
    )

    current = report["current_tree_metadata_readback"]
    assert report["scope"]["approved_raw_paths"] == 1_736
    assert report["scope"]["approved_projection_paths"] == 23
    assert report["scope"]["approved_total_paths"] == 1_759
    assert current["candidate_paths_present"] == 1_759
    assert current["candidate_paths_missing"] == 0
    assert current["git_blob_oid_matches"] == 1_759
    assert current["git_blob_oid_mismatches"] == 0
    assert current["byte_count_matches"] == 1_759
    assert current["byte_count_mismatches"] == 0
    assert current["current_lfs_sha256_matches"] == 1_645
    assert current["current_lfs_sha256_mismatches"] == 0
    assert current["raw_lfs_sha256_matches"] == 1_634
    assert current["projection_lfs_sha256_matches"] == 11

    by_dataset = {row["dataset"]: row for row in current["datasets"]}
    assert set(by_dataset) == {
        row["dataset"] for row in tree_readback["datasets"]
    }
    for row in tree_readback["datasets"]:
        observed = by_dataset[row["dataset"]]
        assert observed["revision"] == row["revision"]
        assert observed["candidate_paths"] == (
            row["candidate_raw_path_count"]
            + row["candidate_projection_path_count"]
        )

    expected_candidates = len(inventory["raw_source_payload_candidates"]) + len(
        inventory["existing_data_projection_candidates"]
    )
    assert expected_candidates == current["candidate_paths_present"]


def test_additional_mbs_hashes_match_existing_authorized_sidecars() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    source_join = _read(
        "quality/qualifications/australian-m112-source-archive-receipt-join-audit-20260930.json"
    )
    authorization = _read(
        "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
    )

    readback = report["additional_anonymous_raw_byte_hashes"]
    assert readback["objects_hashed"] == 4
    assert readback["payload_bytes_streamed"] == 9_055_125
    assert readback["persisted_payload_bytes"] == 0
    assert readback["dataset"] == authorization["dataset"]
    assert readback["revision"] == "40891976f77ee5e7688edceed25c9ac98a77547e"

    sidecars = {
        item["path"]: match
        for item in source_join["mbs"]["objects"]
        for match in item["receipt_or_authorization_matches"]
        if match.get("kind") == "sidecar"
    }
    categories = set(authorization["categories"])
    for item in readback["objects"]:
        sidecar = sidecars[item["path"]]
        assert item["http_status"] == 200
        assert item["anonymous"] is True
        assert item["streamed_without_persistence"] is True
        assert item["source_values_inspected"] is False
        assert item["source_id"] in authorization["allowed_sources"]
        assert item["category"] in categories
        assert item["sidecar_sha256"] == sidecar["receipt_sha256"]
        assert (
            item["expected_bytes"] == item["observed_bytes"] == sidecar["bytes"]
        )
        assert (
            item["expected_sha256"]
            == item["observed_sha256"]
            == sidecar["sha256"]
        )


def test_digest_gaps_and_rights_gates_remain_explicit() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    coverage = report["digest_coverage"]
    boundaries = report["boundaries"]

    assert coverage["paths_with_direct_sha256_evidence"] == 1_654
    assert coverage["same_git_blob_identity_alias_paths"] == 1
    assert coverage["paths_without_direct_sha256"] == 105
    assert (
        coverage["paths_without_direct_or_same_git_object_sha256_binding"]
        == 104
    )
    assert coverage["remaining_non_lfs_raw_paths_without_digest_evidence"] == 92
    assert coverage["remaining_projection_paths_without_digest_evidence"] == 12
    assert boundaries["new_rights_or_licensing_conclusion"] is False
    assert boundaries["v4_admission_performed"] is False
    assert boundaries["consumer_canaries_performed"] is False
    assert boundaries["m112_federation_accepted"] is False


def test_report_hash_binds_each_evidence_input() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    for item in report["evidence_inputs"]:
        path = ROOT / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
