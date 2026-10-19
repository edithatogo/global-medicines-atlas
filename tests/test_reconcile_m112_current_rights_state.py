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
)

ROOT = Path(__file__).resolve().parents[1]


def test_current_m112_rights_reconcile_exact_object_groups_and_cms_effective_state() -> (
    None
):
    report = build_report(ROOT, observed_at="2026-10-19T13:00:00Z")

    assert report["frozen_inventory"]["object_count"] == 1759
    assert report["frozen_inventory"]["membership_changed"] is False
    assert report["frozen_inventory"]["all_b1_b2_lineages_complete"] is True
    assert report["effective_m112_rights"]["resolved_object_count"] == 32
    assert report["effective_m112_rights"]["unresolved_object_count"] == 1727
    assert report["exact_july_2025_mbs_silver"]["object_count"] == 6
    assert (
        report["exact_july_2025_mbs_silver"]["public_release_authorized"]
        is True
    )
    assert (
        report["exact_july_2025_mbs_silver"]["public_release_performed"]
        is False
    )
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

    assert report["boundaries"]["all_1759_deferrals_preserved"] is True
    assert report["boundaries"]["v4_admissions"] == 0
    assert report["boundaries"]["consumer_canaries"] == 0
    assert report["boundaries"]["source_payload_bytes_read"] is False


def test_rights_counts_cover_every_frozen_object() -> None:
    report = build_report(ROOT, observed_at="2026-10-19T13:00:00Z")
    counts = cast(
        "list[dict[str, Any]]", report["effective_m112_rights"]["state_counts"]
    )

    assert sum(item["object_count"] for item in counts) == 1759
    assert all(item["object_count"] > 0 for item in counts)
    assert {item["state"] for item in counts} >= {
        "maintainer_attested_exact_public_release_permission_for_bronze_projection",
        "maintainer_attested_exact_public_release_permission_for_silver_object",
        "maintainer_attested_dataset_publication_permission_with_vocabulary_exclusion",
        "authorized_exact_source_release_permitted",
        "unresolved: source-specific rights and per-record provenance not qualified",
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
