"""Tests for fail-closed public-fixture checkpoint preflight."""

from __future__ import annotations

import hashlib
import io
import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import global_medicines_atlas.platinum_checkpoint as checkpoint
from global_medicines_atlas.platinum_checkpoint import (
    PublicFixturePin,
    fetch_empty_machine_fixture,
    fetch_unadmitted_public_fixture,
    observe_unadmitted_public_fixture,
)


def payload() -> bytes:
    """Return a tiny source-faithful transport fixture."""
    output = io.BytesIO()
    pq.write_table(
        pa.table({
            "source_record_id": ["au-mbs:1", "au-mbs:2"],
            "source_ordinal": [1, 2],
            "fields": [[{"name": "ItemNum", "value": "1"}], []],
        }),
        output,
    )
    return output.getvalue()


def pin(raw: bytes) -> PublicFixturePin:
    """Bind the synthetic bytes to an exact immutable public identity."""
    return PublicFixturePin(
        dataset="edithatogo/australian-mbs-source-archive",
        revision="7" * 40,
        path="bronze/mbs/releases/fixture/p7.parquet",
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_count=len(raw),
        row_count=2,
        columns=("source_record_id", "source_ordinal", "fields"),
        max_bytes=64 * 1024,
        sample_rows=1,
    )


def metadata() -> bytes:
    """Return minimal anonymous Hub revision metadata."""
    return json.dumps({
        "sha": "7" * 40,
        "private": False,
        "gated": False,
    }).encode()


def test_verified_transport_remains_explicitly_unadmitted() -> None:
    raw = payload()
    result = observe_unadmitted_public_fixture(pin(raw), metadata(), raw)

    assert result.transport_verified is True
    assert result.product_admitted is False
    assert result.checkpoint_complete is False
    assert result.layer == "bronze"
    assert result.sample_row_count == 1
    assert result.row_count == 2
    assert result.reasons == (
        "independently admitted v4 product contract is absent",
        "independently admitted semantic manifest is absent",
        "Australian benefits medallion dataset is not yet published",
    )
    assert (
        result.receipt_sha256
        == hashlib.sha256(result.canonical_bytes).hexdigest()
    )
    assert b"fields" not in result.canonical_sample_rows
    assert result.observed_at.endswith("+00:00")


def test_observation_time_is_bound_into_receipt_digest() -> None:
    """A stale observation cannot be relabelled without changing identity."""
    raw = payload()
    first = observe_unadmitted_public_fixture(
        pin(raw),
        metadata(),
        raw,
        observed_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    relabelled = replace(first, observed_at="2026-09-02T00:00:00+00:00")

    assert first.receipt_sha256 != relabelled.receipt_sha256
    assert json.loads(first.canonical_bytes)["observed_at"] == first.observed_at

    with pytest.raises(ValueError, match="timezone"):
        observe_unadmitted_public_fixture(
            pin(raw),
            metadata(),
            raw,
            observed_at=datetime(2026, 9, 1),  # ruff: ignore[call-datetime-without-tzinfo] - negative control
        )


def test_public_preflight_receipt_content_address_is_current() -> None:
    """The committed live receipt must bind every public claim it contains."""
    receipt_path = Path(
        "quality/qualifications/platinum-mbs-transport-preflight-20260902.json"
    )
    receipt = json.loads(receipt_path.read_bytes())
    claimed_digest = receipt.pop("receipt_sha256")
    canonical = json.dumps(
        receipt, sort_keys=True, separators=(",", ":")
    ).encode()

    assert receipt["observed_at"].endswith("+00:00")
    assert hashlib.sha256(canonical).hexdigest() == claimed_digest


@pytest.mark.parametrize(
    "state",
    [
        {"sha": "8" * 40, "private": False, "gated": False},
        {"sha": "7" * 40, "private": True, "gated": False},
        {"sha": "7" * 40, "private": False, "gated": True},
        [],
    ],
)
def test_mutable_private_gated_or_malformed_metadata_fails(state) -> None:
    raw = payload()
    with pytest.raises((TypeError, ValueError), match="metadata"):
        observe_unadmitted_public_fixture(
            pin(raw), json.dumps(state).encode(), raw
        )


def test_changed_oversized_or_malformed_payload_fails() -> None:
    raw = payload()
    exact = pin(raw)
    for changed, message in (
        (raw + b"x", "identity"),
        (b"x" * (exact.max_bytes + 1), "budget"),
        (b"x" * exact.byte_count, "identity"),
    ):
        with pytest.raises(ValueError, match=message):
            observe_unadmitted_public_fixture(exact, metadata(), changed)

    malformed = b"x" * 100
    malformed_pin = PublicFixturePin(
        dataset=exact.dataset,
        revision=exact.revision,
        path=exact.path,
        sha256=hashlib.sha256(malformed).hexdigest(),
        byte_count=len(malformed),
        row_count=exact.row_count,
        columns=exact.columns,
        max_bytes=exact.max_bytes,
        sample_rows=exact.sample_rows,
    )
    with pytest.raises(ValueError, match="Parquet"):
        observe_unadmitted_public_fixture(malformed_pin, metadata(), malformed)


@pytest.mark.parametrize("raw_metadata", [b"", b"not-json"])
def test_missing_or_invalid_metadata_fails(raw_metadata) -> None:
    raw = payload()
    with pytest.raises(ValueError, match="metadata"):
        observe_unadmitted_public_fixture(pin(raw), raw_metadata, raw)


def test_schema_and_row_denominator_drift_fail_closed() -> None:
    raw = payload()
    exact = pin(raw)
    with pytest.raises(ValueError, match="columns"):
        observe_unadmitted_public_fixture(
            replace(exact, columns=(*exact.columns, "unexpected")),
            metadata(),
            raw,
        )
    with pytest.raises(ValueError, match="row count"):
        observe_unadmitted_public_fixture(
            replace(exact, row_count=3),
            metadata(),
            raw,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"dataset": "mutable"},
        {"revision": "main"},
        {"sha256": "bad"},
        {"byte_count": True},
        {"row_count": -1},
        {"columns": ()},
        {"max_bytes": 0},
        {"sample_rows": 0},
    ],
)
def test_pin_is_strict(changes) -> None:
    raw = payload()
    values = {**pin(raw).__dict__, **changes}
    with pytest.raises(ValueError, match="fixture pin"):
        PublicFixturePin(**values)


def test_anonymous_fetch_uses_exact_revision_and_bounded_payload() -> None:
    raw = payload()
    exact = pin(raw)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept-encoding"] == "identity"
        if "/api/datasets/" in str(request.url):
            return httpx.Response(200, content=metadata())
        assert exact.revision in str(request.url)
        return httpx.Response(200, content=raw)

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Accept-Encoding": "identity"},
        trust_env=False,
    ) as client:
        result = fetch_unadmitted_public_fixture(exact, client)
    assert result.transport_verified is True
    assert result.product_admitted is False


def test_empty_machine_preflight_rejects_existing_local_lake(
    tmp_path: Path,
) -> None:
    raw = payload()
    exact = pin(raw)
    lake = tmp_path / "lake"
    lake.mkdir()

    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: pytest.fail("transport issued")
            ),
            trust_env=False,
        ) as client,
        pytest.raises(ValueError, match="durable local lake"),
    ):
        fetch_empty_machine_fixture(exact, client, local_paths=(lake,))


def test_empty_machine_preflight_is_bounded_and_unadmitted(
    tmp_path: Path,
) -> None:
    raw = payload()
    exact = pin(raw)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/datasets/" in str(request.url):
            return httpx.Response(200, content=metadata())
        assert exact.revision in str(request.url)
        return httpx.Response(200, content=raw)

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Accept-Encoding": "identity"},
        trust_env=False,
    ) as client:
        result = fetch_empty_machine_fixture(
            exact, client, local_paths=(tmp_path / "absent-lake",)
        )

    assert result.bounded_fixture_ready is True
    assert result.durable_local_lake_present is False
    assert result.observation.transport_verified is True
    assert result.observation.product_admitted is False
    assert result.observation.checkpoint_complete is False


@pytest.mark.parametrize(
    "client_kwargs",
    [
        {"headers": {"Authorization": "Bearer secret"}},
        {"headers": {"Cookie": "session=secret"}},
        {"auth": ("user", "secret")},
        {"cookies": {"session": "secret"}},
    ],
)
def test_anonymous_fetch_rejects_inherited_credentials(client_kwargs) -> None:
    """No supplied client credential may enter an anonymous receipt path."""
    raw = payload()
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: pytest.fail("credentialled request issued")
            ),
            trust_env=False,
            **client_kwargs,
        ) as client,
        pytest.raises(ValueError, match="anonymous client"),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client)


@pytest.mark.parametrize("hook_kind", ["request", "response"])
def test_anonymous_fetch_rejects_client_hooks(hook_kind: str) -> None:
    """No client hook may inject credentials during a preflight sequence."""
    raw = payload()
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: pytest.fail("hooked request issued")
            ),
            event_hooks={hook_kind: [lambda _message: None]},
            trust_env=False,
        ) as client,
        pytest.raises(ValueError, match="anonymous client"),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client)


@pytest.mark.parametrize(
    "client_kwargs",
    [{"params": {"api_key": "secret"}}, {"follow_redirects": True}],
)
def test_anonymous_fetch_rejects_implicit_request_mutation(
    client_kwargs,
) -> None:
    """Defaults cannot bypass destination or anonymous-request validation."""
    raw = payload()
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: pytest.fail("mutated request issued")
            ),
            trust_env=False,
            **client_kwargs,
        ) as client,
        pytest.raises(ValueError, match="anonymous client"),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client)


def test_each_request_receives_only_the_remaining_shared_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata latency reduces the timeout available to the payload request."""
    raw = payload()
    exact = pin(raw)
    observed_timeouts: list[float] = []
    original_stream = httpx.Client.stream

    def recording_stream(self, method, url, **kwargs):
        observed_timeouts.append(kwargs["timeout"])
        return original_stream(self, method, url, **kwargs)

    clock = iter(float(value) for value in range(100, 112))
    monkeypatch.setattr(checkpoint.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(httpx.Client, "stream", recording_stream)

    def handler(request: httpx.Request) -> httpx.Response:
        content = metadata() if "/api/datasets/" in str(request.url) else raw
        return httpx.Response(200, content=content)

    with httpx.Client(
        transport=httpx.MockTransport(handler), trust_env=False
    ) as client:
        fetch_unadmitted_public_fixture(exact, client, timeout_seconds=10)

    assert len(observed_timeouts) == 2
    assert 0 < observed_timeouts[1] < observed_timeouts[0] <= 10


def test_anonymous_fetch_rejects_redirect_outside_allowlist() -> None:
    raw = payload()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "huggingface.co":
            return httpx.Response(
                302, headers={"location": "https://example.com/x"}
            )
        raise AssertionError("unsafe redirect was requested")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="destination"),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(302), "redirect missing"),
        (httpx.Response(503), "retrieval failed"),
        (
            httpx.Response(
                200,
                content=b"x",
                headers={"content-encoding": "gzip"},
            ),
            "encoding",
        ),
    ],
)
def test_anonymous_fetch_rejects_invalid_http_response(
    response: httpx.Response, message: str
) -> None:
    raw = payload()

    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _request: response)
        ) as client,
        pytest.raises(ValueError, match=message),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client)


def test_anonymous_fetch_rejects_nonpositive_timeout() -> None:
    raw = payload()
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _request: None)
        ) as client,
        pytest.raises(ValueError, match="timeout"),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client, timeout_seconds=0)


@pytest.mark.parametrize(
    "timeout_seconds", [float("inf"), float("-inf"), float("nan"), True, "30"]
)
def test_anonymous_fetch_rejects_nonfinite_or_boolean_timeout(
    timeout_seconds: object,
) -> None:
    raw = payload()
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _request: None)
        ) as client,
        pytest.raises(ValueError, match="finite positive"),
    ):
        fetch_unadmitted_public_fixture(
            pin(raw),
            client,
            timeout_seconds=timeout_seconds,  # type: ignore[arg-type]
        )


def test_anonymous_fetch_enforces_remote_byte_budget() -> None:
    raw = payload()

    def handler(request: httpx.Request) -> httpx.Response:
        content = (
            metadata()
            if "/api/datasets/" in str(request.url)
            else b"x" * (64 * 1024 + 1)
        )
        return httpx.Response(200, content=content)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="size exceeds budget"),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client)


def test_anonymous_fetch_enforces_redirect_limit() -> None:
    raw = payload()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": str(request.url)})

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="redirect limit"),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client)


@pytest.mark.parametrize("clock", [iter((0.0, 31.0)), iter((0.0, 0.0, 31.0))])
def test_anonymous_fetch_enforces_single_deadline(
    monkeypatch: pytest.MonkeyPatch, clock
) -> None:
    raw = payload()
    monkeypatch.setattr(checkpoint.time, "monotonic", lambda: next(clock))

    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, content=metadata())
            )
        ) as client,
        pytest.raises(ValueError, match="deadline"),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client, timeout_seconds=30)


def test_stream_stall_cannot_exceed_aggregate_deadline() -> None:
    """A body read stalled by its transport cannot extend the wall deadline."""
    raw = payload()

    class StalledStream(httpx.SyncByteStream):
        def __iter__(self):
            time.sleep(0.2)
            yield raw

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/datasets/" in str(request.url):
            return httpx.Response(200, content=metadata())
        return httpx.Response(200, stream=StalledStream())

    started = time.monotonic()
    with (
        httpx.Client(
            transport=httpx.MockTransport(handler), trust_env=False
        ) as client,
        pytest.raises(ValueError, match="deadline"),
    ):
        fetch_unadmitted_public_fixture(pin(raw), client, timeout_seconds=0.02)
    assert time.monotonic() - started < 0.15


def test_stream_transport_failure_is_preserved() -> None:
    """The deadline bridge must not relabel a transport failure as success."""

    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            raise RuntimeError("stream failed")
            yield b""  # pragma: no cover - preserves generator typing

    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, stream=BrokenStream())
            ),
            trust_env=False,
        ) as client,
        pytest.raises(RuntimeError, match="stream failed"),
    ):
        checkpoint._download(
            client,
            "https://huggingface.co/example",
            limit=10,
            deadline=time.monotonic() + 1,
        )
