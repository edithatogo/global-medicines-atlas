"""Integrity checks for the PBS official schedule-index observation."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

REPORT_PATH = Path(
    "quality/qualifications/australian-pbs-schedule-index-metadata-20261018.json"
)


def _load_report() -> dict[str, object]:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_pbs_schedule_index_observation_has_stable_digest_and_counts() -> None:
    report = _load_report()
    digest = report["digest"]
    assert isinstance(digest, dict)
    expected_digest = digest.pop("value")
    canonical = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == expected_digest

    pages = report["year_pages"]
    assert isinstance(pages, list)
    assert [page["year"] for page in pages] == list(range(2003, 2027))
    assert all(page["http_status"] == 200 for page in pages)

    links = [link for page in pages for link in page["schedule_data_links"]]
    assert len(links) == 316
    assert all(link["effective_date_from_page_heading"] for link in links)
    assert all(link["schema_version_inferred"] is False for link in links)
    assert all(link["source_file_requested"] is False for link in links)

    classifications = Counter(
        link["format_label_classification"] for link in links
    )
    assert classifications == {
        "xml_version_unspecified": 88,
        "xml_v3": 105,
        "xml_v2_down_converted": 105,
        "pbs_api_csv": 18,
    }

    summary = report["release_link_summary"]
    assert summary["total_schedule_data_link_count"] == len(links)
    assert summary["format_label_classification_counts"] == dict(
        classifications
    )
    assert summary["distinct_schedule_periods_with_data_links"] == 197


def test_pbs_schedule_index_observation_keeps_rights_and_acceptance_open() -> (
    None
):
    report = _load_report()
    authorization = report["authorization_and_qualification"]

    assert authorization["historical_xml_reuse_status"] == "unknown"
    assert authorization["current_api_retention_authorized"] is False
    assert (
        authorization["current_api_external_redistribution_authorized"] is False
    )
    assert authorization["source_payload_acquisition_performed"] is False
    assert authorization["source_semantics_qualified"] is False
    assert authorization["silver_admission_performed"] is False
    assert authorization["m109_accepted"] is False
    assert authorization["m107_accepted"] is False
    assert report["source_payloads_read"] is False
    assert report["source_rights_concluded"] is False

    documentation = report["official_documentation_review"]
    schema = documentation["xml_schema_history"]
    assert schema["reported_milestones"][0] == {
        "version": "1.1.1",
        "date": "2006-12",
    }
    assert (
        "not evidence of complete schedule release identities"
        in schema["boundary"]
    )
    api = documentation["public_api_information"]
    assert "most recent 12 months" in api["documented_schedule_window"]
    assert "does not establish" in api["boundary"]
