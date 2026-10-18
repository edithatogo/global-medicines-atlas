"""Tests for the exact July 2025 MBS Silver projection lineage joins."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from scripts import reconcile_m112_july_mbs_silver_lineage as reconciliation

from global_medicines_atlas.mbs_silver_qualification import (
    MbsSilverQualification,
    report_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    reconciliation.BASE,
    reconciliation.FROZEN_INVENTORY,
    reconciliation.TREE_INVENTORY,
    reconciliation.SOURCE_LINEAGE,
    reconciliation.SOURCE_RECEIPT,
    reconciliation.MANIFEST,
    reconciliation.PUBLIC_QUALIFICATION,
    reconciliation.CANDIDATE_REPORT,
    reconciliation.PUBLIC_READBACK,
    reconciliation.SUPERSEDED_OUTPUT,
    Path("scripts/reconcile_m112_july_mbs_silver_lineage.py"),
)


def _fixture_root(tmp_path: Path) -> Path:
    for relative in INPUTS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, target)
    return tmp_path


def test_silver_lineage_changes_only_the_six_frozen_projection_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    monkeypatch.setattr(reconciliation, "ROOT", root)
    baseline = json.loads((root / reconciliation.BASE).read_text())
    frozen_membership = baseline["approved_path_membership_sha256"]

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
    assert len(qualification["outputs"]) == 6
    assert len(changed) == 6
    assert {row["path"] for row in changed} == {
        row["path"] for row in qualification["outputs"]
    }
    assert all(row["b1_b2_lineage"]["complete"] is True for row in changed)
    assert all(
        row["lineage_kind"] == "source_faithful_silver_projection"
        for row in changed
    )
    prior_by_path = {row["path"]: row for row in baseline["objects"]}
    assert all(
        row["rights"] == prior_by_path[row["path"]]["rights"] for row in changed
    )
    assert overlay["approved_path_membership_sha256"] == frozen_membership
    assert overlay["updated_gate_totals"]["approved_denominator"] == 1759
    assert overlay["updated_gate_totals"]["complete_raw_b1_b2_lineage"] == 22
    assert overlay["updated_gate_totals"]["complete_projection_lineage"] == 6
    assert (
        overlay["updated_gate_totals"]["complete_b1_b2_lineage_objects"] == 28
    )
    assert overlay["updated_gate_totals"]["preserved_deferrals"] == 1759
    assert overlay["updated_gate_totals"]["v4_admissions"] == 0
    assert overlay["updated_gate_totals"]["consumer_canaries"] == 0
    assert (
        qualification["scope_limits"]["rights_or_licensing_conclusion_added"]
        is False
    )
    assert (
        qualification["scope_limits"][
            "source_payload_bytes_requested_or_inspected"
        ]
        is False
    )


def test_silver_lineage_rejects_manifest_output_digest_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    monkeypatch.setattr(reconciliation, "ROOT", root)
    base_path = root / reconciliation.BASE
    base = json.loads(base_path.read_text())
    row = next(
        item
        for item in base["objects"]
        if item["path"].endswith("/benefits.parquet")
    )
    row["identity"]["sha256"] = "0" * 64
    base_path.write_text(json.dumps(base))

    with pytest.raises(
        ValueError, match="frozen output, transformation, or readback mismatch"
    ):
        reconciliation.main()

    assert not (root / reconciliation.OUTPUT).exists()


def test_silver_lineage_rejects_stale_current_tree_identity_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    monkeypatch.setattr(reconciliation, "ROOT", root)
    tree_path = root / reconciliation.TREE_INVENTORY
    tree = json.loads(tree_path.read_text())
    observation = next(
        row
        for row in tree["observations"]
        if row.get("dataset") == reconciliation.DATASET
        and row.get("path", "").endswith("/benefits.parquet")
    )
    observation["observed_lfs_sha256"] = "0" * 64
    # Leave the cached boolean true to prove direct identity fields are checked.
    tree_path.write_text(json.dumps(tree))

    with pytest.raises(
        ValueError, match="frozen output, transformation, or readback mismatch"
    ):
        reconciliation.main()

    assert not (root / reconciliation.OUTPUT).exists()


def test_silver_lineage_rejects_candidate_table_hash_not_in_bound_qualification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    monkeypatch.setattr(reconciliation, "ROOT", root)
    candidate_path = root / reconciliation.CANDIDATE_REPORT
    candidate = json.loads(candidate_path.read_text())
    qualification = MbsSilverQualification.model_validate(
        candidate["qualification"]
    )
    table = qualification.tables[0].model_copy(
        update={"lineage_sha256": "0" * 64}
    )
    altered = qualification.model_copy(
        update={
            "tables": (table, *qualification.tables[1:]),
            "qualification_sha256": "0" * 64,
        }
    )
    candidate["qualification"] = altered.model_dump(mode="json")
    candidate["qualification"]["qualification_sha256"] = report_digest(altered)
    candidate_path.write_text(json.dumps(candidate))

    with pytest.raises(ValueError, match="candidate table lineage differs"):
        reconciliation.main()

    assert not (root / reconciliation.OUTPUT).exists()
