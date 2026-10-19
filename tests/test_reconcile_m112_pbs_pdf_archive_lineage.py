"""Verify exact PBS archive PDF lineage and independent gate boundaries."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from scripts import reconcile_m112_pbs_pdf_archive_lineage as module

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceManifest,
    RawEvidenceState,
)
from global_medicines_atlas.receipts import AcquisitionEvent, RightsState


def test_five_exact_pdf_reads_bind_reference_only_landed_lineage() -> None:
    lineage, artifacts, overlay = module.build_report()

    saved_lineage = json.loads(
        (module.ROOT / module.OUTPUT).read_text(encoding="utf-8")
    )
    saved_overlay = json.loads(
        (module.ROOT / module.OVERLAY_OUTPUT).read_text(encoding="utf-8")
    )
    assert saved_lineage == lineage
    assert saved_overlay == overlay

    assert len(lineage["objects"]) == 5
    assert lineage["boundaries"]["source_payload_bytes_persisted"] is False
    assert lineage["boundaries"]["source_payload_values_inspected"] is False
    assert (
        lineage["boundaries"]["rights_or_licensing_conclusion_added"] is False
    )
    assert overlay["updated_gate_totals"]["complete_raw_b1_b2_lineage"] == 1736
    assert (
        overlay["updated_gate_totals"]["complete_b1_b2_lineage_objects"] == 1746
    )
    assert (
        overlay["lineage_counts_after_expansion"]["incomplete_raw_lineages"]
        == 0
    )
    assert (
        overlay["lineage_counts_after_expansion"][
            "incomplete_projection_lineages"
        ]
        == 13
    )
    assert overlay["updated_gate_totals"]["preserved_deferrals"] == 1759
    assert overlay["updated_gate_totals"]["v4_admissions"] == 0
    assert overlay["updated_gate_totals"]["consumer_canaries"] == 0

    for item in lineage["objects"]:
        for relative, expected in lineage["output_bindings"].items():
            if relative in {
                item["acquisition_event_path"],
                item["b2_manifest_path"],
                item["landed_admission_path"],
            }:
                actual = hashlib.sha256(
                    (module.ROOT / relative).read_bytes()
                ).hexdigest()
                assert actual == expected
        event = AcquisitionEvent.model_validate_json(
            artifacts[Path(item["acquisition_event_path"])]
        )
        b2 = RawEvidenceManifest.model_validate_json(
            artifacts[Path(item["b2_manifest_path"])]
        )
        admission = BronzeAdmissionRecord.model_validate_json(
            artifacts[Path(item["landed_admission_path"])]
        )
        assert event.content_id == item["content_sha256"]
        assert event.rights_state is RightsState.UNKNOWN
        assert event.retrieval is not None
        assert (
            event.retrieval.retrieved_at.isoformat().replace("+00:00", "Z")
            == item["retrieval"]["retrieved_at"]
        )
        assert b2.row_count == 1
        assert b2.rows[0].state is RawEvidenceState.EXTERNAL_REFERENCE_ONLY
        assert b2.rows[0].content_id == item["content_sha256"]
        assert b2.rows[0].payload_sha256 is None
        assert b2.rows[0].byte_count is None
        assert admission.state is BronzeAdmissionState.LANDED
        assert admission.reviewer_status == "unreviewed"


def test_changed_pdf_digest_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    value = json.loads(
        (module.ROOT / module.READBACK).read_text(encoding="utf-8")
    )
    changed = copy.deepcopy(value)
    changed["objects"][0]["sha256_observed"] = "0" * 64
    path = tmp_path / "changed-readback.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    monkeypatch.setattr(module, "READBACK", path)
    with pytest.raises(ValueError, match="readback or source receipt binding"):
        module.build_report()


def test_changed_producer_receipt_line_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    value = json.loads(
        (module.ROOT / module.READBACK).read_text(encoding="utf-8")
    )
    changed = copy.deepcopy(value)
    changed["objects"][0]["producer_record_jsonl"] += " "
    path = tmp_path / "changed-receipt.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    monkeypatch.setattr(module, "READBACK", path)
    with pytest.raises(ValueError, match="readback or source receipt binding"):
        module.build_report()
