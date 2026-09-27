#!/usr/bin/env python3
"""Bounded, metadata-only probe of one official Medicare publication page."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from global_medicines_atlas.australian_harvesting import DEFAULT_HARVEST_HEADERS

SOURCE_PAGE = (
    "https://www.health.gov.au/resources/publications/"
    "medicare-annual-statistics-state-and-territory-2009-10-to-2025-26"
    "?language=en"
)
ALLOWED_HOSTS = frozenset({"www.health.gov.au", "health.gov.au"})
MAX_PAGE_BYTES = 262_144
MAX_REDIRECTS = 3
MAX_CAUSE_DEPTH = 4


def _safe_page(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_HOSTS
        and parsed.username is None
        and parsed.password is None
        and parsed.port is None
    )


def _error_classes(exc: BaseException) -> list[str]:
    classes: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while (
        current is not None
        and len(classes) < MAX_CAUSE_DEPTH
        and id(current) not in seen
    ):
        seen.add(id(current))
        classes.append(type(current).__name__)
        current = current.__cause__
    return classes


def _response_metadata(
    response: httpx.Response, url: str, redirect_count: int
) -> dict[str, object]:
    result: dict[str, object] = {
        "outcome": "http_response",
        "http_status": response.status_code,
        "final_url": url,
        "redirect_count": redirect_count,
        "content_type": response.headers.get("content-type", ""),
    }
    if response.status_code != HTTPStatus.OK:
        return result
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > MAX_PAGE_BYTES:
            return {"outcome": "page_too_large", "http_status": HTTPStatus.OK}
    page = bytes(body)
    result["byte_count"] = len(page)
    result["sha256"] = hashlib.sha256(page).hexdigest()
    result["xlsx_link_count"] = len(
        re.findall(
            rb'href=["\'][^"\']+\.xlsx(?:\?[^"\']*)?["\']', page, re.IGNORECASE
        )
    )
    return result


def probe_page(
    client: httpx.Client, *, timeout_seconds: float
) -> dict[str, object]:
    """Read only bounded HTML; never request an XLSX link or return page text."""
    url = SOURCE_PAGE
    for redirect_count in range(MAX_REDIRECTS + 1):
        if not _safe_page(url):
            return {
                "outcome": "blocked_redirect",
                "redirect_count": redirect_count,
            }
        try:  # ruff: ignore[too-many-statements-in-try-clause] -- bounded stream and redirect transaction
            with client.stream(
                "GET",
                url,
                headers=DEFAULT_HARVEST_HEADERS,
                timeout=timeout_seconds,
                follow_redirects=False,
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        return {
                            "outcome": "missing_redirect_location",
                            "http_status": response.status_code,
                        }
                    url = urljoin(url, location)
                    continue
                return _response_metadata(response, url, redirect_count)
        except httpx.RequestError as exc:
            return {
                "outcome": "transport_error",
                "error_classes": _error_classes(exc),
            }
    return {
        "outcome": "too_many_redirects",
        "redirect_count": MAX_REDIRECTS + 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    attempts: list[dict[str, object]] = []
    with httpx.Client(trust_env=True) as client:
        for timeout_seconds in (12.0, 30.0):
            result = probe_page(client, timeout_seconds=timeout_seconds)
            attempts.append({"timeout_seconds": timeout_seconds, **result})
            if result["outcome"] == "http_response":
                break
    receipt = {
        "schema_id": "global-medicines-atlas.mbs-page-transport-diagnostic",
        "schema_version": 1,
        "observed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_page": SOURCE_PAGE,
        "metadata_only": True,
        "workbook_requested": False,
        "publication_performed": False,
        "attempts": attempts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
