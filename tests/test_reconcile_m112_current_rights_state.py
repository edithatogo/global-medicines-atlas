"""Effective rights do not overwrite history or imply product admission."""

from __future__ import annotations

import json
from pathlib import Path
from shutil import copytree
from typing import Any, cast

import pytest
from scripts.reconcile_m112_current_rights_state import (
    build_report,
    reconcile_august_mbs_attestation,
    reconcile_reimbursement_medallion_attestation,
)

ROOT = Path(__file__).resolve().parents[1]


def test_current_m112_rights_reconcile_exact_object_groups_and_cms_effective_state() -> (
    None
):
    report = build_report(ROOT, observed_at="2026-10-19T13:00:00Z")

    assert report["frozen_inventory"]["object_count"] == 1759
    assert report["frozen_inventory"]["membership_changed"] is False
    assert report["frozen_inventory"]["all_b1_b2_lineages_complete"] is True
    assert report["effective_m112_rights"]["resolved_object_count"] == 1752
    assert report["effective_m112_rights"]["unresolved_object_count"] == 7
    assert report["exact_july_2025_mbs_silver"]["object_count"] == 6
    assert (
        report["exact_july_2025_mbs_silver"]["public_release_authorized"]
        is True
    )
    assert (
        report["exact_july_2025_mbs_silver"]["public_release_performed"]
        is False
    )
    current_public_readback = report["exact_july_2025_mbs_silver"][
        "current_public_tree_readback"
    ]
    assert current_public_readback["dataset"] == (
        "edithatogo/australian-mbs-source-archive"
    )
    assert current_public_readback["revision"] == (
        "42d73b6facac016f14a335d36d83f1a3b630add8"
    )
    assert current_public_readback["anonymous_metadata_identity_verified"]
    assert current_public_readback["exact_object_count"] == 6
    assert (
        current_public_readback["current_revision_payload_bytes_reverified"]
        is False
    )
    assert current_public_readback["public_release_observed"] is True
    assert report["august_2026_mbs_bronze_projections"]["object_count"] == 4
    assert all(
        obj["lineage_complete"]
        for obj in report["august_2026_mbs_bronze_projections"]["objects"]
    )
    august = report["august_2026_mbs_bronze_projections"]
    assert august["rights_state"] == (
        "maintainer_attested_exact_public_release_permission_for_bronze_projection"
    )
    assert august["public_release_rights_attested"] is True
    assert august["m108_assessment_derived_output_authority"] == "absent"
    assert len(august["objects"]) == 4

    pbs = report["pbs_utilisation_raw_objects"]
    assert pbs["object_count"] == 6
    assert pbs["public_release_authorized_within_scope"] is True
    assert pbs["maintainer_asserted_redistribution_permission"] is True
    assert pbs["unlicensed_vocabulary_presence_reviewed"] is False
    assert pbs["full_object_release_requires_exclusion_review"] is True
    assert (
        "unlicensed vocabulary redistribution" in pbs["publication_exclusions"]
    )
    assert all(
        obj["sha256"] and obj["byte_count"] > 0 for obj in pbs["objects"]
    )

    cms = report["cms_hcpcs_external_reference"]
    assert cms["inside_m112_frozen_inventory"] is False
    assert cms["rights_state"] == "permitted"
    assert cms["reviewer_status"] == "approved"
    assert cms["acquisition_time_rights_state_preserved"] == "unknown"
    assert cms["latest_admission_state"] == "landed"
    assert cms["b2_state"] == "external_reference_only"
    assert cms["processing_or_v4_admission_authorized"] is False
    assert cms["consumer_canaries_authorized"] is False
    assert cms["derived_table_rights_concluded"] is False
    assert cms["external_publication_authorized"] is False

    assert report["boundaries"]["all_remaining_deferrals_preserved"] is True
    assert report["boundaries"]["deferred_objects"] == 1755
    assert report["boundaries"]["v4_admissions"] == 4
    assert report["boundaries"]["consumer_canaries"] == 4
    assert report["boundaries"]["source_payload_bytes_read"] is False


def test_pbs_raw_owner_permission_binds_exact_lineaged_objects_only() -> None:
    report = build_report(ROOT, observed_at="2026-10-20T00:00:00Z")
    permission = report["pbs_raw_redistribution_permission"]

    assert permission["source_owner_permission"]["permission_status"] == (
        "active"
    )
    assert permission["source_owner_permission"]["source_id"] == "au_pbs"
    assert permission["source_owner_permission"]["decision"] == (
        "allow_raw_redistribution"
    )
    assert permission["source_owner_permission"]["publication_state"] == (
        "not_asserted"
    )
    assert permission["rights_state"] == (
        "owner_attested_pbs_raw_redistribution_permission"
    )
    assert permission["object_count"] == 1708
    assert permission["dataset_counts"] == {
        "edithatogo/australian-pbs-source-archive": 1,
        "edithatogo/reimbursement-atlas": 1707,
    }
    assert permission["format_counts"] == {
        "csv": 3,
        "pdf": 1052,
        "zip": 653,
    }
    assert permission["b1_b2_lineage_complete"] is True
    assert permission["all_objects_remain_deferred"] is True
    assert permission["v4_admissions"] == 0
    assert permission["consumer_canaries"] == 0
    assert permission["external_publication_performed"] is False
    assert permission["project_publication_authorized_by_this_record"] is False
    assert all(
        obj["source_locator"].startswith(
            "https://www.pbs.gov.au/publication/schedule/"
        )
        for obj in permission["objects"]
    )
    assert all(obj["lineage_complete"] for obj in permission["objects"])
    assert all(obj["v4_admission"] is False for obj in permission["objects"])
    assert all(obj["consumer_canary"] is False for obj in permission["objects"])

    assert report["effective_m112_rights"]["resolved_object_count"] == 1752
    assert report["effective_m112_rights"]["unresolved_object_count"] == 7
    pbs_archive = report["pbs_source_archive_exact_publication"]
    assert pbs_archive["historical_acquisition_rights_state"] == "unknown"
    assert pbs_archive["rights_state"] == permission["rights_state"]
    assert pbs_archive["source_projection"]["rights_state"] == (
        "upstream redistribution terms unknown"
    )
    cms = report["cms_hcpcs_external_reference"]
    assert cms["rights_state"] == "permitted"
    assert cms["derived_table_rights_concluded"] is False


def test_reimbursement_medallion_rights_are_exact_and_do_not_admit() -> None:
    report = build_report(ROOT, observed_at="2026-10-20T00:00:00Z")
    projections = report["reimbursement_atlas_medallion_projections"]

    assert projections["object_count"] == 12
    assert projections["public_redistribution_rights_attested"] is True
    assert projections["public_release_performed"] is False
    assert projections["v4_admissions"] == 0
    assert projections["consumer_canaries"] == 0
    assert all(item["lineage_complete"] for item in projections["objects"])
    assert all(not item["v4_admission"] for item in projections["objects"])
    assert all(not item["consumer_canary"] for item in projections["objects"])


def test_pbs_raw_owner_permission_fails_closed_when_revoked(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "repo"
    copytree(
        ROOT,
        copied_root,
        ignore=lambda _directory, names: {
            name for name in names if name in {".git", ".venv"}
        },
    )
    permission_path = (
        copied_root
        / "quality/qualifications/reimbursement-atlas-pbs-raw-permission-20260831.json"
    )
    permission = json.loads(permission_path.read_text())
    permission["permission_status"] = "revoked"
    permission["revoked_at"] = "2026-10-20"
    permission_path.write_text(json.dumps(permission))

    with pytest.raises(ValueError, match="PBS raw redistribution permission"):
        build_report(copied_root, observed_at="2026-10-20T00:00:00Z")


def test_pbs_archive_publication_is_exact_and_does_not_clear_derivative() -> (
    None
):
    report = build_report(ROOT, observed_at="2026-10-19T13:00:00Z")
    pbs_archive = report["pbs_source_archive_exact_publication"]

    assert pbs_archive["dataset"] == "edithatogo/australian-pbs-source-archive"
    assert pbs_archive["path"] == "raw/2026-04-01/2026-04-01-XML-V3.zip"
    assert pbs_archive["sha256"] == (
        "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
    )
    assert pbs_archive["byte_count"] == 11156706
    assert pbs_archive["exact_object_publication_authorized"] is True
    assert pbs_archive["hosted_anonymous_digest_verification"] == "passed"
    assert pbs_archive["current_digest_matches_hosted_verification"] is True
    assert pbs_archive["upstream_redistribution_terms"].startswith(
        "owner-attested"
    )
    assert pbs_archive["historical_acquisition_rights_state"] == "unknown"
    assert pbs_archive["rights_conclusion_made"] is True
    assert pbs_archive["release_performed_by_this_reconciliation"] is False
    assert pbs_archive["v4_admission"] is False
    assert pbs_archive["source_projection"]["path"] == (
        "bronze/2026-04-01/pbs-v3-source.parquet"
    )
    assert pbs_archive["source_projection"]["rights_state"] == (
        "upstream redistribution terms unknown"
    )
    assert (
        pbs_archive["source_projection"][
            "derived_rights_inferred_from_source_permission"
        ]
        is False
    )


def test_m112_admission_and_canary_receipts_supersede_stale_overlay_flags() -> (
    None
):
    report = build_report(ROOT, observed_at="2026-10-19T13:00:00Z")
    readback = report["m112_admission_canary_readback"]

    assert readback["admitted_object_count"] == 4
    assert readback["canaried_object_count"] == 4
    assert any(
        run["run_id"] == 39356792827
        for run in readback["successful_workflow_runs"]
    )
    assert readback["deferred_object_count"] == 1755
    assert len(readback["current_role_qualification"]["admitted_objects"]) == 4
    assert readback["object"]["rights_state"] == (
        "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified"
    )
    assert len(readback["successful_workflow_runs"]) == 4
    assert readback["unique_object_counts_are_deduplicated_across_runs"] is True
    assert readback["source_values_or_rows_interpreted"] is False
    assert readback["native_workbook_layout_qualified"] is False
    assert readback["public_dataset_mutated_by_reconciliation"] is False
    assert readback["overlay_object_flags_pre_readback"] == {
        "disposition": "deferred_not_admitted",
        "v4_admission": False,
        "consumer_canary": False,
    }


def test_rights_counts_cover_every_frozen_object() -> None:
    report = build_report(ROOT, observed_at="2026-10-19T13:00:00Z")
    counts = cast(
        "list[dict[str, Any]]", report["effective_m112_rights"]["state_counts"]
    )

    assert sum(item["object_count"] for item in counts) == 1759
    assert all(item["object_count"] > 0 for item in counts)
    assert {item["state"] for item in counts} >= {
        "maintainer_attested_exact_public_release_permission_for_bronze_projection",
        "maintainer_attested_exact_public_release_permission_for_derived_projection",
        "maintainer_attested_exact_public_release_permission_for_silver_object",
        "maintainer_attested_dataset_publication_permission_with_vocabulary_exclusion",
        "authorized_exact_source_release_permitted",
        "owner_attested_pbs_raw_redistribution_permission",
    }


def test_august_mbs_rights_attestation_fails_closed_on_digest_mismatch() -> (
    None
):
    overlay = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261019-reimbursement-medallion-projection-lineage.json"
        ).read_text()
    )
    attestation = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-mbs-august-bronze-rights-attestation-20261020.json"
        ).read_text()
    )
    attestation["authorized_objects"][0]["sha256"] = "0" * 64
    with pytest.raises(
        ValueError, match="August MBS attestation identity mismatch"
    ):
        reconcile_august_mbs_attestation(overlay["objects"], attestation)


def test_reimbursement_medallion_attestation_fails_closed_on_identity_mismatch() -> (
    None
):
    overlay = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261019-reimbursement-medallion-projection-lineage.json"
        ).read_text()
    )
    attestation = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-reimbursement-atlas-medallion-rights-attestation-20261020.json"
        ).read_text()
    )
    attestation["authorized_objects"][0]["sha256"] = "0" * 64
    with pytest.raises(
        ValueError,
        match="Reimbursement Atlas rights attestation identity mismatch",
    ):
        reconcile_reimbursement_medallion_attestation(
            overlay["objects"], attestation
        )


def test_pbs_scope_mismatch_fails_closed(tmp_path: Path) -> None:
    copied_root = tmp_path / "repo"
    copytree(
        ROOT,
        copied_root,
        ignore=lambda _directory, names: {
            name for name in names if name in {".git", ".venv"}
        },
    )
    authorization_path = (
        copied_root
        / "quality/qualifications/australian-pbs-utilisation-publication-authorization.json"
    )
    authorization = json.loads(authorization_path.read_text())
    authorization["allowed_domains"] = ["example.invalid"]
    authorization_path.write_text(json.dumps(authorization))

    with pytest.raises(
        ValueError, match="PBS utilisation rights scope mismatch"
    ):
        build_report(copied_root, observed_at="2026-10-19T13:00:00Z")
