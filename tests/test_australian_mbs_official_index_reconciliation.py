"""Pin the scope and observable counts of the 2026-10-17 MBS index review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION = (
    REPOSITORY_ROOT
    / "quality/qualifications/australian-mbs-official-index-reconciliation-20261017.json"
)


def _qualification() -> dict[str, Any]:
    value = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_official_mbs_index_counts_bind_to_exact_observation_scope() -> None:
    record = _qualification()
    downloads = record["downloads_index"]
    pages = downloads["pages"]

    assert record["schema_id"] == (
        "global-medicines-atlas.australian-mbs-official-index-reconciliation"
    )
    assert record["requirement"] == "M-107"
    assert record["status"] == "current_official_index_receipts_reconciled"
    assert downloads["http_status"] == 200
    assert downloads["page_count"] == 55
    assert downloads["resource_link_count"] == 531
    assert downloads["distinct_resource_url_count"] == 417
    assert len(pages) == downloads["page_count"]
    assert len({page["url"] for page in pages}) == len(pages)
    assert all(page["http_status"] == 200 for page in pages)
    assert sum(page["resource_count"] for page in pages) == 531


def test_current_mbs_xml_links_are_receipt_reconciled_without_accepting_m107() -> (
    None
):
    record = _qualification()
    inventory = record["monthly_schedule_xml_index_reconciliation"]
    resources = inventory["resources"]

    assert inventory["listed_xml_link_count"] == 82
    assert inventory["distinct_source_url_count"] == 82
    assert inventory["page_count"] == 41
    assert inventory["receipt_matched_count"] == 82
    assert inventory["no_matching_current_receipt_count"] == 0
    assert len(resources) == 82
    assert (
        sum(resource["current_archive_receipt"] for resource in resources) == 82
    )
    assert all(
        resource["filename"].lower().startswith("mbs-xml-")
        for resource in resources
    )
    assert record["current_public_archive"]["revision"] == (
        "da83cad9116e2f9a5b927be7b080e9a5e5ea6998"
    )
    assert record["current_public_archive"]["manifest_sha256"] == (
        "68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055"
    )
    refresh = record["archive_receipt_refresh"]
    assert refresh["monthly_schedule_receipt_metadata_read"] == 87
    assert refresh["read_errors"] == 0
    assert refresh["exact_source_url_matches"] == 82
    assert refresh["remaining_page_ids"] == []
    assert refresh["unmatched_urls"] == []
    assert refresh["targeted_page_run"]["run"] == "39000296702"
    assert refresh["targeted_page_run"]["identity_conflict_count"] == 0
    assert (
        refresh["targeted_page_run"]["anonymous_digest_verification"]
        == "passed"
    )
    assert (
        refresh["targeted_page_run"]["temporary_source_bytes_removed"] is True
    )
    assert refresh["m107_accepted"] is False
    assert record["previous_public_archive_observation"]["revision"] == (
        "52ad5c31cfe101c487a4c7a9c382540642e6110a"
    )
    assert record["limits"][
        "missing_current_receipt_is_not_failed_retrieval_or_negative_evidence"
    ]
    assert record["limits"][
        "source_period_or_release_date_not_inferred_from_page_id_suffix"
    ]
    assert (
        "not a complete expected MBS/PBS period denominator"
        in record["denominator_boundary"]
    )


def test_previous_downloads_formats_remain_outside_schedule_claims() -> None:
    record = _qualification()
    previous = record["previous_downloads"]

    assert previous["http_status"] == 200
    assert previous["listed_resource_link_count"] == 106
    assert previous["distinct_resource_url_count"] == 106
    assert previous["listed_file_count"] == 105
    assert previous["distinct_file_url_count"] == 105
    assert previous["file_extension_counts"] == {"pdf": 105}
    assert previous["rss_feed_link_count"] == 1
    assert previous["rss_feed_links"] == [
        {
            "classification": "site_wide_rss_feed_not_historical_mbs_download",
            "filename": "mbsonline.xml",
            "label": "RSS",
            "url": "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/AttachmentsByTitle/rss/$FILE/mbsonline.xml",
        }
    ]
    assert all(
        file["filename"].lower().endswith(".pdf") for file in previous["files"]
    )
    assert previous["listed_period_years"][0] == "1974"
    assert previous["listed_period_years"][-1] == "2010"
    assert record["authorization"]["historical_pdf_word_scope"] == (
        "not established by this authorization"
    )
    assert record["limits"][
        "historical_pdf_file_links_not_acquired_or_claimed_authorized"
    ]
    assert "No MBS/PBS source payload" in record["method"]
