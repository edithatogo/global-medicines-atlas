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


def test_per_path_observations_bind_the_candidate_inventory() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    inventory = _read(
        "quality/qualifications/australian-m112-object-inventory-20260930.json"
    )
    per_path = _read(
        "quality/qualifications/australian-m112-current-tree-object-inventory-20261004.json"
    )
    tree_readback = _read(
        "quality/qualifications/australian-m112-public-tree-readback-20261003.json"
    )
    current = report["current_tree_metadata_readback"]
    current_revisions = {
        row["dataset"]: row["revision"] for row in tree_readback["datasets"]
    }

    expected_by_path = {
        row["path"]: (row, "raw_source_payload")
        for row in inventory["raw_source_payload_candidates"]
    }
    expected_by_path.update({
        row["path"]: (row, "existing_data_projection")
        for row in inventory["existing_data_projection_candidates"]
    })
    observed_by_path = {row["path"]: row for row in per_path["observations"]}
    assert set(observed_by_path) == set(expected_by_path)
    assert per_path["candidate_paths"] == len(expected_by_path) == 1_759
    assert per_path["payload_endpoints_used"] is False
    assert per_path["payload_values_read"] is False
    for path, observed in observed_by_path.items():
        candidate, candidate_class = expected_by_path[path]
        assert observed["dataset"] == candidate["dataset"]
        assert observed["candidate_inventory_revision"] == candidate["revision"]
        assert observed["revision"] == current_revisions[candidate["dataset"]]
        assert observed["candidate_class"] == candidate_class
        assert (
            observed["expected_git_blob_oid"] == candidate["hub_git_blob_oid"]
        )
        assert observed["expected_bytes"] == candidate["bytes"]
        assert observed["expected_lfs_sha256"] == candidate["lfs_sha256"]
        assert observed["git_blob_oid_match"] is True
        assert observed["byte_count_match"] is True
        if candidate["lfs_sha256"] is not None:
            assert observed["lfs_sha256_match"] is True

    assert (
        sum(row["git_blob_oid_match"] for row in observed_by_path.values())
        == (current["git_blob_oid_matches"])
    )
    assert (
        sum(row["byte_count_match"] for row in observed_by_path.values())
        == (current["byte_count_matches"])
    )
    assert (
        sum(row["lfs_sha256_match"] for row in observed_by_path.values())
        == (current["current_lfs_sha256_matches"])
    )
    assert (
        sum(
            row["lfs_sha256_match"]
            for row in observed_by_path.values()
            if row["candidate_class"] == "raw_source_payload"
        )
        == current["raw_lfs_sha256_matches"]
    )
    assert (
        sum(
            row["lfs_sha256_match"]
            for row in observed_by_path.values()
            if row["candidate_class"] == "existing_data_projection"
        )
        == current["projection_lfs_sha256_matches"]
    )

    inventory_path = (
        ROOT
        / "quality/qualifications/australian-m112-current-tree-object-inventory-20261004.json"
    )
    digest = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    assert current["per_path_metadata_inventory"]["sha256"] == digest
    assert current["per_path_metadata_inventory"]["observation_count"] == 1_759
    correction = report["current_tree_metadata_revision_correction"]
    assert correction["previous_supplemental_inventory_sha256"] == (
        "bfaf0291fc37d6761b3ba0e26f32d8f2cfeba46db7b48d48ed68c52df9f24bd1"
    )
    assert correction["current_tree_revisions"] == current_revisions
    pages = per_path["page_response_hashes"]
    assert len(pages) == current["metadata_pages"] == 39
    assert (
        sum(page["response_bytes"] for page in pages)
        == current["metadata_response_bytes"]
    )
    assert all(len(page["response_sha256"]) == 64 for page in pages)
    for dataset in current["datasets"]:
        dataset_pages = [
            page for page in pages if page["dataset"] == dataset["dataset"]
        ]
        assert len(dataset_pages) == dataset["metadata_pages"]
        assert (
            sum(page["response_bytes"] for page in dataset_pages)
            == dataset["metadata_response_bytes"]
        )


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
