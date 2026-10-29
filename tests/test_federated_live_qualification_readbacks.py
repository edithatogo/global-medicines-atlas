"""Checks for the 2026-10-23 live federation qualification receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONSUMER_REPORT = ROOT / (
    "quality/qualifications/"
    "australian-mbs-gold-candidate-consumers-20261023-39939296038.json"
)
RECOVERY_REPORT = ROOT / (
    "quality/qualifications/"
    "australian-m112-primary-recovery-readback-20261023.json"
)
ROLE_REPORT = ROOT / (
    "quality/qualifications/"
    "australian-m112-v4-contract-role-evidence-qualification-20261021.json"
)
PREFLIGHT_REPORT = ROOT / (
    "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261023-36.json"
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_consumer_receipt_binds_exact_reviewed_edges_and_surfaces() -> (
    None
):
    report = _read(CONSUMER_REPORT)
    assert report["candidate_only"] is True
    assert report["edge_count"] == 5_989
    assert report["graph_sha256"] == (
        "44c6c4f2d3dee80e49efac7bc14cc8965958b476a0e73c3758214645c7f7b27b"
    )
    assert report["hosted_workflow"]["run_id"] == 39_939_296_038
    assert report["hosted_workflow"]["commit"] == (
        "78e857839aad8298060c65eb5ef03a4e3114827a"
    )
    review = report["reviewed_candidate_relationship"]
    assert review["state"] == "reviewed_candidate_only"
    assert review["m110_overall_accepted"] is False
    assert review["m112_federation_accepted"] is False
    canary = report["reviewed_candidate_consumer_canary"]
    assert canary["status"] == "passed"
    assert canary["surface_canary_count"] == 4
    assert set(canary["surfaces"]) == {"API", "Atlas", "Browser", "CLI"}
    assert set(report["surface_edge_id_sha256"].values()) == {
        review["edge_id_sha256"]
    }
    assert report["public_publication_performed"] is False
    assert report["source_payload_bytes_retained"] is False


def test_primary_recovery_readback_joins_all_admissions_without_independence_claim() -> (
    None
):
    report = _read(RECOVERY_REPORT)
    assert report["status"] == (
        "primary_clean_room_restore_reconciled_independent_recovery_open"
    )
    assert report["frozen_inventory"] == {
        "object_count": 1_759,
        "admitted_object_count": 8,
        "consumer_canary_count": 8,
        "deferred_object_count": 1_751,
        "denominator_changed": False,
    }
    assert report["inputs"]["public_manifest"]["sha256"] == (
        "9e9848f32287cdb8141d65f2f2741916cf7e391e396ac2fcaf5794eccdaa3bab"
    )
    assert report["inputs"]["restore"]["issue_comment_body_sha256"] == (
        "5069e57b54a2c3d2aff9901389738998a8944de006505a8f3ac0e02bb4e87a15"
    )
    assert report["inputs"]["restore"]["verified_file_count"] == 28
    assert (
        report["inputs"]["public_manifest"]["anonymous_metadata_readback"]
        is True
    )
    assert report["inputs"]["public_manifest"]["http_status"] == 200
    assert len(report["objects"]) == 8
    assert all(
        row["restore_status"] == "passed"
        and row["recovery_role"] == "primary"
        and row["independent"] is False
        and row["rpo_seconds"] is None
        and row["rto_seconds"] is None
        for row in report["objects"]
    )
    assert report["recovery_limits"]["independent_replica_qualified"] is False
    assert report["recovery_limits"]["production_dr_claimed"] is False
    assert report["boundaries"]["external_publication"] is False
    assert report["boundaries"]["new_admission"] is False
    assert report["boundaries"]["new_consumer_canary"] is False

    role_report = _read(ROLE_REPORT)
    preflight = _read(PREFLIGHT_REPORT)
    assert (
        _sha256(ROLE_REPORT) == report["inputs"]["role_qualification"]["sha256"]
    )
    assert _sha256(PREFLIGHT_REPORT) == report["inputs"]["preflight"]["sha256"]
    assert (
        preflight["m112_admission_canary_readback"]["admitted_object_count"]
        == 8
    )
    assert (
        preflight["m112_admission_canary_readback"]["canaried_object_count"]
        == 8
    )
    expected_identities = {
        (item["dataset"], item["revision"], item["path"], item["sha256"])
        for item in preflight["m112_admission_canary_readback"][
            "current_role_qualification"
        ]["admitted_objects"]
    }
    observed_identities = {
        (item["dataset"], item["revision"], item["path"], item["sha256"])
        for item in report["objects"]
    }
    assert observed_identities == expected_identities
    assert len(role_report["objects"]) == 16
    for row in report["objects"]:
        contract = _read(ROOT / row["contract_path"])
        assert _sha256(ROOT / row["contract_path"]) == row["contract_sha256"]
        assert contract["location"]["path"] == row["path"]
        assert contract["location"]["sha256"] == row["sha256"]
        assert contract["location"]["bytes"] == row["byte_count"]
        assert contract["recovery"]["independent"] is False
        assert (
            contract["recovery"]["checksum_inventory"]["sha256"]
            == report["inputs"]["public_manifest"]["sha256"]
        )
        assert (
            contract["recovery"]["restore_receipt"]["sha256"]
            == report["inputs"]["restore"]["issue_comment_body_sha256"]
        )
        assert contract["verification"]["status"] == "passed"
