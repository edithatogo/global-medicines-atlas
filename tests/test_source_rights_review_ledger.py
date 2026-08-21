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


def test_fda_sources_have_candidate_evidence_but_no_blanket_approval() -> None:
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
        "pending_exact_manifest_maintainer_approval"
    )
    for source_id in expected:
        entry = entries[source_id]
        assert entry["maintainer_licence_approved"] is False
        assert entry["maintainer_publication_approved"] is False
        assert entry["public_source_eligible"] is False
        assert entry["disposition"] == "catalogue_only"
        assert entry["evidence"]
        assert "pending" in entry["blocker"]
        exclusions = " ".join(entry["field_exclusions"]).casefold()
        assert "third-party" in exclusions
        assert "claim" in exclusions


def test_unreviewed_international_sources_remain_explicitly_fail_closed() -> (
    None
):
    entries = _entries()
    non_public = [
        entry
        for entry in entries
        if entry["disposition"] in {"catalogue_only", "credentialed_excluded"}
    ]
    assert len(non_public) == 172
    assert all(entry["blocker"] for entry in non_public)
    assert all(entry["public_source_eligible"] is False for entry in non_public)


def test_permissive_international_candidates_have_official_evidence() -> None:
    entries = {entry["source_id"]: entry for entry in _entries()}
    expected = {
        "eu-union-register",
        "fr-bdpm",
        "fr-bdpm-smr-asmr",
        "fr-open-medic",
        "gb-emit",
        "gb-nhs-drug-tariff",
        "gb-nice-medicines-utilisation",
        "global-rxnorm",
        "nl-gipdatabank",
        "nz-pharmac-hml",
        "nz-pharmac-schedule",
        "nz-pharmac-schedule-xml",
        "us-rxnorm-api",
    }
    candidates = {
        source_id
        for source_id, entry in entries.items()
        if entry["policy_family_id"]
        not in {
            "unresolved-source-specific-terms",
            "fda-website-public-domain",
            "openfda-cc0",
        }
    }
    assert candidates == expected
    assert _ledger()["candidate_policy_assignment_count"] == 26
    for source_id in expected:
        entry = entries[source_id]
        assert entry["evidence"]
        assert all(item["content_sha256"] for item in entry["evidence"])
        assert entry["disposition"] == "catalogue_only"
        assert entry["maintainer_publication_approved"] is False


def test_every_international_review_has_observation_or_failure_receipt() -> (
    None
):
    entries = _entries()
    assert sum(bool(entry["evidence"]) for entry in entries) == 154
    unavailable = [entry for entry in entries if not entry["evidence"]]
    assert len(unavailable) == 18
    assert all(
        "outcome" in entry["blocker"] or "access is" in entry["blocker"]
        for entry in unavailable
    )


def test_credentialed_sources_are_excluded_independently_of_rights() -> None:
    entries = _entries()
    credentialed = [
        entry
        for entry in entries
        if entry["disposition"] == "credentialed_excluded"
    ]
    assert len(credentialed) == 17
    assert all("access is" in entry["blocker"] for entry in credentialed)
