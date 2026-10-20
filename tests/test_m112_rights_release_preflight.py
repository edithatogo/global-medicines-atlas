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
    historical = report["historical_preflight"]
    assert historical["superseded"] is True
    assert historical["preserved_unchanged"] is True
    assert historical["path"].endswith("preflight-20261019.json")
    assert report["frozen_inventory"]["object_count"] == 1759
    assert report["frozen_inventory"]["membership_changed"] is False
    assert report["effective_m112_rights"]["resolved_object_count"] == 1752
    assert report["effective_m112_rights"]["unresolved_object_count"] == 7
    assert report["previous_preflight"]["path"].endswith(
        "australian-m112-rights-release-preflight-20261020-3.json"
    )
    assert report["previous_preflight"]["preserved_unchanged"] is True
    previous_preflight = ROOT / report["previous_preflight"]["path"]
    assert (
        hashlib.sha256(previous_preflight.read_bytes()).hexdigest()
        == report["previous_preflight"]["sha256"]
    )
    pbs_archive = report["pbs_source_archive_exact_publication"]
    assert pbs_archive["exact_object_publication_authorized"] is True
    assert pbs_archive["rights_state"] == (
        "owner_attested_pbs_raw_redistribution_permission"
    )
    assert pbs_archive["rights_conclusion_made"] is True
    assert report["pbs_raw_redistribution_permission"]["object_count"] == 1708
    assert (
        report["pbs_raw_redistribution_permission"][
            "project_publication_authorized_by_this_record"
        ]
        is False
    )
    assert (
        pbs_archive["source_projection"][
            "derived_rights_inferred_from_source_permission"
        ]
        is False
    )


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
    assert cms["superseded_admission_reviewer_status"] == "unreviewed"
    assert cms["latest_admission_state"] == "landed"
    assert cms["latest_admission_reviewer_status"] == "approved"
    assert cms["external_publication_authorized"] is False
    assert cms["derived_table_rights_concluded"] is False
    assert report["pbs_utilisation_raw_objects"][
        "full_object_release_requires_exclusion_review"
    ]
    gates = report["release_and_admission_boundaries"]
    assert gates["all_remaining_deferrals_preserved"] is True
    assert gates["deferred_objects"] == 1756
    assert gates["v4_admissions"] == 3
    assert gates["consumer_canaries"] == 3
    assert gates["external_publications_performed"] is False


def test_out_of_denominator_mbs_outputs_remain_a_separate_rights_exception() -> (
    None
):
    report = _json(PREFLIGHT)
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
    assert scope["scope"]["frozen_inventory_membership_changed"] is False
    assert scope["scope"]["new_publication_performed"] is False
    assert scope["scope"]["public_release_performed_by_this_action"] is False
    assert all(
        not item["in_frozen_m112_inventory"] for item in scope["objects"]
    )
    attestation_ref = exception["attestation_path"]
    attestation_path = ROOT / attestation_ref
    attestation = _json(attestation_path)
    assert (
        hashlib.sha256(attestation_path.read_bytes()).hexdigest()
        == (exception["attestation_sha256"])
    )
    assert attestation["maintainer_response"] == "Attest exact four"
    assert attestation["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed_or_located_at_maintainer_direction"
    )
    assert attestation["public_release_rights_attested"] is True
    assert attestation["boundaries"]["new_publication_performed"] is False
    assert (
        attestation["boundaries"]["v4_admission_or_promotion_authorized"]
        is False
    )
    assert attestation["boundaries"]["consumer_canaries_authorized"] is False
    assert len(attestation["authorized_objects"]) == 4
    by_identity = {
        (item["path"], item["sha256"], item["byte_count"])
        for item in attestation["authorized_objects"]
    }
    assert by_identity == {
        (item["path"], item["sha256"], item["byte_count"])
        for item in scope["objects"]
    }
    assert all(
        item["rights_state"] == scope["scope"]["rights_state"]
        and item["permission_evidence"]
        == {
            "path": attestation_ref,
            "sha256": exception["attestation_sha256"],
        }
        for item in scope["objects"]
    )


def test_reimbursement_projection_rights_are_bounded_and_do_not_admit() -> None:
    report = _json(PREFLIGHT)
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
