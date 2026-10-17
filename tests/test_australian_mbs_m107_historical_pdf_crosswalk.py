"""Integrity and scope checks for the historical MBS PDF link crosswalk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_mbs_m107_historical_pdf_crosswalk import build_report
from scripts.build_mbs_m107_previous_downloads_crosswalk import (
    build_report as build_previous_downloads_report,
)

REPORT = Path(
    "quality/qualifications/australian-mbs-m107-historical-pdf-crosswalk-20261018.json"
)
DOCUMENTATION = Path("docs/qualification/australian-mbs-pbs-m107-snapshots.md")
PREVIOUS_REPORT = Path(
    "quality/qualifications/australian-mbs-m107-previous-downloads-crosswalk-20261018.json"
)


def _report() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _previous_report() -> dict[str, object]:
    return json.loads(PREVIOUS_REPORT.read_text(encoding="utf-8"))


def test_historical_pdf_crosswalk_digest_and_source_projection_are_stable() -> (
    None
):
    report = _report()
    digest = report["digest"]
    assert isinstance(digest, dict)
    expected_digest = digest.pop("value")
    canonical = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == expected_digest
    rebuilt = build_report()
    rebuilt_digest = rebuilt["digest"].pop("value")
    assert rebuilt_digest == expected_digest
    assert report == rebuilt


def test_historical_pdf_crosswalk_reconciles_occurrences_and_url_identities() -> (
    None
):
    report = _report()
    scope = report["scope"]
    assert isinstance(scope, dict)
    assert scope["official_pages"] == 9
    assert scope["pdf_link_occurrences"] == 119
    assert scope["distinct_pdf_source_urls"] == 113
    assert scope["duplicate_url_identity_count"] == 5
    assert scope["duplicate_link_occurrence_excess"] == 6
    assert scope["rss_link_occurrences_excluded_from_pdf_files"] == 18
    assert scope["distinct_rss_source_urls"] == 2
    assert scope["label_filename_period_comparison_counts"] == {
        "different_tokens": 8,
        "not_comparable_from_label_and_filename": 1,
        "same_tokens": 110,
    }

    links = report["links"]
    assert isinstance(links, list)
    assert len(links) == 119
    assert all(link["source_payload_requested"] is False for link in links)
    assert all(link["source_payload_read"] is False for link in links)
    assert all(
        link["authorization"]["category_match"] is False for link in links
    )
    assert all(
        link["authorization"]["source_rights_decision"]
        == "not established for this link"
        for link in links
    )


def test_historical_pdf_crosswalk_records_year_counts_and_preserves_limits() -> (
    None
):
    report = _report()
    assert report["per_year"] == {
        "2011": {"pdf_link_occurrences": 14},
        "2012": {"pdf_link_occurrences": 24},
        "2013": {"pdf_link_occurrences": 21},
        "2014": {"pdf_link_occurrences": 18},
        "2015": {"pdf_link_occurrences": 10},
        "2016": {"pdf_link_occurrences": 9},
        "2017": {"pdf_link_occurrences": 7},
        "2018": {"pdf_link_occurrences": 7},
        "2019": {"pdf_link_occurrences": 9},
    }
    duplicates = report["duplicate_url_identities"]
    assert isinstance(duplicates, list)
    assert len(duplicates) == 5
    assert any(
        duplicate["labels"]
        == [
            "2014 April Optometrist",
            "2014 March Optometrist",
            "2014 January Optometrist",
        ]
        for duplicate in duplicates
    )

    interpretation = report["interpretation"]
    assert isinstance(interpretation, dict)
    assert (
        "neither is accepted as a verified effective date"
        in interpretation["period_boundary"]
    )
    assert (
        "does not establish historical PDF rights"
        in interpretation["rights_boundary"]
    )
    assert report["scope"]["m107_accepted"] is False


def test_snapshot_documentation_uses_reconciled_historical_pdf_counts() -> None:
    documentation = " ".join(DOCUMENTATION.read_text(encoding="utf-8").split())
    assert (
        "**Total** | **119 link appearances; 113 distinct PDF URLs**"
        in documentation
    )
    assert "| 2012 | 24 |" in documentation
    assert "six duplicate link appearances across five URLs" in documentation


def test_previous_downloads_crosswalk_covers_1974_to_2010_metadata_only() -> (
    None
):
    report = _previous_report()
    digest = report["digest"]
    assert isinstance(digest, dict)
    expected_digest = digest.pop("value")
    canonical = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == expected_digest
    rebuilt = build_previous_downloads_report()
    assert rebuilt["digest"].pop("value") == expected_digest
    assert report == rebuilt

    scope = report["scope"]
    assert isinstance(scope, dict)
    assert scope["listed_pdf_files"] == 105
    assert scope["pdf_link_occurrences"] == 105
    assert scope["distinct_pdf_source_urls"] == 105
    assert scope["duplicate_url_identity_count"] == 0
    assert scope["duplicate_link_occurrence_excess"] == 0
    assert scope["listed_period_years"][0] == "1974"
    assert scope["listed_period_years"][-1] == "2010"
    assert scope["label_filename_period_comparison_counts"] == {
        "not_comparable_from_label_and_filename": 80,
        "same_tokens": 25,
    }

    links = report["links"]
    assert isinstance(links, list)
    assert len(links) == 105
    assert all(link["filename"].lower().endswith(".pdf") for link in links)
    assert all(link["source_payload_requested"] is False for link in links)
    assert all(link["source_payload_read"] is False for link in links)
    assert all(
        link["authorization"]["category_match"] is False for link in links
    )
    assert report["scope"]["m107_accepted"] is False


def test_previous_and_year_page_crosswalks_have_distinct_url_denominators() -> (
    None
):
    recent_links = _report()["links"]
    previous_links = _previous_report()["links"]
    assert isinstance(recent_links, list)
    assert isinstance(previous_links, list)
    recent_urls = {item["source_url"] for item in recent_links}
    previous_urls = {item["source_url"] for item in previous_links}
    assert len(recent_links) == 119
    assert len(recent_urls) == 113
    assert len(previous_links) == 105
    assert len(previous_urls) == 105
    assert recent_urls.isdisjoint(previous_urls)
    assert len(recent_urls | previous_urls) == 218
    assert len(recent_links) + len(previous_links) == 224


def test_documentation_records_previous_downloads_scope_and_rights_boundary() -> (
    None
):
    documentation = " ".join(DOCUMENTATION.read_text(encoding="utf-8").split())
    assert (
        "lists 105 PDF URLs on the separate Previous Downloads page, covering labels from 1974 through 2010"
        in documentation
    )
    assert "80 labels have no comparable month token" in documentation
    assert "does not establish historical PDF rights" in documentation
