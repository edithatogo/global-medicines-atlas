"""Read-only hosted reachability probe for authorized Medicare workbooks."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import httpx

WORKBOOKS = (
    (
        "quarterly",
        "https://www.health.gov.au/sites/default/files/2026-08/medicare-quarterly-statistics-state-and-territory-june-quarter-2025-26.xlsx",
    ),
    (
        "annual",
        "https://www.health.gov.au/sites/default/files/2026-08/medicare-annual-statistics-state-and-territory-2009-10-to-2024-25.xlsx",
    ),
    (
        "year_to_date",
        "https://www.health.gov.au/sites/default/files/2026-08/medicare-statistics-year-to-date-summary-tables-july-to-june-2025-26.xlsx",
    ),
)
_XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def preflight_medicare_workbook_urls(
    *,
    exact_commit: str,
    workflow_commit: str,
    workflow_ref: str,
    run_id: str,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Issue bounded HEAD-only requests and return a value-free receipt."""
    if re.fullmatch(r"[0-9a-f]{40}", exact_commit) is None:
        raise ValueError("preflight exact commit is invalid")
    if workflow_commit != exact_commit or workflow_ref != "refs/heads/main":
        raise ValueError("preflight must run on the exact main commit")
    results: list[dict[str, Any]] = []
    timeout = httpx.Timeout(15.0, connect=5.0)
    with httpx.Client(
        follow_redirects=False,
        timeout=timeout,
        transport=transport,
        headers={
            "User-Agent": "GlobalMedicinesAtlas/1.0 (read-only MBS source preflight)",
            "Accept": _XLSX_CONTENT_TYPE,
        },
    ) as client:
        for name, url in WORKBOOKS:
            try:
                response = client.head(url)
            except httpx.TimeoutException:
                results.append({"source": name, "status": "timeout"})
                continue
            except httpx.TransportError:
                results.append({"source": name, "status": "transport_error"})
                continue
            try:
                content_length = int(response.headers.get("content-length", ""))
            except ValueError:
                content_length = 0
            content_type = response.headers.get("content-type", "")
            if ";" in content_type:
                content_type = content_type.split(";", maxsplit=1)[0].strip()
            headers_valid = (
                content_length > 0 and content_type == _XLSX_CONTENT_TYPE
            )
            result_status = (
                "passed"
                if response.status_code == HTTPStatus.OK and headers_valid
                else "unexpected_response"
            )
            results.append({
                "source": name,
                "status": result_status,
                "http_status": response.status_code,
                "content_length": content_length
                if content_length > 0
                else None,
                "content_type_valid": content_type == _XLSX_CONTENT_TYPE,
                "body_read": False,
            })
    passed = len(results) == len(WORKBOOKS) and all(
        result["status"] == "passed" for result in results
    )
    return {
        "schema_version": 1,
        "status": "passed" if passed else "incomplete",
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "workflow_commit": workflow_commit,
        "workflow_ref": workflow_ref,
        "exact_commit": exact_commit,
        "run_id": run_id,
        "request_method": "HEAD",
        "request_timeout_seconds": 15,
        "redirects_followed": False,
        "source_bytes_read": False,
        "results": results,
        "publication_performed": False,
    }
