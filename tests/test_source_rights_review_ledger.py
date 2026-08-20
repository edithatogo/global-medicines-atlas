"""Generated ledger coverage and fail-closed FDA review contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.build_source_rights_reviews import build

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "quality/qualifications/source-rights-review-ledger.json"


def _ledger() -> dict[str, Any]:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _entries() -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", _ledger()["entries"])


def test_ledger_is_deterministic_and_covers_all_sources() -> None:
    ledger = _ledger()
    assert ledger == build()
    assert ledger["catalogue_source_count"] == 172
    assert ledger["review_count"] == 172
    entries = _entries()
    assert len({entry["source_id"] for entry in entries}) == 172


def test_fda_sources_are_approved_with_explicit_exclusions() -> None:
    entries = {entry["source_id"]: entry for entry in _entries()}
    candidates = {
        source_id
        for source_id, entry in entries.items()
        if entry["policy_family_id"]
        in {"fda-website-public-domain", "openfda-cc0"}
    }
    expected = {
        "us-drugsfda",
        "us-fda-drug-shortages",
        "us-fda-faers",
        "us-fda-ndc-directory",
        "us-fda-nsde",
        "us-fda-orange-book",
        "us-fda-recalls-notices",
        "us-fda-rems",
        "us-openfda-drugsfda",
        "us-openfda-enforcement",
        "us-openfda-faers",
        "us-openfda-ndc",
        "us-openfda-nsde",
    }
    assert candidates == expected
    assert _ledger()["publication_gate"] == (
        "maintainer_authorized_fda_publication_20260821"
    )
    for source_id in expected:
        entry = entries[source_id]
        assert entry["maintainer_licence_approved"] is True
        assert entry["maintainer_publication_approved"] is True
        assert entry["public_source_eligible"] is True
        assert entry["disposition"] == "approved_public_source"
        assert entry["evidence"]
        assert entry["blocker"] is None
        exclusions = " ".join(entry["field_exclusions"]).casefold()
        assert "third-party" in exclusions
        assert "claim" in exclusions


def test_unreviewed_international_sources_remain_explicitly_fail_closed() -> (
    None
):
    entries = _entries()
    unresolved = [
        entry for entry in entries if entry["disposition"] == "catalogue_only"
    ]
    assert len(unresolved) == 159
    assert all(entry["blocker"] for entry in unresolved)
    assert all(entry["public_source_eligible"] is False for entry in unresolved)
