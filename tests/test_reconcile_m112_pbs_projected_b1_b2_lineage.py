"""Bind existing PBS B1/B2 projection joins to current unreviewed landings."""

from __future__ import annotations

import pytest
from scripts.reconcile_m112_pbs_projected_b1_b2_lineage import (
    EXPECTED_OBJECTS,
    build_report,
    projection_key,
)

from global_medicines_atlas.bronze_admission import BronzeAdmissionRecord
from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest
from global_medicines_atlas.receipts import AcquisitionEvent


def test_projection_key_rejects_missing_identity_fields() -> None:
    with pytest.raises(
        ValueError, match="PBS projection join lacks a complete object key"
    ):
        projection_key({"dataset": "example", "revision": None, "path": "x"})


def test_pinned_pbs_projection_joins_get_current_landed_records() -> None:
    report, outputs, overlay = build_report()

    assert len(report["objects"]) == EXPECTED_OBJECTS == 1703
    assert report["scope"]["unique_acquisition_events"] == 1702
    assert report["scope"]["source_receipt_projection_joins"] == 1703
    assert report["scope"]["lineages_completed"] == 1703
    assert report["boundaries"]["source_payload_bytes_read"] is False
    assert report["boundaries"]["source_payload_values_inspected"] is False
    assert report["boundaries"]["rights_or_licensing_conclusion_added"] is False
    assert report["boundaries"]["source_owner_records_modified"] is False
    assert report["boundaries"]["v4_admission_performed"] is False
    assert report["boundaries"]["consumer_canary_performed"] is False
    assert report["scope"]["all_objects_remain_deferred"] is True
    assert overlay["updated_gate_totals"]["complete_raw_b1_b2_lineage"] == 1725
    assert overlay["updated_gate_totals"]["complete_projection_lineage"] == 10
    assert (
        overlay["updated_gate_totals"]["complete_b1_b2_lineage_objects"] == 1735
    )
    assert overlay["updated_gate_totals"]["v4_admissions"] == 0
    assert overlay["updated_gate_totals"]["consumer_canaries"] == 0
    assert overlay["updated_gate_totals"]["preserved_deferrals"] == 1759
    assert (
        overlay["lineage_counts_after_expansion"]["incomplete_raw_lineages"]
        == 11
    )
    assert (
        overlay["lineage_counts_after_expansion"][
            "incomplete_projection_lineages"
        ]
        == 13
    )
    assert len(outputs) == 1702 * 3


def test_every_pbs_lineage_binds_all_roles_and_keeps_review_open() -> None:
    report, _, overlay = build_report()
    base_objects = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in overlay["objects"]
    }

    for row in report["objects"]:
        key = (row["dataset"], row["revision"], row["path"])
        frozen = base_objects[key]
        assert row["lineage_complete"] is True
        assert row["reviewer_status"] == "unreviewed"
        assert row["processing_admission"] is False
        assert row["v4_admission"] is False
        assert row["consumer_canary"] is False
        assert row["source_receipt_projection"]["record_sha256"]
        assert row["producer_b1"]["event_id"].startswith("event:")
        assert row["producer_b2"]["evidence_id"].endswith(row["content_sha256"])
        assert row["content_sha256"] == frozen["identity"]["sha256"]
        assert row["byte_count"] == frozen["identity"]["byte_count"]
        assert frozen["disposition"] == "deferred_not_admitted"


def test_generated_records_round_trip_and_match_report_bindings() -> None:
    report, outputs, _ = build_report()
    event_count = 0
    b2_count = 0
    admission_count = 0

    for path, body in outputs.items():
        assert report["output_bindings"][path.as_posix()]
        if "/imported-acquisitions/" in path.as_posix():
            AcquisitionEvent.model_validate_json(body)
            event_count += 1
        elif "/raw-evidence/" in path.as_posix():
            RawEvidenceManifest.model_validate_json(body)
            b2_count += 1
        elif "/admissions/" in path.as_posix():
            decision = BronzeAdmissionRecord.model_validate_json(body)
            assert decision.reviewer_status == "unreviewed"
            admission_count += 1

    assert event_count == b2_count == admission_count == 1702
