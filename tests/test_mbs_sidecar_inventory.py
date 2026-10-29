"""Frozen BSD/RVG candidates require exact identity and original metadata roles."""

import json
from pathlib import Path

import pytest

from global_medicines_atlas import mbs_sidecar_inventory as module
from global_medicines_atlas.mbs_sidecar_inventory import load_sidecars

ROOT = Path(__file__).resolve().parents[1]


def test_exact_frozen_sidecars_bind_all_five_original_roles():
    objects = load_sidecars(ROOT)
    assert len(objects) == 3
    assert {obj.format for obj in objects} == {"csv", "xml", "text"}
    for obj in objects:
        assert len(obj.metadata) == 5
        assert obj.revision == "42d73b6facac016f14a335d36d83f1a3b630add8"
        assert obj.byte_count > 0
        assert len(obj.sha256) == 64
        assert obj.source_path.startswith("raw/mbs/")
        assert {pin.role for pin in obj.metadata} == {
            "acquisition",
            "b2_reference",
            "source_receipt",
            "landed_admission",
            "path_receipt",
        }


def test_modified_retained_metadata_is_rejected(tmp_path):
    name, _ = module.INPUTS["lineage"]
    target = tmp_path / module.PREFIX / name
    target.parent.mkdir(parents=True)
    target.write_text("changed")
    with pytest.raises(ValueError, match="metadata digest"):
        load_sidecars(tmp_path)


@pytest.mark.parametrize("change", ["identity", "lineage", "role", "admission"])
def test_binding_does_not_accept_incomplete_or_mismatched_roles(
    monkeypatch, change
):
    reports = {
        key: json.loads((ROOT / module.PREFIX / name).read_bytes())
        for key, (name, _) in module.INPUTS.items()
    }
    candidate = next(
        row
        for row in reports["identity"]["authorized_objects"]
        if "/bsd/" in row["path"]
    )
    lineage = next(
        row
        for row in reports["lineage"]["objects"]
        if row["path"] == candidate["path"] and row["dataset"] == module.DATASET
    )
    acquisition = lineage["b1_b2_lineage"]["acquisition_id"]
    if change == "identity":
        candidate["byte_count"] += 1
    elif change == "lineage":
        lineage["b1_b2_lineage"]["complete"] = False
    elif change == "role":
        lineage["b1_b2_lineage"]["receipt_roles"]["acquisition"] = False
    else:
        reports["metadata"]["readbacks"] = [
            row
            for row in reports["metadata"]["readbacks"]
            if not row["path"].startswith(
                f"bronze/admissions/au-mbs/{acquisition}/"
            )
        ]
    monkeypatch.setattr(module, "_bound", lambda _, key: reports[key])
    with pytest.raises(ValueError, match="MBS sidecar"):
        load_sidecars(ROOT)
