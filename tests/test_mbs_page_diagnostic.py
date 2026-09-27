"""Safety and bounded outcome tests for the MBS page-only diagnostic."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

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

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ) as client:
            return await probe_page(client, timeout_seconds=12)

    result = asyncio.run(run())
    assert requested == [SOURCE_PAGE]
    assert result["outcome"] == "http_response"
    assert result["xlsx_link_count"] == 1
    assert "annual.xlsx" not in str(result)


def test_probe_reports_transport_class_without_error_text() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive diagnostic detail", request=request)

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(timeout)
        ) as client:
            return await probe_page(client, timeout_seconds=12)

    result = asyncio.run(run())
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

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(redirect)
        ) as client:
            return await probe_page(client, timeout_seconds=12)

    result = asyncio.run(run())
    assert requested == [SOURCE_PAGE]
    assert result["outcome"] == "blocked_redirect"


def test_probe_rejects_same_host_workbook_redirect_without_requesting_it() -> (
    None
):
    requested: list[str] = []

    def redirect(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            302,
            headers={
                "location": "https://www.health.gov.au/sites/default/files/annual.xlsx"
            },
        )

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(redirect)
        ) as client:
            return await probe_page(client, timeout_seconds=12)

    assert asyncio.run(run())["outcome"] == "blocked_redirect"
    assert requested == [SOURCE_PAGE]


def test_probe_rejects_oversized_page_without_returning_body() -> None:
    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    content=b"x" * (MAX_PAGE_BYTES + 1),
                    headers={"content-type": "text/html"},
                )
            )
        ) as client:
            return await probe_page(client, timeout_seconds=12)

    result = asyncio.run(run())
    assert result == {"outcome": "page_too_large", "http_status": 200}


def test_probe_does_not_read_non_html_response() -> None:
    class UnreadableStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            raise AssertionError("binary body must not be read")
            yield b""

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    headers={
                        "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    },
                    stream=UnreadableStream(),
                )
            )
        ) as client:
            return await probe_page(client, timeout_seconds=12)

    assert asyncio.run(run()) == {
        "outcome": "non_html_response",
        "http_status": 200,
    }


def test_probe_has_whole_response_deadline_for_slow_drip() -> None:
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            for _ in range(20):
                await asyncio.sleep(0.01)
                yield b"x"

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    headers={"content-type": "text/html"},
                    stream=SlowStream(),
                )
            )
        ) as client:
            return await probe_page(client, timeout_seconds=0.05)

    assert asyncio.run(run()) == {"outcome": "wall_clock_timeout"}
