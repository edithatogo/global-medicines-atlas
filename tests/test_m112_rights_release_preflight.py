"""Current M-112 rights preflight preserves exact scope and release gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261022-12.json"
)
PREVIOUS_PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261022-11.json"
)
PRESERVED_MAIN_PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261020-5.json"
)
PRESERVED_MAIN_PREFLIGHT_SHA256 = (
    "6022ff3ca2b1a5fe8a095bc5ebba48e3ac86297e3b7ddeff63e92ea5af21dc82"
)
PRESERVED_AUGUST_RIGHTS_PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261020-6.json"
)
PRESERVED_AUGUST_RIGHTS_PREFLIGHT_SHA256 = (
    "20cf284b95eb83436fdd437eca1d5075dda1bc6bc23bda7c12f1591d25c9bd3f"
)


def _json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def test_preflight_binds_current_inputs_and_preserves_historical_snapshot() -> (
    None
):
    report = _json(PREFLIGHT)
    for path, expected_digest in report["inputs"].items():
        assert (
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            == expected_digest
        )
    assert report["status"] == (
        "frozen_m112_exact_object_rights_attested_lineage_and_admission_gaps_open"
    )
    assert report["effective_m112_rights"]["resolved_object_count"] == 1759
    assert report["effective_m112_rights"]["unresolved_object_count"] == 0
    assert not any(
        "full PBS utilisation vocabulary exclusion review" in item["work"]
        for item in report["remaining_rights_work"]
    )
    previous = report["previous_preflight"]
    assert previous["path"].endswith(
        "australian-m112-rights-release-preflight-20261022-11.json"
    )
    assert previous["preserved_unchanged"] is True
    assert (
        hashlib.sha256(PREVIOUS_PREFLIGHT.read_bytes()).hexdigest()
        == previous["sha256"]
    )
    previous_report = _json(PREVIOUS_PREFLIGHT)
    assert (
        previous_report["release_and_admission_boundaries"]["v4_admissions"]
        == 8
    )
    assert (
        previous_report["release_and_admission_boundaries"]["consumer_canaries"]
        == 8
    )
    reconciliation = report["current_rights_reconciliation"]
    assert reconciliation["approved_denominator"] == 1759
    assert reconciliation["membership_changed"] is False
    assert reconciliation["v4_admissions"] == 8
    assert reconciliation["consumer_canaries"] == 8
    assert reconciliation["deferred_objects"] == 1751
    assert (
        hashlib.sha256((ROOT / reconciliation["path"]).read_bytes()).hexdigest()
        == reconciliation["sha256"]
    )
    q2 = report["q2_admission"]
    assert q2["workflow_run_id"] == 39419974066
    assert q2["consumer_canary_passed"] is True
    assert q2["source_values_or_rows_interpreted"] is False
    assert q2["source_payload_bytes_retained"] is False
    assert q2["reader_cache_bytes_after_close"] == 0
    assert (
        hashlib.sha256((ROOT / q2["receipt_path"]).read_bytes()).hexdigest()
        == q2["receipt_sha256"]
    )
    assert any(
        run["run_id"] == 39419974066
        for run in report["m112_admission_canary_readback"][
            "successful_workflow_runs"
        ]
    )
    raw = report["mbs_raw_object_rights_attestation"]
    assert raw["object_count"] == 6
    assert raw["public_release_rights_attested"] is True
    assert raw["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed"
    )
    assert raw["b1_b2_lineage_or_admission_inferred"] is False
    assert raw["v4_admission"] is False
    assert raw["consumer_canary"] is False
    q3 = report["q3_admission"]
    assert q3["workflow_run_id"] == 39356792827
    assert q3["consumer_canary_passed"] is True
    assert (
        hashlib.sha256((ROOT / q3["receipt_path"]).read_bytes()).hexdigest()
        == q3["receipt_sha256"]
    )
    projection = report["pbs_source_archive_exact_publication"][
        "source_projection"
    ]
    assert projection["public_release_rights_attested"] is True
    assert projection["permission_instrument_independently_reviewed"] is False
    assert projection["release_performed_by_this_reconciliation"] is False


def test_scoped_rights_do_not_cross_object_or_release_boundaries() -> None:
    report = _json(PREFLIGHT)
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
    gates = report["release_and_admission_boundaries"]
    assert gates["all_remaining_deferrals_preserved"] is True
    assert gates["deferred_objects"] == 1751
    assert gates["v4_admissions"] == 8
    assert gates["consumer_canaries"] == 8
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
    assert scope["scope"]["rights_authorized_by_this_record"] is True
    assert scope["scope"]["rights_state"] == (
        "maintainer_attested_exact_public_release_permission_for_bronze_projection"
    )
    assert scope["scope"]["frozen_m112_object_count"] == 1759
    assert all(
        not item["in_frozen_m112_inventory"] for item in scope["objects"]
    )
    assert all(
        item["rights_state"] == scope["scope"]["rights_state"]
        for item in scope["objects"]
    )
    assert all(
        not item["in_frozen_m112_inventory"] for item in scope["objects"]
    )
    assert scope["scope"]["public_release_performed_by_this_action"] is False


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


def test_latest_main_rights_snapshot_is_preserved_without_replacing_q3_delta() -> (
    None
):
    report = _json(PRESERVED_AUGUST_RIGHTS_PREFLIGHT)

    assert (
        hashlib.sha256(
            PRESERVED_AUGUST_RIGHTS_PREFLIGHT.read_bytes()
        ).hexdigest()
        == PRESERVED_AUGUST_RIGHTS_PREFLIGHT_SHA256
    )
    assert report["previous_preflight"]["sha256"] == (
        PRESERVED_MAIN_PREFLIGHT_SHA256
    )
    assert report["august_2026_mbs_bronze_projections"][
        "attestation_sha256"
    ] == ("d746b166b6c9de75b0ff00c1a709c8929535dc3373f4bfd574a8727e789b8b9f")
    assert report["cms_hcpcs_reference"][
        "latest_admission_reviewer_status"
    ] == ("approved")
    assert report["release_and_admission_boundaries"]["v4_admissions"] == 3
    assert report["release_and_admission_boundaries"]["consumer_canaries"] == 3


def test_pbs_rights_attestation_is_exact_and_keeps_other_gates_open() -> None:
    report = _json(PREFLIGHT)
    pbs = report["pbs_utilisation_raw_objects"]
    assert pbs["full_object_release_requires_exclusion_review"] is False
    assert pbs["rights_exclusion_fully_resolved_by_exact_attestation"] is True
    assert pbs["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed"
    )
    assert pbs["exact_rights_attestation_path"].endswith(
        "australian-pbs-utilisation-six-object-rights-attestation-20261020.json"
    )
    assert pbs["public_release_performed_by_this_reconciliation"] is False
    assert pbs["v4_admission"] is False
    assert pbs["consumer_canary"] is False
    assert len(pbs["objects"]) == 6
    assert all(
        obj["rights_state"] == pbs["rights_state"] for obj in pbs["objects"]
    )
    limited_screen = pbs["limited_vocabulary_screen"]
    assert (
        limited_screen["results"]["full_vocabulary_exclusion_review_complete"]
        is False
    )
    assert (
        limited_screen["full_object_release_requires_exclusion_review"] is False
    )
    assert (
        limited_screen["rights_exclusion_fully_resolved_by_exact_attestation"]
        is True
    )


def test_q1_hr_exact_hosted_identity_is_in_current_preflight() -> None:
    report = _json(PREFLIGHT)
    q1 = report["q1_hr_admission"]
    assert q1["workflow_run_id"] == 39575404598
    assert q1["workflow_commit"] == "b6e8a8e4f6d633dfea0056104b62972a669c1b3e"
    assert q1["admissions"] == q1["consumer_canaries"] == 1
    assert q1["source_values_or_rows_interpreted"] is False
    assert q1["reader_cache_bytes_after_close"] == 0
    receipt_path = ROOT / q1["path"]
    assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() == q1["sha256"]
