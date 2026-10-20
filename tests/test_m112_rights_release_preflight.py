"""Current M-112 rights preflight preserves exact scope and release gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261020-4.json"
)
PREVIOUS_PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261020-3.json"
)
PRESERVED_MAIN_PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261020-5.json"
)
PRESERVED_MAIN_PREFLIGHT_SHA256 = (
    "6022ff3ca2b1a5fe8a095bc5ebba48e3ac86297e3b7ddeff63e92ea5af21dc82"
)


def _json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def test_preflight_binds_current_inputs_and_preserves_historical_snapshot() -> (
    None
):
    report = _json(PREFLIGHT)
    assert report["status"] == "current_m112_admission_readback_refreshed"
    previous = report["previous_preflight"]
    assert previous["path"].endswith(
        "australian-m112-rights-release-preflight-20261020-3.json"
    )
    assert previous["preserved_unchanged"] is True
    assert (
        hashlib.sha256(PREVIOUS_PREFLIGHT.read_bytes()).hexdigest()
        == previous["sha256"]
    )
    previous_report = _json(PREVIOUS_PREFLIGHT)
    assert (
        previous_report["release_and_admission_boundaries"]["v4_admissions"]
        == 4
    )
    assert (
        previous_report["release_and_admission_boundaries"]["consumer_canaries"]
        == 4
    )
    reconciliation = report["current_rights_reconciliation"]
    assert reconciliation["approved_denominator"] == 1759
    assert reconciliation["membership_changed"] is False
    assert reconciliation["v4_admissions"] == 4
    assert reconciliation["consumer_canaries"] == 4
    assert reconciliation["deferred_objects"] == 1755
    assert (
        hashlib.sha256((ROOT / reconciliation["path"]).read_bytes()).hexdigest()
        == reconciliation["sha256"]
    )
    q3 = report["q3_admission"]
    assert q3["workflow_run_id"] == 39356792827
    assert q3["consumer_canary_passed"] is True
    assert (
        hashlib.sha256((ROOT / q3["receipt_path"]).read_bytes()).hexdigest()
        == q3["receipt_sha256"]
    )


def test_scoped_rights_do_not_cross_object_or_release_boundaries() -> None:
    report = _json(PREVIOUS_PREFLIGHT)
    july = report["july_2025_mbs_silver"]
    assert len(july["objects"]) == 6
    assert july["public_release_authorized"] is True
    assert july["public_release_performed"] is False
    current_public = july["current_public_tree_readback"]
    assert current_public["dataset"] == (
        "edithatogo/australian-mbs-source-archive"
    )
    assert current_public["revision"] == (
        "42d73b6facac016f14a335d36d83f1a3b630add8"
    )
    assert current_public["anonymous_metadata_identity_verified"] is True
    assert current_public["exact_object_count"] == 6
    assert current_public["public_release_observed"] is True
    assert current_public["current_revision_payload_bytes_reverified"] is False
    assert july["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed_or_located_at_maintainer_direction"
    )
    august = report["august_2026_mbs_bronze_projections"]
    assert len(august["objects"]) == 4
    assert august["rights_state"] == (
        "maintainer_attested_exact_public_release_permission_for_bronze_projection"
    )
    assert august["public_release_rights_attested"] is True
    assert august["public_release_performed_by_this_action"] is False
    assert august["m108_assessment_derived_output_authority"] == "absent"
    assert all(obj["lineage_complete"] for obj in august["objects"])
    assert all(
        obj["rights_state"] == august["rights_state"]
        for obj in august["objects"]
    )
    cms = report["cms_hcpcs_reference"]
    assert cms["rights_state"] == "permitted"
    assert cms["reviewer_status"] == "approved"
    assert cms["acquisition_time_rights_state_preserved"] == "unknown"
    assert cms["external_publication_authorized"] is False
    assert cms["derived_table_rights_concluded"] is False
    assert report["pbs_utilisation_raw_objects"][
        "full_object_release_requires_exclusion_review"
    ]
    gates = report["release_and_admission_boundaries"]
    assert gates["all_remaining_deferrals_preserved"] is True
    assert gates["deferred_objects"] == 1755
    assert gates["v4_admissions"] == 4
    assert gates["consumer_canaries"] == 4
    assert gates["external_publications_performed"] is False


def test_out_of_denominator_mbs_outputs_remain_a_separate_rights_exception() -> (
    None
):
    report = _json(PREVIOUS_PREFLIGHT)
    exception = report["august_2026_mbs_out_of_denominator_scope_exception"]
    scope = _json(ROOT / exception["path"])
    assert exception["object_count"] == 4
    assert exception["dataset_revision"] == scope["revision"]
    assert exception["outside_frozen_inventory"] is True
    assert exception["frozen_inventory_membership_changed"] is False
    assert scope["scope"]["rights_authorized_by_this_record"] is False
    assert scope["scope"]["rights_state"] == "unresolved"
    assert scope["scope"]["frozen_m112_object_count"] == 1759
    assert all(
        not item["in_frozen_m112_inventory"] for item in scope["objects"]
    )
    assert all(
        item["rights_state"].startswith("unresolved_")
        for item in scope["objects"]
    )


def test_reimbursement_projection_rights_are_bounded_and_do_not_admit() -> None:
    report = _json(PREVIOUS_PREFLIGHT)
    projections = report["reimbursement_atlas_medallion_projections"]
    assert projections["object_count"] == 12
    assert projections["public_redistribution_rights_attested"] is True
    assert projections["public_release_performed"] is False
    assert projections["v4_admissions"] == 0
    assert projections["consumer_canaries"] == 0
    assert all(
        item["rights_state"] == projections["rights_state"]
        for item in projections["objects"]
    )
    assert all(item["lineage_complete"] for item in projections["objects"])
    assert all(not item["v4_admission"] for item in projections["objects"])
    assert all(not item["consumer_canary"] for item in projections["objects"])


def test_main_cms_rights_readback_is_preserved_separately_from_m112_counts() -> (
    None
):
    report = _json(PRESERVED_MAIN_PREFLIGHT)

    assert (
        hashlib.sha256(PRESERVED_MAIN_PREFLIGHT.read_bytes()).hexdigest()
        == PRESERVED_MAIN_PREFLIGHT_SHA256
    )
    assert report["cms_hcpcs_reference"]["latest_admission_state"] == "landed"
    assert (
        report["cms_hcpcs_reference"]["latest_admission_reviewer_status"]
        == "approved"
    )
    assert (
        report["cms_hcpcs_reference"]["acquisition_time_rights_state_preserved"]
        == "unknown"
    )
    assert report["release_and_admission_boundaries"]["v4_admissions"] == 3
    assert report["release_and_admission_boundaries"]["consumer_canaries"] == 3
