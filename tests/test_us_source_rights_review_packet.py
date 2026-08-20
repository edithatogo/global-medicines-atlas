"""Fail-closed contracts for the bounded U.S. rights-review packet."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.build_us_source_rights_review_packet import build

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "quality/qualifications/us-source-rights-review-packet.json"
CATALOG = ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"


def _packet() -> dict[str, Any]:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_packet_is_generated_and_covers_the_us_catalogue_exactly() -> None:
    packet = _packet()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    expected = {
        source["source_id"]
        for source in catalog["sources"]
        if source["source_id"].startswith("us-")
    }
    assert packet == build()
    entries = packet["entries"]
    assert packet["source_count"] == len(expected) == 20
    assert {entry["source_id"] for entry in entries} == expected
    assert len(entries) == len(expected)


def test_packet_authorizes_fda_and_keeps_non_fda_fail_closed() -> None:
    packet = _packet()
    assert packet["licensing_decision"] == "fda_approved_non_fda_pending"
    assert packet["live_acquisition"] == "authorized_for_fda_sources"
    assert packet["public_release"] == "approved_for_fda_sources"
    for entry in packet["entries"]:
        unresolved = entry["source_id"] in {
            "us-cms-mdrp",
            "us-cms-nadac",
            "us-cms-partd-formulary",
            "us-cms-partd-spending",
            "us-dailymed-spl",
            "us-gsrs-unii",
            "us-rxnorm-api",
        }
        assert entry["maintainer_licence_approved"] is (not unresolved)
        assert entry["maintainer_publication_approved"] is (not unresolved)
        assert entry["public_release"] == (
            "not_approved" if unresolved else "approved"
        )


def test_terms_evidence_uses_only_official_authority_domains() -> None:
    allowed = {
        "cms.gov",
        "data.cms.gov",
        "fda.gov",
        "nih.gov",
        "open.fda.gov",
        "nlm.nih.gov",
    }
    for entry in _packet()["entries"]:
        assert entry["terms_evidence"]
        for evidence in entry["terms_evidence"]:
            host = urlparse(str(evidence["url"])).hostname
            assert host is not None
            assert any(
                host == domain or host.endswith(f".{domain}")
                for domain in allowed
            )
            assert evidence["observed_at"] == "2026-08-20"


def test_openfda_candidates_exclude_third_party_content() -> None:
    entries = {entry["source_id"]: entry for entry in _packet()["entries"]}
    openfda = [
        entry
        for source_id, entry in entries.items()
        if source_id.startswith("us-openfda-")
    ]
    assert len(openfda) == 5
    for entry in openfda:
        assert (
            entry["candidate_disposition"]
            == "approved_public_source_scoped_cc0"
        )
        exclusions = " ".join(entry["field_exclusions"]).casefold()
        assert "third-party" in exclusions
        assert "gmdn" in exclusions
        assert (
            entry["raw_payload_redistribution"]
            == "approved_subject_to_field_exclusions"
        )


def test_cms_and_terminology_sources_remain_evidence_gaps() -> None:
    entries = {entry["source_id"]: entry for entry in _packet()["entries"]}
    unresolved = {
        "us-cms-mdrp",
        "us-cms-nadac",
        "us-cms-partd-formulary",
        "us-cms-partd-spending",
        "us-dailymed-spl",
        "us-gsrs-unii",
        "us-rxnorm-api",
    }
    assert {
        source_id
        for source_id, entry in entries.items()
        if entry["candidate_disposition"] == "terms_gap_catalogue_only"
    } == unresolved
    assert all(
        entries[source_id]["retain_source_bytes"] == "unknown"
        for source_id in unresolved
    )
