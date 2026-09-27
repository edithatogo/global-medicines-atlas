"""Safety and bounded outcome tests for the MBS page-only diagnostic."""

from __future__ import annotations

import httpx
from scripts.diagnose_mbs_publication_page import (
    MAX_PAGE_BYTES,
    SOURCE_PAGE,
    probe_page,
)


def test_probe_reads_only_pinned_page_and_counts_workbook_links() -> None:
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            200,
            text='<a href="/sites/default/files/annual.xlsx">Workbook</a>',
            headers={"content-type": "text/html"},
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = probe_page(client, timeout_seconds=12)
    assert requested == [SOURCE_PAGE]
    assert result["outcome"] == "http_response"
    assert result["xlsx_link_count"] == 1
    assert "annual.xlsx" not in str(result)


def test_probe_reports_transport_class_without_error_text() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive diagnostic detail", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        result = probe_page(client, timeout_seconds=12)
    assert result == {
        "outcome": "transport_error",
        "error_classes": ["ReadTimeout"],
    }


def test_probe_rejects_external_redirect_without_requesting_it() -> None:
    requested: list[str] = []

    def redirect(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            302, headers={"location": "https://example.org/book.xlsx"}
        )

    with httpx.Client(transport=httpx.MockTransport(redirect)) as client:
        result = probe_page(client, timeout_seconds=12)
    assert requested == [SOURCE_PAGE]
    assert result["outcome"] == "blocked_redirect"


def test_probe_rejects_oversized_page_without_returning_body() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, content=b"x" * (MAX_PAGE_BYTES + 1)
            )
        )
    ) as client:
        result = probe_page(client, timeout_seconds=12)
    assert result == {"outcome": "page_too_large", "http_status": 200}
