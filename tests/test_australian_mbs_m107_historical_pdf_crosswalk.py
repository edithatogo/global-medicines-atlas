"""Integrity and scope checks for the historical MBS PDF link crosswalk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_mbs_m107_historical_pdf_crosswalk import build_report

REPORT = Path(
    "quality/qualifications/australian-mbs-m107-historical-pdf-crosswalk-20261018.json"
)
DOCUMENTATION = Path("docs/qualification/australian-mbs-pbs-m107-snapshots.md")


def _report() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


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
