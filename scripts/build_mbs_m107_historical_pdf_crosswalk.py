"""Build a metadata-only crosswalk of official MBS 2011-2019 PDF links."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX = (
    ROOT
    / "quality/qualifications/australian-mbs-official-index-reconciliation-20261017.json"
)
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
)
OUTPUT = (
    ROOT
    / "quality/qualifications/australian-mbs-m107-historical-pdf-crosswalk-20261018.json"
)

YEAR_PAGES = {f"Downloads-{year}-PDF" for year in range(2011, 2020)}
MONTHS = {
    name: f"{number:02d}"
    for number, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        1,
    )
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _period_comparison(label: str, filename: str) -> dict[str, Any]:
    label_match = re.search(
        r"\b(20\d{2})\s*(January|February|March|April|May|June|July|August|September|October|November|December)",
        label,
        flags=re.IGNORECASE,
    )
    file_match = re.match(r"(\d{6})", filename)
    if label_match is None or file_match is None:
        return {"status": "not_comparable_from_label_and_filename"}

    label_month = MONTHS[label_match.group(2).title()]
    label_token = f"{label_match.group(1)}{label_month}"
    filename_token = file_match.group(1)
    return {
        "status": (
            "different_tokens"
            if label_token != filename_token
            else "same_tokens"
        ),
        "displayed_label_token": label_token,
        "filename_token": filename_token,
    }


def _link_row(
    page: dict[str, Any],
    resource: dict[str, Any],
    url_occurrences: Counter[str],
    allowed_categories: list[str],
) -> dict[str, Any]:
    return {
        "page_id": page["page_id"],
        "displayed_label": resource["label"],
        "filename": resource["filename"],
        "source_url": resource["url"],
        "same_url_link_occurrence_count": url_occurrences[resource["url"]],
        "label_filename_period_comparison": _period_comparison(
            resource["label"], resource["filename"]
        ),
        "authorization": {
            "allowed_categories": allowed_categories,
            "historical_pdf_word_scope": "not established by this authorization",
            "category_match": False,
            "source_rights_decision": "not established for this link",
        },
        "source_payload_requested": False,
        "source_payload_read": False,
    }


def _page_metadata(
    pages: list[dict[str, Any]], allowed_categories: list[str]
) -> dict[str, Any]:
    all_resources = [
        (page, resource) for page in pages for resource in page["resources"]
    ]
    pdf_resources = [
        (page, resource)
        for page, resource in all_resources
        if resource["filename"].lower().endswith(".pdf")
    ]
    url_occurrences: Counter[str] = Counter(
        resource["url"] for _, resource in pdf_resources
    )
    rows = [
        _link_row(page, resource, url_occurrences, allowed_categories)
        for page, resource in pdf_resources
    ]
    by_year = {
        page["page_id"].split("-")[1]: {
            "pdf_link_occurrences": sum(
                resource["filename"].lower().endswith(".pdf")
                for resource in page["resources"]
            )
        }
        for page in pages
    }
    duplicate_url_entries = [
        {
            "source_url": url,
            "link_occurrence_count": count,
            "labels": [
                resource["label"]
                for _, resource in pdf_resources
                if resource["url"] == url
            ],
        }
        for url, count in sorted(url_occurrences.items())
        if count > 1
    ]
    comparison_counts = Counter(
        row["label_filename_period_comparison"]["status"] for row in rows
    )
    rss_resources = [
        resource
        for _, resource in all_resources
        if resource["filename"].lower().endswith(".xml")
        and resource["label"] == "RSS"
    ]
    distinct_urls = len(url_occurrences)
    summary = {
        "official_pages": len(pages),
        "pdf_link_occurrences": len(rows),
        "distinct_pdf_source_urls": distinct_urls,
        "duplicate_url_identity_count": len(duplicate_url_entries),
        "duplicate_link_occurrence_excess": len(rows) - distinct_urls,
        "rss_link_occurrences_excluded_from_pdf_files": len(rss_resources),
        "distinct_rss_source_urls": len({
            item["url"] for item in rss_resources
        }),
        "label_filename_period_comparison_counts": dict(
            sorted(comparison_counts.items())
        ),
        "source_payloads_requested": False,
        "source_payloads_read": False,
        "m107_accepted": False,
    }
    return {
        "links": rows,
        "per_year": by_year,
        "duplicate_url_identities": duplicate_url_entries,
        "scope": summary,
    }


def build_report() -> dict[str, Any]:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    pages = [
        page
        for page in index["downloads_index"]["pages"]
        if page["page_id"] in YEAR_PAGES
    ]
    if {page["page_id"] for page in pages} != YEAR_PAGES:
        raise ValueError("Expected all nine official 2011-2019 PDF pages")
    metadata = _page_metadata(pages, authorization["categories"])

    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.australian-mbs-m107-historical-pdf-crosswalk",
        "schema_version": 1,
        "recorded_at": "2026-10-18",
        "requirement": "M-107",
        "status": "official_page_metadata_crosswalk_rights_and_acceptance_open",
        "scope": metadata["scope"],
        "source_observation": {
            "path": INDEX.relative_to(ROOT).as_posix(),
            "recorded_at": index["recorded_at"],
            "sha256": _sha256(INDEX),
            "page_observation_window": index["downloads_index"][
                "observation_window_utc"
            ],
        },
        "authorization_input": {
            "path": AUTHORIZATION.relative_to(ROOT).as_posix(),
            "sha256": _sha256(AUTHORIZATION),
            "allowed_categories": authorization["categories"],
            "historical_pdf_word_scope": "not established by this authorization",
        },
        "per_year": metadata["per_year"],
        "duplicate_url_identities": metadata["duplicate_url_identities"],
        "interpretation": {
            "period_boundary": "Displayed labels and filename tokens are compared only as metadata; neither is accepted as a verified effective date.",
            "duplicate_boundary": "Repeated source URLs are counted as link appearances and distinct URL identities separately; different labels on one URL need source-owner clarification before treating them as different snapshots.",
            "rights_boundary": "The current MBS authorization covers listed source categories and does not establish historical PDF rights. No acquisition or publication is authorized by this crosswalk.",
            "completeness_boundary": "This is a nine-page index observation, not a complete historical MBS/PBS period denominator or M-107 acceptance.",
        },
        "links": metadata["links"],
    }
    report["digest"] = {"algorithm": "sha256-canonical-json"}
    report["digest"]["value"] = _canonical_digest(report)
    return report


if __name__ == "__main__":
    OUTPUT.write_text(
        json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
