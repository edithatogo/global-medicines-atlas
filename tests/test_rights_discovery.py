"""Bounded official-page rights discovery tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx

from global_medicines_atlas.rights_discovery import discover_rights_evidence

NOW = datetime(2026, 8, 21, tzinfo=UTC)


def test_discovers_and_resolves_rights_links_with_content_digest() -> None:
    body = b"""<html><body>
    <a href='/copyright'>Copyright and reuse</a>
    <a href='https://creativecommons.org/licenses/by/4.0/'>CC BY</a>
    <a href='/about'>About</a>
    </body></html>"""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=body,
            request=request,
        )
    )
    with httpx.Client(transport=transport) as client:
        receipt = discover_rights_evidence(
            "https://authority.example/data",
            client=client,
            observed_at=NOW,
        )
    assert receipt.outcome == "observed"
    assert receipt.content_sha256 == hashlib.sha256(body).hexdigest()
    assert {item.url for item in receipt.rights_links} == {
        "https://authority.example/copyright",
        "https://creativecommons.org/licenses/by/4.0/",
    }


def test_byte_limit_produces_failure_receipt_without_content_digest() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"x" * 32,
            request=request,
        )
    )
    with httpx.Client(transport=transport) as client:
        receipt = discover_rights_evidence(
            "https://authority.example/data",
            client=client,
            observed_at=NOW,
            max_bytes=16,
        )
    assert receipt.outcome == "too_large"
    assert receipt.content_sha256 is None
    assert receipt.observed_bytes == 32


def test_network_failure_is_redacted_to_exception_class() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret-bearing diagnostic", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        receipt = discover_rights_evidence(
            "https://authority.example/data",
            client=client,
            observed_at=NOW,
        )
    assert receipt.outcome == "failed"
    assert receipt.failure_reason == "ConnectError"
    assert "secret" not in receipt.model_dump_json()
