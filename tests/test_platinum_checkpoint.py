"""Tests for fail-closed public-fixture checkpoint preflight."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import replace

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import global_medicines_atlas.platinum_checkpoint as checkpoint
from global_medicines_atlas.platinum_checkpoint import (
    PublicFixturePin,
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
    ) as client:
        result = fetch_unadmitted_public_fixture(exact, client)
    assert result.transport_verified is True
    assert result.product_admitted is False


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
