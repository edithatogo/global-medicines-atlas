"""Tests for Prompt 36's final measured reconciliation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_final_source_coverage_reconciliation.py"
OUTPUT = (
    ROOT
    / "quality/qualifications/final-source-coverage-reconciliation-20260821.json"
)


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "final_reconciliation", SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checked_in_reconciliation_is_reproducible_and_fail_closed() -> None:
    expected = json.loads(OUTPUT.read_text(encoding="utf-8"))
    actual = _module().build_reconciliation()
    assert actual == expected
    assert actual["catalog_source_count"] == 174
    assert len(actual["jurisdiction_matrix"]) == 46
    assert actual["coverage_complete"] is False
    assert actual["missing_coverage_is_negative_evidence"] is False
    assert actual["fixture_or_metadata_counts_as_live"] is False
    assert actual["external_publication_performed"] is False


def test_all_requested_facets_and_accountable_boundaries_are_reported() -> None:
    reconciliation = json.loads(OUTPUT.read_text(encoding="utf-8"))
    facets = {row["facet"]: row for row in reconciliation["facet_matrix"]}
    assert set(facets) == {
        "regulatory_registration",
        "essential_or_formulary_status",
        "reimbursement_or_funding",
        "pricing_or_procurement",
        "pharmacovigilance",
        "recalls",
        "shortages",
        "clinical_trials",
        "utilisation",
        "terminology",
    }
    assert all(
        row["live_qualified"] <= row["fixture_qualified"] <= row["catalogued"]
        for row in facets.values()
    )
    assert (
        facets["pharmacovigilance"]["catalogued"]
        > facets["pharmacovigilance"]["live_qualified"]
    )
    assert facets["utilisation"]["catalogued"] == 10
    assert facets["clinical_trials"]["catalogued"] == 0
    assert reconciliation["high_value_gap_candidates"]
    assert reconciliation["new_track_recommendation"].startswith("Do not open")
