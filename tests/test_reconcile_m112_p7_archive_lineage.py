"""Regression coverage for metadata-only P7 archive-boundary lineage."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from scripts import reconcile_m112_p7_archive_lineage as reconciliation

from global_medicines_atlas.bronze_admission import BronzeAdmissionRecord
from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest
from global_medicines_atlas.receipts import AcquisitionEvent, SourceReceipt

if TYPE_CHECKING:
    import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    reconciliation.BASE,
    reconciliation.P7_STORAGE,
    reconciliation.PUBLIC_ARCHIVE,
    Path("quality/qualifications/mbs-workbook-storage-20260830.json"),
    Path("scripts/reconcile_m112_p7_archive_lineage.py"),
    Path("src/global_medicines_atlas/mbs_p7_receipt_reconciliation.py"),
)


def _fixture_root(tmp_path: Path) -> Path:
    for relative in INPUTS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, target)
    return tmp_path


def test_p7_archive_lineage_updates_only_the_frozen_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    monkeypatch.setattr(reconciliation, "ROOT", root)
    baseline = json.loads((root / reconciliation.BASE).read_text())
    membership = baseline["approved_path_membership_sha256"]

    reconciliation.main()

    qualification = json.loads((root / reconciliation.OUTPUT).read_text())
    overlay = json.loads((root / reconciliation.OVERLAY_OUTPUT).read_text())
    assert qualification["archive_retrieval"]["streamed_sha256"] == (
        reconciliation.SOURCE_SHA256
    )
    assert qualification["archive_retrieval"]["streamed_byte_count"] == (
        reconciliation.SOURCE_BYTES
    )
    assert (
        qualification["implementation"]["sha256"]
        == hashlib.sha256(
            (root / qualification["implementation"]["path"]).read_bytes()
        ).hexdigest()
    )
    assert (
        qualification["scope_limits"]["source_origin_acquisition_evidenced"]
        is False
    )
    assert (
        qualification["scope_limits"]["rights_or_licensing_conclusion_added"]
        is False
    )
    assert len(overlay["objects"]) == len(baseline["objects"]) == 1759
    assert overlay["approved_path_membership_sha256"] == membership
    changed = [
        current
        for prior, current in zip(
            baseline["objects"], overlay["objects"], strict=True
        )
        if prior != current
    ]
    assert len(changed) == 1
    assert changed[0]["path"] == reconciliation.ARCHIVE_MEMBER_PATH
    assert overlay["updated_gate_totals"]["complete_raw_b1_b2_lineage"] == 21
    assert overlay["updated_gate_totals"]["v4_admissions"] == 0
    assert overlay["updated_gate_totals"]["consumer_canaries"] == 0
    assert overlay["updated_gate_totals"]["preserved_deferrals"] == 1759
    p7 = next(
        row
        for row in overlay["objects"]
        if row["path"] == reconciliation.ARCHIVE_MEMBER_PATH
    )
    assert p7["b1_b2_lineage"]["complete"] is True
    assert p7["revision"] == p7["b1_b2_lineage"]["source_revision"]
    assert p7["b1_b2_lineage"]["archive_revision"] == (
        reconciliation.ARCHIVE_REVISION
    )
    assert p7["b1_b2_lineage"]["admission_state"] == "landed"
    assert p7["b1_b2_lineage"]["reviewer_status"] == "unreviewed"


def test_p7_archive_lineage_outputs_are_bound_and_reproducible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    monkeypatch.setattr(reconciliation, "ROOT", root)

    reconciliation.main()
    first = (root / reconciliation.OUTPUT).read_bytes()
    qualification = json.loads(first)
    for relative, expected in qualification["output_bindings"].items():
        assert (
            hashlib.sha256((root / relative).read_bytes()).hexdigest()
            == expected
        )
    SourceReceipt.model_validate_json(
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
    assert b2.rows[0].acquisition_id == event.acquisition_id
    assert admission.acquisition_id == event.acquisition_id
    assert b2.rows[0].external_reference == reconciliation.ARCHIVE_URI

    reconciliation.main()
    assert (root / reconciliation.OUTPUT).read_bytes() == first
    assert (root / reconciliation.OVERLAY_OUTPUT).exists()


def test_historical_p7_receipt_remains_exact_and_archive_scoped() -> None:
    receipt = reconciliation.reconstruct_p7_storage_source_receipt(REPO_ROOT)
    storage = json.loads((REPO_ROOT / reconciliation.P7_STORAGE).read_text())
    assert receipt.digest() == storage["recorded_receipt_sha256"]
    assert str(receipt.retrieval.uri) == reconciliation.ARCHIVE_URI
