"""Contracts for the fail-closed source-rights disposition."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_source_rights_matrix import build

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "quality/qualifications/source-rights-disposition.json"


def test_every_catalogue_source_has_a_fail_closed_disposition() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    built = build()
    assert matrix == built
    assert matrix["source_count"] == 172
    assert len(matrix["entries"]) == 172
    assert {
        entry["recommended_disposition"] for entry in matrix["entries"]
    } == {"catalogue_only"}
    assert {entry["public_derived_release"] for entry in matrix["entries"]} == {
        "not_approved"
    }


def test_public_surfaces_are_not_approved_by_batch_policy() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert (
        matrix["public_derived_release"] == "source_specific_receipt_required"
    )
    assert all(
        entry["approved_surfaces"] == ["repository_metadata"]
        for entry in matrix["entries"]
    )
