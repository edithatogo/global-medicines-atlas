"""Tests for exact July 2025 MBS source B1/B2 lineage binding."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from scripts import reconcile_m112_july_mbs_source_lineage as reconciliation

from global_medicines_atlas.bronze_admission import BronzeAdmissionRecord
from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest
from global_medicines_atlas.receipts import AcquisitionEvent, SourceReceipt

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    reconciliation.BASE,
    reconciliation.CURRENT_TREE,
    reconciliation.PUBLIC_ARCHIVE,
    reconciliation.V4_READBACK,
    reconciliation.V4_MANIFEST,
    reconciliation.SOURCE_RECEIPT,
    Path("scripts/reconcile_m112_july_mbs_source_lineage.py"),
)


def _fixture_root(tmp_path: Path) -> Path:
    for relative in INPUTS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, target)
    return tmp_path


def test_july_mbs_source_lineage_changes_only_the_exact_frozen_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    monkeypatch.setattr(reconciliation, "ROOT", root)
    baseline = json.loads((root / reconciliation.BASE).read_text())
    prior_membership = baseline["approved_path_membership_sha256"]
    prior = next(
        row
        for row in baseline["objects"]
        if row["path"] == reconciliation.SOURCE_PATH
    )

    reconciliation.main()

    qualification = json.loads((root / reconciliation.OUTPUT).read_text())
    overlay = json.loads((root / reconciliation.OVERLAY_OUTPUT).read_text())
    changed = [
        current
        for old, current in zip(
            baseline["objects"], overlay["objects"], strict=True
        )
        if old != current
    ]
    assert len(changed) == 1
    assert changed[0]["path"] == reconciliation.SOURCE_PATH
    assert changed[0]["revision"] == reconciliation.INVENTORY_REVISION
    assert changed[0]["b1_b2_lineage"]["complete"] is True
    assert changed[0]["rights"] == prior["rights"]
    assert overlay["approved_path_membership_sha256"] == prior_membership
    assert overlay["updated_gate_totals"]["approved_denominator"] == 1759
    assert overlay["updated_gate_totals"]["complete_raw_b1_b2_lineage"] == 22
    assert overlay["updated_gate_totals"]["v4_admissions"] == 0
    assert overlay["updated_gate_totals"]["consumer_canaries"] == 0
    assert overlay["updated_gate_totals"]["preserved_deferrals"] == 1759
    assert (
        overlay["current_b1_b2_lineage_expansion"]
        == baseline["current_b1_b2_lineage_expansion"]
    )
    assert (
        overlay["july_2025_mbs_source_lineage_expansion"][
            "cumulative_exact_receipt_acquisition_path_joins"
        ]
        == 27
    )
    assert (
        qualification["scope_limits"]["per_object_rights_gate_closed"] is False
    )
    assert (
        qualification["scope_limits"][
            "source_payload_bytes_requested_or_inspected"
        ]
        is False
    )

    receipt = SourceReceipt.model_validate_json(
        (root / qualification["lineage"]["source_receipt_path"]).read_bytes()
    )
    event = AcquisitionEvent.model_validate_json(
        (root / qualification["lineage"]["acquisition_event_path"]).read_bytes()
    )
    b2 = RawEvidenceManifest.model_validate_json(
        (root / qualification["lineage"]["b2_manifest_path"]).read_bytes()
    )
    admission = BronzeAdmissionRecord.model_validate_json(
        (root / qualification["lineage"]["landed_admission_path"]).read_bytes()
    )
    assert receipt.digest() == reconciliation.SOURCE_RECEIPT_SHA256
    assert event.acquisition_id == reconciliation.ACQUISITION_ID
    assert b2.rows[0].acquisition_id == event.acquisition_id
    assert b2.rows[0].external_reference == reconciliation.ARCHIVE_URI
    assert admission.acquisition_id == event.acquisition_id
    assert admission.reviewer_status == "unreviewed"


def test_bound_output_rejects_different_existing_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    monkeypatch.setattr(reconciliation, "ROOT", root)
    relative = (
        Path("quality/bronze/acquisitions/au-mbs")
        / f"{reconciliation.ACQUISITION_ID}.json"
    )
    destination = root / relative
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"retained event")

    with pytest.raises(ValueError, match="immutable evidence conflict"):
        reconciliation.main()

    assert destination.read_bytes() == b"retained event"
