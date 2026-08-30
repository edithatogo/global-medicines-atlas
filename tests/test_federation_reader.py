"""Synthetic anonymous transport and cache tests; no real source downloads."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from jsonschema import FormatChecker

from global_medicines_atlas import federation_reader as runtime
from global_medicines_atlas.federation_reader import FederatedReader

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "contracts/medallion/v4/federation.schema.json").read_bytes()
PAYLOAD = b"synthetic payload"
NOW = datetime(2026, 8, 30, 1, tzinfo=UTC)


def document(**changes: Any) -> bytes:
    value = json.loads(
        (ROOT / "contracts/medallion/v4/fixtures/valid.json").read_bytes()
    )
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    for group in ("location", "verification"):
        value[group].update(sha256=digest, bytes=len(PAYLOAD))
    value["rights"]["subject_sha256"] = digest
    value["cache"]["offline_behavior"] = "verified_exact_digest_only"
    for group, fields in changes.items():
        value[group].update(fields)
    return json.dumps(value).encode()


class Hub:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.payload = PAYLOAD
        self.metadata: dict[str, Any] = {
            "sha": "a" * 40,
            "private": False,
            "gated": False,
        }
        self.status = 200

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        if "/api/datasets/" in request.url.path:
            return httpx.Response(self.status, json=self.metadata)
        return httpx.Response(self.status, content=self.payload)


def reader(hub: Hub, *documents: bytes, **kwargs: Any) -> FederatedReader:
    return FederatedReader(
        schema=SCHEMA,
        admitted_contracts=frozenset(
            hashlib.sha256(item).hexdigest() for item in documents
        ),
        transport_factory=lambda: httpx.MockTransport(hub.handle),
        clock=lambda: NOW,
        **kwargs,
    )


def test_remote_roundtrip_offline_and_eviction() -> None:
    raw = document()
    hub = Hub()
    with reader(hub, raw) as client:
        with client.open(raw) as result:
            assert result.origin == "remote"
            assert result.stream.read() == PAYLOAD
        assert result.stream.closed
        assert len(hub.requests) == 2
        with client.open(raw, offline=True) as result:
            assert result.origin == "verified_cache"
            assert result.stream.read() == PAYLOAD
        assert len(hub.requests) == 2
        client.evict()
        with (
            pytest.raises(ValueError, match="offline"),
            client.open(raw, offline=True),
        ):
            pytest.fail("eviction must not synthesize an object")
        with client.open(raw) as result:
            assert result.stream.read() == PAYLOAD
    assert client.cached_bytes == 0
    with pytest.raises(ValueError, match="closed"), client.open(raw):
        pytest.fail("closed reader")


def test_unadmitted_or_invalid_contract_never_fetches() -> None:
    raw = document()
    hub = Hub()
    with (
        reader(hub) as client,
        pytest.raises(ValueError, match="admitted"),
        client.open(raw),
    ):
        pytest.fail("unadmitted")
    invalid = document(location={"revision": "main"})
    with (
        reader(hub, invalid) as client,
        pytest.raises(ValueError, match="contract"),
        client.open(invalid),
    ):
        pytest.fail("invalid")
    assert not hub.requests
    with pytest.raises(ValueError, match="schema"):
        FederatedReader(schema=b"{}", admitted_contracts=frozenset())


@pytest.mark.parametrize(
    "metadata",
    [{"private": True}, {"gated": "auto"}, {"sha": "b" * 40}, {"private": 0}],
)
def test_live_visibility_must_match(metadata: dict[str, Any]) -> None:
    raw = document()
    hub = Hub()
    hub.metadata.update(metadata)
    with reader(hub, raw) as client:
        with pytest.raises(ValueError, match="public"), client.open(raw):
            pytest.fail("private or misbound")
        assert client.cached_bytes == 0
        assert len(hub.requests) == 1


@pytest.mark.parametrize("payload", [b"x", b"x" * len(PAYLOAD), PAYLOAD + b"x"])
def test_unverified_bytes_never_escape(payload: bytes) -> None:
    raw = document()
    hub = Hub()
    hub.payload = payload
    with reader(hub, raw) as client:
        with pytest.raises(ValueError, match=r"digest|size"), client.open(raw):
            pytest.fail("unverified output")
        assert client.cached_bytes == 0


def test_remote_failure_does_not_silently_use_cache() -> None:
    raw = document()
    hub = Hub()
    with reader(hub, raw) as client:
        with client.open(raw):
            pass
        hub.status = 503
        with pytest.raises(ValueError, match="HTTP"), client.open(raw):
            pytest.fail("implicit stale fallback")
        with client.open(raw, offline=True) as result:
            assert result.stream.read() == PAYLOAD


def test_cache_budget_and_expiry() -> None:
    raw = document()
    hub = Hub()
    with reader(hub, raw, cache_bytes=1) as client:
        with client.open(raw):
            pass
        assert client.cached_bytes == 0
    expires = NOW - timedelta(seconds=1)
    expired = document(
        cache={"expires_at": expires.isoformat().replace("+00:00", "Z")}
    )
    with reader(hub, expired) as client:
        with client.open(expired):
            pass
        with (
            pytest.raises(ValueError, match="offline"),
            client.open(expired, offline=True),
        ):
            pytest.fail("expired")
    with (
        reader(hub, raw, max_object_bytes=1) as client,
        pytest.raises(ValueError, match="budget"),
        client.open(raw),
    ):
        pytest.fail("over budget")


def test_offline_fail_closed_policy() -> None:
    raw = document(cache={"offline_behavior": "fail_closed"})
    hub = Hub()
    with reader(hub, raw) as client:
        with client.open(raw):
            pass
        with (
            pytest.raises(ValueError, match="offline"),
            client.open(raw, offline=True),
        ):
            pytest.fail("policy")


@pytest.mark.parametrize(
    "options",
    [
        {"max_object_bytes": 0},
        {"cache_bytes": True},
        {"max_entries": -1},
        {"max_open_reads": 0},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": 0},
    ],
)
def test_invalid_reader_limits(options: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"budgets|timeout"):
        reader(Hub(), **options)


def test_admission_pin_and_document_bounds() -> None:
    with pytest.raises(ValueError, match="digest"):
        FederatedReader(schema=SCHEMA, admitted_contracts=frozenset({"bad"}))
    raw = document(authority={"schema_sha256": "b" * 64})
    with (
        reader(Hub(), raw) as client,
        pytest.raises(ValueError, match="schema pin"),
        client.open(raw),
    ):
        pytest.fail("wrong schema era")
    oversized = b" " * (runtime.METADATA_BYTES + 1)
    with (
        reader(Hub(), oversized) as client,
        pytest.raises(ValueError, match="metadata budget"),
        client.open(oversized),
    ):
        pytest.fail("oversized contract")


def test_cache_lru_identity_and_open_result_bounds() -> None:
    first = document()
    second = document(source={"acquisition_id": "another-acquisition"})
    hub = Hub()
    with reader(hub, first, second, max_entries=1, max_open_reads=1) as client:
        with client.open(first) as held:
            with (
                pytest.raises(ValueError, match="open-result"),
                client.open(second),
            ):
                pytest.fail("too many live materializations")
            assert held.stream.read() == PAYLOAD
        with client.open(first):
            pass
        assert (
            len(hub.requests) == 4
        )  # online reads never silently prefer cache
        with client.open(second):
            pass
        with (
            pytest.raises(ValueError, match="offline"),
            client.open(first, offline=True),
        ):
            pytest.fail("identity silently reused")
        with client.open(second, offline=True) as result:
            assert result.stream.read() == PAYLOAD
            client.close()
            result.stream.seek(0)
            assert result.stream.read() == PAYLOAD
        assert result.stream.closed


@pytest.mark.parametrize(
    "url",
    [
        "http://huggingface.co/file",
        "https://localhost/file",
        "https://huggingface.co.evil.invalid/file",
        "https://user@huggingface.co/file",
        "https://huggingface.co:444/file",
        "https://huggingface.co/file#fragment",
    ],
)
def test_redirect_destination_rejected_before_contact(url: str) -> None:
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": url})

    raw = document()
    with (
        FederatedReader(
            schema=SCHEMA,
            admitted_contracts=frozenset({hashlib.sha256(raw).hexdigest()}),
            transport_factory=lambda: httpx.MockTransport(handle),
        ) as client,
        pytest.raises(ValueError, match="destination"),
        client.open(raw),
    ):
        pytest.fail("untrusted redirect")
    assert len(calls) == 1


def test_allowed_redirect_never_replays_cookies_or_environment_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = Hub()
    raw = document()
    monkeypatch.setenv("HF_TOKEN", "synthetic-not-a-real-token")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")

    def handle(request: httpx.Request) -> httpx.Response:
        if "/resolve/" in request.url.path:
            assert "authorization" not in request.headers
            return httpx.Response(
                302,
                headers={
                    "location": "https://cas-bridge.xethub.hf.co/payload?signature=synthetic",
                    "set-cookie": "secret=synthetic; Domain=.hf.co; Secure",
                },
            )
        return hub.handle(request)

    with (
        FederatedReader(
            schema=SCHEMA,
            admitted_contracts=frozenset({hashlib.sha256(raw).hexdigest()}),
            transport_factory=lambda: httpx.MockTransport(handle),
            clock=lambda: NOW,
        ) as client,
        client.open(raw) as result,
    ):
        assert result.stream.read() == PAYLOAD


@pytest.mark.parametrize("mode", ["loop", "no-location", "encoded", "timeout"])
def test_http_failures_are_bounded_and_redacted(mode: str) -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if mode == "timeout":
            raise httpx.ReadTimeout(
                "sensitive signed URL omitted", request=request
            )
        if mode == "encoded":
            return httpx.Response(
                200, headers={"content-encoding": "unknown"}, content=b"x"
            )
        headers = {"location": str(request.url)} if mode == "loop" else {}
        return httpx.Response(302, headers=headers)

    raw = document()
    with (
        FederatedReader(
            schema=SCHEMA,
            admitted_contracts=frozenset({hashlib.sha256(raw).hexdigest()}),
            transport_factory=lambda: httpx.MockTransport(handle),
        ) as client,
        pytest.raises(ValueError, match="HTTP") as error,
        client.open(raw),
    ):
        pytest.fail("bad HTTP")
    assert calls <= 4
    assert "sensitive" not in str(error.value)


@pytest.mark.parametrize("ticks", [[0, 100], [0, 0, 100]])
def test_total_deadline_checked_before_request_and_during_body(
    monkeypatch: pytest.MonkeyPatch,
    ticks: list[int],
) -> None:
    values = iter(ticks)
    monkeypatch.setattr(runtime.time, "monotonic", lambda: next(values))
    raw = document()
    with (
        reader(Hub(), raw) as client,
        pytest.raises(ValueError, match="deadline"),
        client.open(raw),
    ):
        pytest.fail("unbounded stream")


def test_expired_cache_and_corruption_do_not_escape() -> None:
    raw = document()
    hub = Hub()
    with reader(hub, raw) as client:
        with client.open(raw):
            pass
        key = hashlib.sha256(raw).hexdigest()
        expired_stream = client._cache[key].stream
        client._cache[key].expires_at = NOW
        with (
            pytest.raises(ValueError, match="offline"),
            client.open(raw, offline=True),
        ):
            pytest.fail("expired")
        assert expired_stream.closed
        assert client.cached_bytes == 0
        with client.open(raw):
            pass
        client._cache[key].stream.seek(0)
        client._cache[key].stream.write(b"broken")
        with (
            pytest.raises(ValueError, match="digest"),
            client.open(raw, offline=True),
        ):
            pytest.fail("corrupt cache")


def test_malformed_hub_metadata_is_not_public_evidence() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    raw = document()
    with (
        FederatedReader(
            schema=SCHEMA,
            admitted_contracts=frozenset({hashlib.sha256(raw).hexdigest()}),
            transport_factory=lambda: httpx.MockTransport(handle),
        ) as client,
        pytest.raises(TypeError, match="metadata"),
        client.open(raw),
    ):
        pytest.fail("malformed metadata")


def test_verified_result_does_not_offer_mutation_or_unbounded_writes() -> None:
    raw = document()
    with reader(Hub(), raw) as client, client.open(raw) as result:
        assert not result.stream.writable()
        with pytest.raises(io.UnsupportedOperation, match="write"):
            result.stream.write(b"unverified growth")
        assert result.stream.read() == PAYLOAD


def test_missing_format_plugins_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def incomplete() -> FormatChecker:
        return FormatChecker(formats=["date"])

    monkeypatch.setattr(runtime, "FormatChecker", incomplete)
    with pytest.raises(ValueError, match="format"):
        reader(Hub())


def test_live_raw_source_reads_remain_actions_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = json.loads(document())
    value["evidence_kind"] = "live"
    value["source"]["comparison_cohort"] = "current"
    raw = json.dumps(value).encode()
    hub = Hub()
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with (
        reader(hub, raw) as client,
        pytest.raises(ValueError, match="GitHub Actions"),
        client.open(raw),
    ):
        pytest.fail("live raw source downloaded on workstation")
    assert not hub.requests
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    with reader(hub, raw) as client, client.open(raw) as result:
        assert result.stream.read() == PAYLOAD
