#!/usr/bin/env python3
"""Reconcile current MBS XML receipts to official release-page metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parents[1]
INDEX = (
    ROOT
    / "quality/qualifications/australian-mbs-official-index-reconciliation-20261017.json"
)
OUTPUT = (
    ROOT
    / "quality/qualifications/australian-mbs-current-release-page-chronology-20261018.json"
)
MAX_PAGE_BYTES = 2_000_000
MAX_WORKERS = 4
HTTP_OK = 200
USER_AGENT = "global-medicines-atlas-metadata-audit/1.0"
DATASET = "edithatogo/australian-mbs-source-archive"
HF_DATASET_API = f"https://huggingface.co/api/datasets/{DATASET}"
HF_DATASET_ROOT = f"https://huggingface.co/datasets/{DATASET}"
DATE_VALUE = re.compile(
    r"(?i)\b(?P<date>\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+"
    r"(?:\s+\d{4})?|[A-Za-z]+\s+\d{1,2},?\s+\d{4}|"
    r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b"
)
DATE_CUE = re.compile(
    r"(?i)(?P<cue>(?:file\s+)?(?:released|updated)\s+on|"
    r"effective\s+(?:from|on)|commenced\s+on)\s*$"
)
PAGE_UPDATED = re.compile(
    r"(?i)\bpage\s+last\s+updated\s*:\s*"
    r"(?P<date>\d{1,2}\s+[A-Za-z]+\s+\d{4})"
)
ALLOWED_HOSTS = {"www.mbsonline.gov.au", "mbsonline.gov.au"}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return _sha256(canonical)


def extract_date_mentions(text: str) -> list[dict[str, str]]:
    """Extract date text and nearby explicit cues without assigning meaning."""
    mentions: list[dict[str, str]] = []
    for match in DATE_VALUE.finditer(text):
        prefix = text[max(0, match.start() - 60) : match.start()]
        cue_match = DATE_CUE.search(prefix)
        mentions.append({
            "cue": cue_match.group("cue") if cue_match else "unclassified",
            "date_text": match.group("date"),
        })
    return mentions


def _page_updated_date(text: str) -> str | None:
    match = PAGE_UPDATED.search(text)
    return match.group("date") if match else None


def match_official_rows(
    page_html: bytes, page_url: str, expected_urls: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Find exact official XML URLs and their table-row metadata in HTML."""
    soup = BeautifulSoup(page_html, "html.parser")
    matches: dict[str, list[dict[str, Any]]] = {
        expected_url: [] for expected_url in expected_urls
    }
    expected = set(expected_urls)
    for anchor in soup.find_all("a", href=True):
        href = cast("str", anchor.get("href"))
        resolved = urljoin(page_url, href)
        if resolved not in expected:
            continue
        row = anchor.find_parent("tr")
        if not isinstance(row, Tag):
            continue
        row_text = row.get_text(" ", strip=True)
        matches[resolved].append({
            "link_label": anchor.get_text(" ", strip=True),
            "row_sha256": _sha256(row_text.encode()),
            "date_mentions": extract_date_mentions(row_text),
        })
    return matches


def _read_page(
    page: dict[str, Any], expected_urls: list[str]
) -> dict[str, Any]:
    """Read one official HTML page in memory and discard its body."""
    requested_url = cast("str", page["url"])
    started = datetime.now(UTC)
    try:
        response = httpx.get(
            requested_url,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        completed = datetime.now(UTC)
    except httpx.HTTPError as exc:
        completed = datetime.now(UTC)
        return {
            "page_id": page["page_id"],
            "requested_url": requested_url,
            "status": "unavailable",
            "failure_class": type(exc).__name__,
            "client_request_started_at": started.isoformat(),
            "client_response_received_at": completed.isoformat(),
            "resources": [],
        }

    body = response.content
    final_url = str(response.url)
    host = urlparse(final_url).hostname
    content_type = response.headers.get("content-type", "")
    page_receipt: dict[str, Any] = {
        "requested_url": requested_url,
        "final_url": final_url,
        "http_status": response.status_code,
        "content_type": content_type,
        "observed_bytes": len(body),
        "sha256": _sha256(body),
        "server_date": response.headers.get("date"),
        "last_modified": response.headers.get("last-modified"),
        "client_request_started_at": started.isoformat(),
        "client_response_received_at": completed.isoformat(),
        "body_retained": False,
    }
    page_metadata: dict[str, Any] = {
        "page_id": page["page_id"],
        "page_label": page["label"],
        "page_url": requested_url,
        "page_receipt": page_receipt,
        "resources": [],
    }
    if (
        response.status_code != HTTP_OK
        or len(body) > MAX_PAGE_BYTES
        or not content_type.lower().startswith("text/html")
        or host not in ALLOWED_HOSTS
    ):
        page_metadata["status"] = "invalid_page_response"
        page_metadata["failure_class"] = "status_size_content_type_or_host"
        return page_metadata

    soup = BeautifulSoup(body, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    heading = soup.find("h1")
    page_metadata["official_heading"] = (
        heading.get_text(" ", strip=True) if isinstance(heading, Tag) else None
    )
    page_metadata["page_last_updated_text"] = _page_updated_date(page_text)
    by_url = match_official_rows(body, final_url, expected_urls)
    page_metadata["status"] = "observed"
    for resource in page["resources"]:
        source_url = cast("str", resource["source_url"])
        page_metadata["resources"].append({
            "source_url": source_url,
            "filename": resource["filename"],
            "archive_receipts": [
                {
                    "receipt_path": receipt.get("receipt_path"),
                    "archive_path": receipt.get("archive_path"),
                    "payload_sha256": receipt.get("payload_sha256"),
                }
                for receipt in resource["matching_archive_receipts"]
            ],
            "matching_official_rows": by_url.get(source_url, []),
        })
    return page_metadata


def _read_json_metadata(url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read one bounded public JSON metadata object without saving its bytes."""
    started = datetime.now(UTC)
    response = httpx.get(
        url,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    completed = datetime.now(UTC)
    body = response.content
    if (
        response.status_code != HTTP_OK
        or len(body) > MAX_PAGE_BYTES
        or urlparse(str(response.url)).hostname != "huggingface.co"
    ):
        raise ValueError("public_metadata_response_invalid")
    loaded: object = json.loads(body)
    if not isinstance(loaded, dict):
        raise TypeError("public_metadata_document_not_object")
    document = cast("dict[str, Any]", loaded)
    return document, {
        "requested_url": url,
        "final_url": str(response.url),
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "observed_bytes": len(body),
        "sha256": _sha256(body),
        "server_date": response.headers.get("date"),
        "client_request_started_at": started.isoformat(),
        "client_response_received_at": completed.isoformat(),
        "body_retained": False,
    }


def read_current_archive_receipts(
    index: dict[str, Any],
) -> dict[str, Any]:
    """Return current receipt evidence or a bounded incomplete observation."""
    expected_count = len(index["current_public_archive"]["receipts"])
    try:
        return _read_current_archive_receipts_unchecked(index)
    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ) as exc:
        return {
            "dataset": DATASET,
            "status": "unavailable_or_invalid",
            "failure_class": type(exc).__name__,
            "anonymous": True,
            "receipt_sidecars_expected": expected_count,
            "receipt_sidecars_verified": 0,
            "receipt_sidecars_unresolved": expected_count,
            "receipt_sidecars": [],
        }


def _read_current_archive_receipts_unchecked(
    index: dict[str, Any],
) -> dict[str, Any]:
    """Read archive metadata; let the caller preserve overall failures."""
    dataset, dataset_receipt = _read_json_metadata(HF_DATASET_API)
    revision = cast("str", dataset.get("sha"))
    if (
        not re.fullmatch(r"[0-9a-f]{40}", revision)
        or dataset.get("private") is not False
        or dataset.get("gated") not in {False, None}
    ):
        raise ValueError("public_dataset_identity_invalid")

    manifest_url = f"{HF_DATASET_ROOT}/resolve/{revision}/manifest.json"
    manifest, manifest_receipt = _read_json_metadata(manifest_url)
    files = cast("list[dict[str, Any]]", manifest.get("files", []))
    manifest_paths = {
        cast("str", entry["path"])
        for entry in files
        if isinstance(entry.get("path"), str)
    }
    if manifest.get("file_count") != len(manifest_paths):
        raise ValueError("public_manifest_file_count_mismatch")

    expected_receipts = {
        cast("str", row["receipt_path"]): row
        for row in index["current_public_archive"]["receipts"]
    }
    if not expected_receipts:
        raise ValueError("index_has_no_receipt_metadata")

    verified: list[dict[str, Any]] = []
    for receipt_path, expected in sorted(expected_receipts.items()):
        receipt_url = f"{HF_DATASET_ROOT}/resolve/{revision}/{receipt_path}"
        record: dict[str, Any] = {
            "receipt_path": receipt_path,
            "status": "not_verified",
        }
        if receipt_path not in manifest_paths:
            record["status"] = "not_in_current_manifest"
            verified.append(record)
            continue
        try:
            sidecar, receipt = _read_json_metadata(receipt_url)
        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as exc:
            record["status"] = "readback_failed"
            record["failure_class"] = type(exc).__name__
            verified.append(record)
            continue

        exact_match = (
            receipt["sha256"] == expected["receipt_sha256"]
            and receipt["observed_bytes"] == expected["receipt_bytes"]
            and sidecar.get("schema_id")
            == "global-medicines-atlas.australian-harvest-receipt"
            and sidecar.get("source_url") == expected["source_url"]
            and sidecar.get("archive_path") == expected["archive_path"]
            and sidecar.get("sha256") == expected["payload_sha256"]
        )
        record.update({
            "status": "exact_current_receipt"
            if exact_match
            else "identity_mismatch",
            "receipt": receipt,
            "source_url": sidecar.get("source_url"),
            "archive_path": sidecar.get("archive_path"),
            "payload_sha256": sidecar.get("sha256"),
        })
        verified.append(record)

    return {
        "dataset": DATASET,
        "status": "exact_current_revision_receipts_verified"
        if all(row["status"] == "exact_current_receipt" for row in verified)
        else "current_revision_receipts_incomplete",
        "revision": revision,
        "private": dataset.get("private"),
        "gated": dataset.get("gated"),
        "anonymous": True,
        "dataset_api_receipt": dataset_receipt,
        "manifest": {
            "path": "manifest.json",
            "file_count": manifest["file_count"],
            "sha256": manifest_receipt["sha256"],
            "observed_bytes": manifest_receipt["observed_bytes"],
            "receipt": manifest_receipt,
        },
        "receipt_sidecars_expected": len(expected_receipts),
        "receipt_sidecars_verified": sum(
            row["status"] == "exact_current_receipt" for row in verified
        ),
        "receipt_sidecars_unresolved": sum(
            row["status"] != "exact_current_receipt" for row in verified
        ),
        "receipt_sidecars": verified,
    }


def _page_inputs(
    index: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    """Group indexed XML links by their exact official release page."""
    pages_by_id: dict[str, dict[str, Any]] = {}
    expected_urls_by_page: dict[str, list[str]] = defaultdict(list)
    for resource in index["monthly_schedule_xml_index_reconciliation"][
        "resources"
    ]:
        page_id = resource["page_id"]
        expected_urls_by_page[page_id].append(resource["source_url"])

    for page in index["downloads_index"]["pages"]:
        page_id = page["page_id"]
        if page_id not in expected_urls_by_page:
            continue
        xml_resources = [
            resource
            for resource in index["monthly_schedule_xml_index_reconciliation"][
                "resources"
            ]
            if resource["page_id"] == page_id
        ]
        pages_by_id[page_id] = {
            "page_id": page_id,
            "url": page["url"],
            "label": page["label"],
            "resources": xml_resources,
        }

    if set(pages_by_id) != set(expected_urls_by_page):
        raise ValueError("index page inventory does not bind every XML link")
    return pages_by_id, expected_urls_by_page


def _observe_pages(
    pages_by_id: dict[str, dict[str, Any]],
    expected_urls_by_page: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Fetch the bounded page set and discard response bodies after hashing."""
    ordered_pages = [pages_by_id[key] for key in sorted(pages_by_id)]

    def observe(page: dict[str, Any]) -> dict[str, Any]:
        page_id = cast("str", page["page_id"])
        return _read_page(page, expected_urls_by_page[page_id])

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        return list(executor.map(observe, ordered_pages))


def _bind_current_receipts(
    resources: list[dict[str, Any]], archive_readback: dict[str, Any]
) -> None:
    """Attach verified current-revision receipt identity to each exact URL."""
    verified = {
        record["receipt_path"]: record
        for record in archive_readback["receipt_sidecars"]
        if record["status"] == "exact_current_receipt"
    }
    for resource in resources:
        for receipt in resource["archive_receipts"]:
            current = verified.get(receipt["receipt_path"])
            if current is not None:
                receipt.update({
                    "current_revision": archive_readback["revision"],
                    "current_receipt_sha256": current["receipt"]["sha256"],
                    "current_payload_sha256": current["payload_sha256"],
                })


def build_report() -> dict[str, Any]:
    """Fetch current official pages and bind their XML link rows to receipts."""
    index_bytes = INDEX.read_bytes()
    index = json.loads(index_bytes)
    archive_readback = read_current_archive_receipts(index)
    pages_by_id, expected_urls_by_page = _page_inputs(index)
    pages = _observe_pages(pages_by_id, expected_urls_by_page)
    resources = [resource for page in pages for resource in page["resources"]]
    _bind_current_receipts(resources, archive_readback)
    unresolved = sum(
        len(resource["matching_official_rows"]) != 1 for resource in resources
    )
    page_failures = sum(page["status"] != "observed" for page in pages)
    current_receipt_failures = cast(
        "int", archive_readback["receipt_sidecars_unresolved"]
    )
    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.australian-mbs-current-release-page-chronology",
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "requirement": "M-109",
        "status": (
            "current_index_links_bound_to_official_rows_and_current_receipts_history_incomplete"
            if page_failures == 0
            and unresolved == 0
            and current_receipt_failures == 0
            and archive_readback["status"]
            == "exact_current_revision_receipts_verified"
            else "incomplete_official_page_observation"
        ),
        "inputs": [
            {
                "path": INDEX.relative_to(ROOT).as_posix(),
                "sha256": _sha256(index_bytes),
            }
        ],
        "scope": {
            "official_pages_expected": len(pages),
            "official_pages_observed": sum(
                page["status"] == "observed" for page in pages
            ),
            "current_index_xml_links": len(resources),
            "exactly_one_official_row_matched": sum(
                len(resource["matching_official_rows"]) == 1
                for resource in resources
            ),
            "unresolved_or_ambiguous_rows": unresolved,
            "archive_revision": archive_readback.get("revision"),
            "current_receipt_sidecars_verified": archive_readback[
                "receipt_sidecars_verified"
            ],
            "current_receipt_sidecars_unresolved": current_receipt_failures,
            "source_payloads_requested": False,
            "source_payloads_read": False,
            "html_bodies_retained": False,
            "expected_historical_denominator_complete": False,
            "m109_accepted": False,
        },
        "interpretation": {
            "date_mentions": (
                "Date phrases are copied from the exact official XML table row. "
                "They are not normalized into effective dates or assigned to "
                "source eras; page labels, page-update dates, and filename tokens "
                "remain separate."
            ),
            "coverage": (
                "This reconciles only the 82 XML links on the observed current "
                "Downloads index. It does not establish the full MBS/PBS "
                "historical denominator, rights, field semantics, or admission."
            ),
            "absence": "An unresolved link is not evidence of source absence.",
        },
        "archive_readback": archive_readback,
        "pages": pages,
    }
    report["digest"] = {"algorithm": "sha256-canonical-json"}
    report["digest"]["value"] = _canonical_digest(report)
    return report


def main() -> int:
    """Write the bounded value-free chronology report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = build_report()
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if report["status"].startswith("current_index_links_bound") else 2


if __name__ == "__main__":
    raise SystemExit(main())
