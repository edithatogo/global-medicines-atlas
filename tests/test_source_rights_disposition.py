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
    assert matrix["source_count"] == 174
    assert len(matrix["entries"]) == 174
    dispositions = {
        entry["recommended_disposition"] for entry in matrix["entries"]
    }
    assert dispositions == {
        "approved_public_source",
        "catalogue_only",
        "credentialed_excluded",
    }
    approved = [
        entry
        for entry in matrix["entries"]
        if entry["public_derived_release"] == "approved_for_exact_manifest"
    ]
    assert len(approved) == 2


def test_public_surfaces_require_source_specific_ledger_approval() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert matrix["public_derived_release"] == "exact_approved_manifests_only"
    entries = {entry["source_id"]: entry for entry in matrix["entries"]}
    for source_id in ("au-mbs", "au-mbs-p7-legacy-workbook"):
        assert entries[source_id]["approved_surfaces"] == [
            "repository_metadata",
            "source_bytes",
            "derived_products",
        ]
        assert entries[source_id]["required_evidence"] == []
        assert entries[source_id]["blocker"] is None
