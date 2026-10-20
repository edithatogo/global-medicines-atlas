"""Effective rights do not overwrite history or imply product admission."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
import scripts.reconcile_m112_current_rights_state as rights_reconciliation
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
    assert report["effective_m112_rights"]["resolved_object_count"] == 1759
    assert report["effective_m112_rights"]["unresolved_object_count"] == 0
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

    cms = report["cms_hcpcs_external_reference"]
    assert cms["inside_m112_frozen_inventory"] is False
    assert cms["rights_state"] == "permitted"
    assert cms["reviewer_status"] == "approved"
    assert cms["acquisition_time_rights_state_preserved"] == "unknown"
    assert cms["latest_admission_state"] == "landed"
    assert cms["latest_admission_reviewer_status"] == "approved"
    assert cms["b2_state"] == "external_reference_only"
    assert cms["processing_or_v4_admission_authorized"] is False
    assert cms["consumer_canaries_authorized"] is False
    assert cms["derived_table_rights_concluded"] is False
    assert cms["external_publication_authorized"] is False

    assert report["boundaries"]["all_remaining_deferrals_preserved"] is True
    assert report["boundaries"]["deferred_objects"] == 1753
    assert report["boundaries"]["v4_admissions"] == 6
    assert report["boundaries"]["consumer_canaries"] == 6
    assert report["boundaries"]["source_payload_bytes_read"] is True


def test_exact_six_mbs_raw_rights_attestation_preserves_lineage_and_release_gates() -> (
    None
):
    report = build_report(ROOT, observed_at="2026-10-20T00:00:00Z")
    raw = report["mbs_raw_object_rights_attestation"]
    assert raw["object_count"] == 6
    assert raw["public_release_rights_attested"] is True
    assert raw["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed"
    )
    assert raw["b1_b2_lineage_or_admission_inferred"] is False
    assert raw["public_release_performed"] is False
    assert raw["v4_admission"] is False
    assert raw["consumer_canary"] is False
    assert (
        sum(
            "sidecar" in obj["pre_attestation_rights_review_state"]
            for obj in raw["objects"]
        )
        == 2
    )
    assert report["effective_m112_rights"]["resolved_object_count"] == 1759
    assert report["effective_m112_rights"]["unresolved_object_count"] == 0


def test_exact_attestation_resolves_rights_without_overstating_limited_screen() -> (
    None
):
    report = build_report(ROOT, observed_at="2026-10-20T00:00:00Z")
    pbs = report["pbs_utilisation_raw_objects"]
    screen = pbs["limited_vocabulary_screen"]
    assert (
        screen["results"]["full_vocabulary_exclusion_review_complete"] is False
    )
    assert pbs["unlicensed_vocabulary_presence_reviewed"] is False
    assert pbs["full_object_release_requires_exclusion_review"] is False
    assert screen["full_object_release_requires_exclusion_review"] is False
    assert (
        screen["rights_exclusion_fully_resolved_by_exact_attestation"] is True
    )
    assert report["boundaries"]["source_payload_bytes_read"] is True
    assert report["boundaries"]["source_payload_values_inspected"] is True
    assert report["boundaries"]["source_payload_values_emitted"] is False
    assert report["boundaries"]["source_payload_files_written"] is False


def test_exact_pbs_utilisation_rights_attestation_is_bounded() -> None:
    report = build_report(ROOT, observed_at="2026-10-20T00:00:00Z")
    pbs = report["pbs_utilisation_raw_objects"]

    assert pbs["object_count"] == 6
    assert pbs["public_release_authorized_within_scope"] is True
    assert pbs["maintainer_asserted_redistribution_permission"] is True
    assert pbs["unlicensed_vocabulary_presence_reviewed"] is False
    assert pbs["full_object_release_requires_exclusion_review"] is False
    assert pbs["rights_exclusion_fully_resolved_by_exact_attestation"] is True
    assert pbs["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed"
    )
    assert pbs["rights_scope_includes_all_file_contents"] is True
    assert pbs["public_release_performed_by_this_reconciliation"] is False
    assert pbs["v4_admission"] is False
    assert pbs["consumer_canary"] is False
    assert (
        "unlicensed vocabulary redistribution" in pbs["publication_exclusions"]
    )
    assert all(
        obj["sha256"] and obj["byte_count"] > 0 for obj in pbs["objects"]
    )


def test_pbs_utilisation_attestation_is_bound_to_all_six_exact_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "attestation.json"
    attestation = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-pbs-utilisation-six-object-rights-attestation-20261020.json"
        ).read_text()
    )
    attestation["authorized_objects"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(attestation))
    monkeypatch.setattr(
        rights_reconciliation,
        "PBS_UTILISATION_EXACT_RIGHTS_ATTESTATION",
        path,
    )

    with pytest.raises(
        ValueError,
        match="PBS utilisation exact rights attestation did not reconcile",
    ):
        build_report(ROOT, observed_at="2026-10-20T00:00:00Z")


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

    assert report["effective_m112_rights"]["resolved_object_count"] == 1759
    assert report["effective_m112_rights"]["unresolved_object_count"] == 0
    pbs_archive = report["pbs_source_archive_exact_publication"]
    assert pbs_archive["historical_acquisition_rights_state"] == "unknown"
    assert pbs_archive["rights_state"] == permission["rights_state"]
    assert pbs_archive["source_projection"]["rights_state"] == (
        "maintainer_attested_exact_public_release_permission_for_bronze_projection"
    )
    assert (
        pbs_archive["source_projection"]["public_release_rights_attested"]
        is True
    )
    assert (
        pbs_archive["source_projection"][
            "permission_instrument_independently_reviewed"
        ]
        is False
    )
    assert (
        pbs_archive["source_projection"][
            "release_performed_by_this_reconciliation"
        ]
        is False
    )
    assert pbs_archive["source_projection"]["v4_admission"] is False
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    permission_path = tmp_path / "permission.json"
    monkeypatch.setattr(
        rights_reconciliation, "PBS_RAW_PERMISSION", permission_path
    )
    permission_path.write_bytes(
        (
            ROOT
            / "quality/qualifications/reimbursement-atlas-pbs-raw-permission-20260831.json"
        ).read_bytes()
    )
    permission = json.loads(permission_path.read_text())
    permission["permission_status"] = "revoked"
    permission["revoked_at"] = "2026-10-20"
    permission_path.write_text(json.dumps(permission))

    with pytest.raises(ValueError, match="PBS raw redistribution permission"):
        build_report(ROOT, observed_at="2026-10-20T00:00:00Z")


def test_cms_effective_rights_readback_fails_closed_if_latest_admission_unreviewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = json.loads(
        (
            ROOT
            / "quality/qualifications/cms-hcpcs-rights-review-20261019.json"
        ).read_text()
    )
    admission_path = tmp_path / "admission.json"
    admission_source = (
        ROOT / "quality/bronze/admissions/us-cms-hcpcs/"
        "db750eb63ae9d6037145e1acddc800ff2e93288640fc59fba97e59c8d947ce2a/"
        "d820173ded1797b36b5504da096d725746b0fef1288d4fb632b9897e3a9876c6.json"
    )
    admission_path.write_bytes(admission_source.read_bytes())
    review["rights_review"]["superseding_admission_path"] = str(admission_path)
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review))
    monkeypatch.setattr(rights_reconciliation, "CMS_REVIEW", review_path)
    admission = json.loads(admission_path.read_text())
    admission["reviewer_status"] = "unreviewed"
    admission_path.write_text(json.dumps(admission))

    with pytest.raises(ValueError, match="CMS HCPCS admission rights review"):
        build_report(ROOT, observed_at="2026-10-20T00:00:00Z")


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
        "maintainer_attested_exact_public_release_permission_for_bronze_projection"
    )
    assert (
        pbs_archive["source_projection"]["public_release_rights_attested"]
        is True
    )
    assert (
        pbs_archive["source_projection"][
            "permission_instrument_independently_reviewed"
        ]
        is False
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

    assert readback["admitted_object_count"] == 6
    assert readback["canaried_object_count"] == 6
    assert any(
        run["run_id"] == 39356792827
        for run in readback["successful_workflow_runs"]
    )
    assert readback["deferred_object_count"] == 1753
    assert len(readback["current_role_qualification"]["admitted_objects"]) == 6
    assert readback["object"]["rights_state"] == (
        "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified"
    )
    assert any(
        run["run_id"] == 39419974066
        for run in readback["successful_workflow_runs"]
    )
    assert len(readback["successful_workflow_runs"]) == 5
    q2_path = (
        "quality/qualifications/"
        "australian-m112-v4-demographics-q2-may-"
        "admission-qualification-20261020.json"
    )
    assert (
        report["evidence_inputs"][q2_path]
        == hashlib.sha256((ROOT / q2_path).read_bytes()).hexdigest()
    )
    assert readback["unique_object_counts_are_deduplicated_across_runs"] is True
    assert readback["source_values_or_rows_interpreted"] is False
    assert readback["native_workbook_layout_qualified"] is False
    assert readback["public_dataset_mutated_by_reconciliation"] is False
    assert readback["overlay_object_flags_pre_readback"] == {
        "disposition": "deferred_not_admitted",
        "v4_admission": False,
        "consumer_canary": False,
    }


def test_q2_canary_count_fails_closed_without_its_exact_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def read_without_q2_canary(root: Path, path: Path) -> dict[str, Any]:
        receipt = cast("dict[str, Any]", json.loads((root / path).read_text()))
        if path == rights_reconciliation.M112_Q2_ADMISSION_CANARY:
            receipt["consumer_canary"] = None
        return receipt

    monkeypatch.setattr(rights_reconciliation, "_read", read_without_q2_canary)
    with pytest.raises(
        TypeError, match="Q2 M-112 consumer-canary receipt is malformed"
    ):
        build_report(ROOT, observed_at="2026-10-20T12:00:00Z")


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
        "maintainer_attested_exact_public_release_permission_for_pbs_utilisation_raw_object",
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


def test_pbs_scope_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authorization_path = tmp_path / "authorization.json"
    monkeypatch.setattr(
        rights_reconciliation,
        "PBS_UTILISATION_AUTHORIZATION",
        authorization_path,
    )
    authorization_path.write_bytes(
        (
            ROOT
            / "quality/qualifications/australian-pbs-utilisation-publication-authorization.json"
        ).read_bytes()
    )
    authorization = json.loads(authorization_path.read_text())
    authorization["allowed_domains"] = ["example.invalid"]
    authorization_path.write_text(json.dumps(authorization))

    with pytest.raises(
        ValueError, match="PBS utilisation rights scope mismatch"
    ):
        build_report(ROOT, observed_at="2026-10-19T13:00:00Z")


def test_pbs_projection_attestation_must_match_frozen_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read: Any = rights_reconciliation.__dict__["_read"]

    def read_with_changed_projection_revision(
        root: Path, relative: Path
    ) -> dict[str, Any]:
        value = read(root, relative)
        if relative == rights_reconciliation.FROZEN_OVERLAY:
            value = deepcopy(value)
            projection = next(
                item
                for item in value["objects"]
                if item["path"]
                == rights_reconciliation.PBS_SOURCE_PROJECTION_PATH
            )
            projection["revision"] = "0" * 40
        return value

    monkeypatch.setattr(
        rights_reconciliation, "_read", read_with_changed_projection_revision
    )
    with pytest.raises(
        ValueError,
        match="exact PBS source publication evidence did not reconcile",
    ):
        build_report(ROOT, observed_at="2026-10-20T00:00:00Z")


def test_pbs_limited_screen_must_bind_every_pinned_lineage_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    screen_path = tmp_path / "screen.json"
    screen = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-pbs-utilisation-limited-vocabulary-screen-20261020.json"
        ).read_text()
    )
    screen["objects"] = []
    screen_path.write_text(json.dumps(screen))
    monkeypatch.setattr(
        rights_reconciliation, "PBS_UTILISATION_LIMITED_SCREEN", screen_path
    )

    with pytest.raises(
        ValueError, match="PBS limited vocabulary screen did not reconcile"
    ):
        build_report(ROOT, observed_at="2026-10-20T00:00:00Z")
