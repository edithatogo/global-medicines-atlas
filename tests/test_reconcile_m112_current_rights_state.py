"""Effective rights do not overwrite history or imply product admission."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from scripts.reconcile_m112_current_rights_state import build_report

ROOT = Path(__file__).resolve().parents[1]


def test_current_m112_rights_reconcile_exact_object_groups_and_cms_effective_state() -> (
    None
):
    report = build_report(ROOT, observed_at="2026-10-19T13:00:00Z")

    assert report["frozen_inventory"]["object_count"] == 1759
    assert report["frozen_inventory"]["membership_changed"] is False
    assert report["frozen_inventory"]["all_b1_b2_lineages_complete"] is True
    assert report["effective_m112_rights"]["resolved_object_count"] == 22
    assert report["effective_m112_rights"]["unresolved_object_count"] == 1737
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
    assert (
        report["august_2026_mbs_bronze_projections"]["derived_output_authority"]
        == "absent"
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
        "maintainer_attested_exact_public_release_permission_for_silver_object",
        "underlying source authorization exists; no projection rights conclusion added",
        "unresolved: source-specific rights and per-record provenance not qualified",
    }
