"""Contracts for the fail-closed source-rights disposition."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_source_rights_matrix import build

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "quality/qualifications/source-rights-disposition.json"
SOURCE_DECISIONS = (
    ROOT / "src/global_medicines_atlas/data/source_rights_source_decisions.json"
)


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
        "approved_public_derived_only",
        "catalogue_only",
        "credentialed_excluded",
    }
    approved = [
        entry
        for entry in matrix["entries"]
        if entry["public_derived_release"] == "approved_for_exact_manifest"
    ]
    decisions = json.loads(SOURCE_DECISIONS.read_text(encoding="utf-8"))
    exact_approved = {
        source_id
        for manifest in decisions["approved_publication_manifests"]
        for source_id in manifest["source_ids"]
    }
    assert {entry["source_id"] for entry in approved} == exact_approved


def test_public_surfaces_require_source_specific_ledger_approval() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert matrix["public_derived_release"] == "exact_approved_manifests_only"
    entries = {entry["source_id"]: entry for entry in matrix["entries"]}
    decisions = json.loads(SOURCE_DECISIONS.read_text(encoding="utf-8"))
    derived_only = {
        source_id
        for manifest in decisions["approved_publication_manifests"]
        for source_id in manifest["derived_only_source_ids"]
    }
    approved_ids = {
        source_id
        for manifest in decisions["approved_publication_manifests"]
        for source_id in manifest["source_ids"]
    }
    assert len(approved_ids) == 28
    for source_id in approved_ids - derived_only:
        entry = entries[source_id]
        assert entry["recommended_disposition"] == "approved_public_source"
        assert entry["public_derived_release"] == (
            "approved_for_exact_manifest"
        )
        assert entry["approved_surfaces"] == [
            "repository_metadata",
            "source_bytes",
            "derived_products",
        ]
        assert entry["required_evidence"] == []
        assert entry["blocker"] is None
    for source_id in derived_only:
        entry = entries[source_id]
        assert entry["recommended_disposition"] == (
            "approved_public_derived_only"
        )
        assert entry["public_derived_release"] == (
            "approved_for_exact_manifest"
        )
        assert entry["approved_surfaces"] == [
            "repository_metadata",
            "derived_products",
        ]
        assert "source_bytes" not in entry["approved_surfaces"]
        assert entry["required_evidence"] == []
        assert entry["blocker"] is None
