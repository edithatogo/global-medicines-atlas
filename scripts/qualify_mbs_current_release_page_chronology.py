#!/usr/bin/env python3
"""Reconcile current MBS XML receipts to official release-page metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
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
STREAM_CHUNK_BYTES = 64 * 1024
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


@dataclass(frozen=True)
class BoundedHTTPResponse:
    """Response metadata and at most the requested in-memory body limit."""

    final_url: str
    status_code: int
    headers: httpx.Headers
    body: bytes
    observed_bytes: int
    body_read_complete: bool


def collect_limited(chunks: Any, max_bytes: int) -> tuple[bytes, int, bool]:
    """Consume response chunks until complete or the bounded read is exceeded."""
    body = bytearray()
    observed_bytes = 0
    for chunk in chunks:
        next_size = observed_bytes + len(chunk)
        if next_size > max_bytes:
            return bytes(body), next_size, False
        body.extend(chunk)
        observed_bytes = next_size
    return bytes(body), observed_bytes, True


def _bounded_get(url: str, max_bytes: int) -> BoundedHTTPResponse:
    """Stream a response, stopping after the first chunk over the size limit."""
    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    ) as response:
        body, observed_bytes, complete = collect_limited(
            response.iter_bytes(chunk_size=STREAM_CHUNK_BYTES), max_bytes
        )
        return BoundedHTTPResponse(
            final_url=str(response.url),
            status_code=response.status_code,
            headers=response.headers,
            body=body,
            observed_bytes=observed_bytes,
            body_read_complete=complete,
        )


def _resource_metadata(
    resource: dict[str, Any], page_status: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Preserve an expected resource even if its official page cannot be read."""
    return {
        "source_url": resource["source_url"],
        "filename": resource["filename"],
        "source_scope": resource.get("source_scope", "current_index_xml"),
        "page_observation_status": page_status,
        "archive_receipts": [
            {
                "receipt_path": receipt.get("receipt_path"),
                "archive_path": receipt.get("archive_path"),
                "payload_sha256": receipt.get("payload_sha256"),
            }
            for receipt in resource["matching_archive_receipts"]
        ],
        "matching_official_rows": rows,
    }


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


def read_page(page: dict[str, Any], expected_urls: list[str]) -> dict[str, Any]:
    """Read one official HTML page in memory and discard its body."""
    requested_url = cast("str", page["url"])
    started = datetime.now(UTC)
    try:
        response = _bounded_get(requested_url, MAX_PAGE_BYTES)
        completed = datetime.now(UTC)
    except httpx.HTTPError as exc:
        completed = datetime.now(UTC)
        resources = [
            _resource_metadata(resource, "unavailable", [])
            for resource in page["resources"]
        ]
        return {
            "page_id": page["page_id"],
            "requested_url": requested_url,
            "status": "unavailable",
            "failure_class": type(exc).__name__,
            "client_request_started_at": started.isoformat(),
            "client_response_received_at": completed.isoformat(),
            "resources": resources,
        }

    final_url = response.final_url
    page_receipt: dict[str, Any] = {
        "requested_url": requested_url,
        "final_url": final_url,
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "observed_bytes": response.observed_bytes,
        "sha256": (
            _sha256(response.body) if response.body_read_complete else None
        ),
        "body_read_complete": response.body_read_complete,
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
        or not response.body_read_complete
        or not page_receipt["content_type"].lower().startswith("text/html")
        or urlparse(final_url).hostname not in ALLOWED_HOSTS
    ):
        page_metadata["status"] = "invalid_page_response"
        page_metadata["failure_class"] = "status_size_content_type_or_host"
        page_metadata["resources"] = [
            _resource_metadata(resource, "invalid_page_response", [])
            for resource in page["resources"]
        ]
        return page_metadata

    soup = BeautifulSoup(response.body, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    heading = soup.find("h1")
    page_metadata["official_heading"] = (
        heading.get_text(" ", strip=True) if isinstance(heading, Tag) else None
    )
    page_metadata["page_last_updated_text"] = _page_updated_date(page_text)
    by_url = match_official_rows(response.body, final_url, expected_urls)
    page_metadata["status"] = "observed"
    for resource in page["resources"]:
        source_url = cast("str", resource["source_url"])
        page_metadata["resources"].append(
            _resource_metadata(resource, "observed", by_url.get(source_url, []))
        )
    return page_metadata


def _read_json_metadata(url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read one bounded public JSON metadata object without saving its bytes."""
    started = datetime.now(UTC)
    response = _bounded_get(url, MAX_PAGE_BYTES)
    completed = datetime.now(UTC)
    body = response.body
    if (
        response.status_code != HTTP_OK
        or not response.body_read_complete
        or urlparse(response.final_url).hostname != "huggingface.co"
    ):
        raise ValueError("public_metadata_response_invalid")
    loaded: object = json.loads(body)
    if not isinstance(loaded, dict):
        raise TypeError("public_metadata_document_not_object")
    document = cast("dict[str, Any]", loaded)
    return document, {
        "requested_url": url,
        "final_url": response.final_url,
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "observed_bytes": response.observed_bytes,
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
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[str]],
    list[dict[str, Any]],
]:
    """Group current-index links and receipt-only URLs by official page."""
    pages_by_id: dict[str, dict[str, Any]] = {}
    expected_urls_by_page: dict[str, list[str]] = defaultdict(list)
    resources_by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    selected_urls: set[str] = set()
    for resource in index["monthly_schedule_xml_index_reconciliation"][
        "resources"
    ]:
        page_id = resource["page_id"]
        selected = {**resource, "source_scope": "current_index_xml"}
        resources_by_page[page_id].append(selected)
        expected_urls_by_page[page_id].append(resource["source_url"])
        selected_urls.add(resource["source_url"])

    official_resources_by_url: dict[str, list[dict[str, Any]]] = defaultdict(
        list
    )
    for page in index["downloads_index"]["pages"]:
        for resource in page["resources"]:
            source_url = resource.get("url")
            if isinstance(source_url, str):
                official_resources_by_url[source_url].append({
                    **resource,
                    "page_id": page["page_id"],
                })

    receipts_by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for receipt in index["current_public_archive"]["receipts"]:
        receipts_by_url[receipt["source_url"]].append({
            "receipt_path": receipt["receipt_path"],
            "archive_path": receipt["archive_path"],
            "payload_sha256": receipt["payload_sha256"],
        })

    unresolved_receipt_resources: list[dict[str, Any]] = []
    for source_url in sorted(set(receipts_by_url) - selected_urls):
        official_matches = official_resources_by_url.get(source_url, [])
        if len(official_matches) != 1:
            unresolved_receipt_resources.append({
                "source_url": source_url,
                "filename": source_url.rsplit("/", 1)[-1],
                "source_scope": "archive_receipt_only_not_selected_current_xml_index",
                "matching_archive_receipts": receipts_by_url[source_url],
                "unresolved_reason": (
                    "no_official_downloads_index_row"
                    if not official_matches
                    else "ambiguous_official_downloads_index_rows"
                ),
            })
            continue

        official_resource = official_matches[0]
        page_id = cast("str", official_resource["page_id"])
        resources_by_page[page_id].append({
            "source_url": source_url,
            "filename": official_resource["filename"],
            "page_id": page_id,
            "source_scope": "archive_receipt_only_not_selected_current_xml_index",
            "matching_archive_receipts": receipts_by_url[source_url],
        })
        expected_urls_by_page[page_id].append(source_url)

    for page in index["downloads_index"]["pages"]:
        page_id = page["page_id"]
        if page_id not in expected_urls_by_page:
            continue
        pages_by_id[page_id] = {
            "page_id": page_id,
            "url": page["url"],
            "label": page["label"],
            "resources": resources_by_page[page_id],
        }

    if set(pages_by_id) != set(expected_urls_by_page):
        raise ValueError("index page inventory does not bind every XML link")
    return pages_by_id, expected_urls_by_page, unresolved_receipt_resources


def _observe_pages(
    pages_by_id: dict[str, dict[str, Any]],
    expected_urls_by_page: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Fetch the bounded page set and discard response bodies after hashing."""
    ordered_pages = [pages_by_id[key] for key in sorted(pages_by_id)]

    def observe(page: dict[str, Any]) -> dict[str, Any]:
        page_id = cast("str", page["page_id"])
        return read_page(page, expected_urls_by_page[page_id])

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        return list(executor.map(observe, ordered_pages))


def bind_current_receipts(
    resources: list[dict[str, Any]], archive_readback: dict[str, Any]
) -> dict[str, int]:
    """Bind every indexed resource receipt or mark that resource unresolved."""
    verified = {
        record["receipt_path"]: record
        for record in archive_readback["receipt_sidecars"]
        if record["status"] == "exact_current_receipt"
    }
    for resource in resources:
        raw_receipts: object = resource["archive_receipts"]
        if not isinstance(raw_receipts, list) or not raw_receipts:
            resource["current_receipt_binding_status"] = (
                "invalid_receipt_mapping"
            )
            continue
        receipts = cast("list[Any]", raw_receipts)
        all_bound = True
        for raw_receipt in receipts:
            if not isinstance(raw_receipt, dict):
                all_bound = False
                continue
            receipt = cast("dict[str, Any]", raw_receipt)
            if not isinstance(receipt.get("receipt_path"), str):
                all_bound = False
                continue
            current = verified.get(receipt["receipt_path"])
            if (
                current is None
                or current.get("source_url") != resource["source_url"]
                or current.get("archive_path") != receipt.get("archive_path")
                or current.get("payload_sha256")
                != receipt.get("payload_sha256")
            ):
                all_bound = False
                continue
            receipt.update({
                "current_revision": archive_readback.get("revision"),
                "current_receipt_sha256": current["receipt"]["sha256"],
                "current_payload_sha256": current["payload_sha256"],
            })
        resource["current_receipt_binding_status"] = (
            "exact_current_receipts_verified"
            if all_bound
            else "current_receipts_unresolved"
        )
    expected = len(resources)
    bound = sum(
        resource["current_receipt_binding_status"]
        == "exact_current_receipts_verified"
        for resource in resources
    )
    return {
        "expected": expected,
        "verified": bound,
        "unresolved": expected - bound,
    }


def qualification_status(
    page_failures: int,
    unresolved_rows: int,
    current_receipt_failures: int,
    resource_receipt_failures: int,
    archive_status: str,
) -> str:
    """Pass only when every current and receipt-only link is reconciled."""
    if (
        page_failures == 0
        and unresolved_rows == 0
        and current_receipt_failures == 0
        and resource_receipt_failures == 0
        and archive_status == "exact_current_revision_receipts_verified"
    ):
        return (
            "current_index_links_bound_to_official_rows_and_current_receipts_"
            "history_incomplete"
        )
    return "incomplete_official_page_observation"


def build_report() -> dict[str, Any]:
    """Fetch current official pages and bind their XML link rows to receipts."""
    index_bytes = INDEX.read_bytes()
    index = json.loads(index_bytes)
    archive_readback = read_current_archive_receipts(index)
    pages_by_id, expected_urls_by_page, unresolved_receipt_resources = (
        _page_inputs(index)
    )
    pages = _observe_pages(pages_by_id, expected_urls_by_page)
    resources = [resource for page in pages for resource in page["resources"]]
    resources.extend(
        {
            **_resource_metadata(
                resource, "unresolved_official_page_mapping", []
            ),
            "unresolved_reason": resource["unresolved_reason"],
        }
        for resource in unresolved_receipt_resources
    )
    unresolved = sum(
        page["status"] != "observed"
        or len(resource["matching_official_rows"]) != 1
        for page in pages
        for resource in page["resources"]
    )
    unresolved += len(unresolved_receipt_resources)
    page_failures = sum(page["status"] != "observed" for page in pages)
    current_receipt_failures = cast(
        "int", archive_readback["receipt_sidecars_unresolved"]
    )
    resource_receipt_bindings = bind_current_receipts(
        resources, archive_readback
    )
    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.australian-mbs-current-release-page-chronology",
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "requirement": "M-109",
        "status": qualification_status(
            page_failures,
            unresolved,
            current_receipt_failures,
            resource_receipt_bindings["unresolved"],
            cast("str", archive_readback["status"]),
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
            "current_index_xml_links": sum(
                resource["source_scope"] == "current_index_xml"
                for resource in resources
            ),
            "archive_receipt_only_links": sum(
                resource["source_scope"]
                == "archive_receipt_only_not_selected_current_xml_index"
                for resource in resources
            ),
            "official_page_link_rows_observed": sum(
                len(resource["matching_official_rows"])
                for resource in resources
            ),
            "archive_receipt_sources_without_unique_official_row": len(
                unresolved_receipt_resources
            ),
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
            "resource_receipt_bindings_expected": resource_receipt_bindings[
                "expected"
            ],
            "resource_receipt_bindings_verified": resource_receipt_bindings[
                "verified"
            ],
            "resource_receipt_bindings_unresolved": resource_receipt_bindings[
                "unresolved"
            ],
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
                "This separately reconciles the 82 XML links selected from the "
                "current Downloads index and archived receipt URLs outside that "
                "selection. Receipt-only links do not expand the current-index "
                "denominator or establish the full MBS/PBS historical denominator, "
                "rights, field semantics, or admission."
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
