"""Tests for the read-only Medicare workbook egress probe."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from global_medicines_atlas.australian_mbs_head_preflight import (
    WORKBOOKS,
    preflight_medicare_workbook_urls,
)

SHA = "a" * 40


class _AsyncMockTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        handler: Callable[
            [httpx.Request], httpx.Response | Awaitable[httpx.Response]
        ],
    ) -> None:
        self.handler = handler

    async def handle_async_request(
        self, request: httpx.Request
    ) -> httpx.Response:
        response = self.handler(request)
        if isinstance(response, httpx.Response):
            return response
        return await response


def _run(
    handler: Callable[
        [httpx.Request], httpx.Response | Awaitable[httpx.Response]
    ],
    *,
    request_timeout_seconds: float = 15,
) -> dict[str, Any]:
    return asyncio.run(
        preflight_medicare_workbook_urls(
            exact_commit=SHA,
            workflow_commit=SHA,
            workflow_ref="refs/heads/main",
            run_id="12345",
            transport=_AsyncMockTransport(handler),
            request_timeout_seconds=request_timeout_seconds,
        )
    )


def test_preflight_uses_head_and_returns_only_bounded_headers() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={
                "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "content-length": "1234",
                "etag": '"must-not-be-copied"',
            },
            request=request,
        )

    report = _run(respond)

    assert report["status"] == "passed"
    assert report["request_method"] == "HEAD"
    assert report["source_bytes_read"] is False
    assert len(requests) == len(WORKBOOKS) == 3
    assert all(request.method == "HEAD" for request in requests)
    assert [item["source"] for item in report["results"]] == [
        "quarterly",
        "annual",
        "year_to_date",
    ]
    assert all(item["content_length"] == 1234 for item in report["results"])
    assert all(item["body_read"] is False for item in report["results"])
    assert all("etag" not in item for item in report["results"])


def test_preflight_records_timeout_without_exception_text() -> None:
    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("source body or private detail")

    report = _run(timeout)

    assert report["status"] == "incomplete"
    assert report["results"] == [
        {"source": name, "status": "timeout"} for name, _url in WORKBOOKS
    ]
    assert "source body" not in str(report)


def test_preflight_records_transport_failures_without_exception_text() -> None:
    def fail_transport(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private transport details", request=request)

    report = _run(fail_transport)

    assert report["status"] == "incomplete"
    assert report["results"] == [
        {"source": name, "status": "transport_error"}
        for name, _url in WORKBOOKS
    ]
    assert "private transport" not in str(report)


def test_preflight_does_not_follow_redirects() -> None:
    def redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "https://other.example/payload.xlsx"},
            request=request,
        )

    report = _run(redirect)

    assert report["status"] == "incomplete"
    assert all(
        item["status"] == "unexpected_response" for item in report["results"]
    )
    assert all("location" not in item for item in report["results"])


@pytest.mark.parametrize(
    ("commit", "workflow_commit", "workflow_ref"),
    [
        ("invalid", SHA, "refs/heads/main"),
        (SHA, "b" * 40, "refs/heads/main"),
        (SHA, SHA, "refs/heads/feature"),
    ],
)
def test_preflight_fails_closed_on_non_exact_main_context(
    commit: str, workflow_commit: str, workflow_ref: str
) -> None:
    with pytest.raises(ValueError, match="preflight"):
        asyncio.run(
            preflight_medicare_workbook_urls(
                exact_commit=commit,
                workflow_commit=workflow_commit,
                workflow_ref=workflow_ref,
                run_id="12345",
                transport=_AsyncMockTransport(
                    lambda _request: pytest.fail(
                        "invalid context must not request"
                    )
                ),
            )
        )


def test_preflight_requires_excel_headers() -> None:
    def wrong_type(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": "88"},
            request=request,
        )

    report = _run(wrong_type)

    assert report["status"] == "incomplete"
    assert all(
        item["status"] == "unexpected_response" for item in report["results"]
    )


def test_preflight_accepts_excel_content_type_parameters() -> None:
    def response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; charset=binary",
                "content-length": "88",
            },
            request=request,
        )

    report = _run(response)

    assert report["status"] == "passed"


def test_preflight_rejects_non_200_with_valid_excel_headers() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            headers={
                "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "content-length": "88",
            },
            request=request,
        )

    report = _run(unavailable)

    assert report["status"] == "incomplete"
    assert all(
        item["status"] == "unexpected_response" for item in report["results"]
    )


def test_preflight_enforces_wall_clock_timeout_on_slow_response() -> None:
    async def slow_response(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(
            200,
            headers={
                "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "content-length": "88",
            },
            request=request,
        )

    report = _run(slow_response, request_timeout_seconds=0.001)

    assert report["status"] == "incomplete"
    assert report["results"] == [
        {"source": name, "status": "timeout"} for name, _url in WORKBOOKS
    ]


@pytest.mark.parametrize(
    "request_timeout_seconds", [0, -1, float("inf"), float("nan")]
)
def test_preflight_rejects_invalid_request_deadlines(
    request_timeout_seconds: float,
) -> None:
    with pytest.raises(ValueError, match="timeout"):
        asyncio.run(
            preflight_medicare_workbook_urls(
                exact_commit=SHA,
                workflow_commit=SHA,
                workflow_ref="refs/heads/main",
                run_id="12345",
                transport=_AsyncMockTransport(
                    lambda _request: pytest.fail(
                        "invalid deadline must not request"
                    )
                ),
                request_timeout_seconds=request_timeout_seconds,
            )
        )
