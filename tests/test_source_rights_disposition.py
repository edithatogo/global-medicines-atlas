"""Contracts for the fail-closed source-rights disposition."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_source_rights_matrix import build

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "quality/qualifications/source-rights-disposition.json"


def test_every_catalogue_source_has_a_review_backed_disposition() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    built = build()
    assert matrix == built
    assert matrix["source_count"] == 172
    assert len(matrix["entries"]) == 172
    assert matrix["public_source_approved_count"] == 13
    assert {
        entry["recommended_disposition"] for entry in matrix["entries"]
    } == {"approved_public_source", "catalogue_only"}
    assert {entry["public_derived_release"] for entry in matrix["entries"]} == {
        "approved",
        "not_approved",
    }


def test_public_surfaces_are_limited_to_review_approved_sources() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert (
        matrix["public_derived_release"] == "approved_sources_only"
    )
    for entry in matrix["entries"]:
        if entry["public_source_eligible"]:
            assert "hugging_face_public_dataset" in entry["approved_surfaces"]
            assert entry["blocker"] is None
        else:
            assert entry["approved_surfaces"] == ["repository_metadata"]
            assert entry["blocker"]
