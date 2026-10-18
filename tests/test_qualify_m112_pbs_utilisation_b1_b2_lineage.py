"""Verify the six PBS utilisation B1/B2 lineages remain evidence-bound."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts import qualify_m112_pbs_utilisation_b1_b2_lineage as module

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
)
from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest
from global_medicines_atlas.receipts import AcquisitionEvent, RightsState


def test_six_pbs_utilisation_paths_have_exact_landed_b1_b2_records() -> None:
    report, outputs = module.build_report()

    assert len(report["objects"]) == 6
    assert report["scope"]["lineages_completed"] == 6
    assert report["boundaries"]["source_payload_bytes_read"] is False
    assert report["boundaries"]["rights_or_licensing_conclusion_added"] is False
    assert report["scope"]["rights_concluded"] is False
    assert len(outputs) == 18

    for item in report["objects"]:
        event = AcquisitionEvent.model_validate_json(
            outputs[Path(item["acquisition_event_path"])]
        )
        assert event.acquisition_id == item["acquisition_id"]
        assert event.content_id == item["content_sha256"]
        assert event.rights_state is RightsState.UNKNOWN

        b2 = RawEvidenceManifest.model_validate_json(
            outputs[Path(item["b2_manifest_path"])]
        )
        assert b2.row_count == 1
        assert b2.rows[0].external_reference == item["pinned_b2_reference"]
        assert b2.rows[0].payload_sha256 is None
        assert b2.rows[0].byte_count is None

        admission = BronzeAdmissionRecord.model_validate_json(
            outputs[Path(item["landed_admission_path"])]
        )
        assert admission.state is BronzeAdmissionState.LANDED
        assert admission.reviewer_status == "unreviewed"
        assert admission.content_id == item["content_sha256"]


def test_pbs_receipt_digest_mismatch_cannot_complete_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_json = module.read_json

    def changed_readback(path: Path) -> dict[str, object]:
        value = original_json(path)
        if path == module.READBACK_PATH:
            value["objects"][0]["receipt_sha256"] = "0" * 64
        return value

    monkeypatch.setattr(module, "read_json", changed_readback)
    with pytest.raises(ValueError, match="receipt identity or gates differ"):
        module.build_report()
