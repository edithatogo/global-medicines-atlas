"""Tests for the MBS-only anonymous metadata reconciliation boundary."""

from __future__ import annotations

import httpx
import pytest
from scripts.reconcile_m112_raw_b2_metadata import (
    AUGUST_LIFECYCLE_REVISION,
    JULY_DATASET,
    MAX_METADATA_BYTES,
    MAX_REDIRECTS,
    manifest_summary,
    read_public_metadata,
    require_august_lifecycle_locator,
)


def test_manifest_summary_keeps_missing_metadata_paths_explicit() -> None:
    body = b'{"file_count":1,"files":[{"path":"bronze/present.json"}]}'
    assert manifest_summary(
        body, ("bronze/present.json", "bronze/absent.json")
    ) == (1, 1)


def test_raw_payload_paths_are_rejected_before_request() -> None:
    with pytest.raises(ValueError, match="only bounded metadata"):
        read_public_metadata(
            "edithatogo/australian-mbs-source-archive",
            "42d73b6facac016f14a335d36d83f1a3b630add8",
            "raw/mbs/release.xml",
        )


def test_metadata_reader_uses_exact_pinned_url() -> None:
    observed: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        observed.append(str(request.url))
        return httpx.Response(200, content=b"{}")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        status, body = read_public_metadata(
            "edithatogo/australian-mbs-source-archive",
            "42d73b6facac016f14a335d36d83f1a3b630add8",
            "bronze/receipts/au-mbs/receipt.json",
            client=client,
        )

    assert status == 200
    assert body == b"{}"
    assert observed == [
        "https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/resolve/42d73b6facac016f14a335d36d83f1a3b630add8/bronze/receipts/au-mbs/receipt.json"
    ]


def test_august_lifecycle_dataset_is_bound_by_root_readback() -> None:
    require_august_lifecycle_locator({
        "dataset": JULY_DATASET,
        "dataset_revision": AUGUST_LIFECYCLE_REVISION,
        "dataset_visibility": {"http_status": 200},
    })

    with pytest.raises(ValueError, match="not independently bound"):
        require_august_lifecycle_locator({
            "dataset": "edithatogo/global-medicines-atlas",
            "dataset_revision": AUGUST_LIFECYCLE_REVISION,
            "dataset_visibility": {"http_status": 200},
        })


@pytest.mark.parametrize("path", ["../raw/secret", "/manifest.json", "foo.txt"])
def test_metadata_reader_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError, match=r"safe relative|only bounded"):
        read_public_metadata(
            "edithatogo/australian-mbs-source-archive",
            "42d73b6facac016f14a335d36d83f1a3b630add8",
            path,
        )


def test_metadata_reader_stops_at_byte_limit() -> None:
    def respond(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (MAX_METADATA_BYTES + 1))

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(ValueError, match="byte bound"),
    ):
        read_public_metadata(
            "edithatogo/australian-mbs-source-archive",
            "42d73b6facac016f14a335d36d83f1a3b630add8",
            "manifest.json",
            client=client,
        )


def test_metadata_reader_enforces_redirect_limit() -> None:
    requests = 0

    def respond(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(302, headers={"location": "/next"})

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(ValueError, match="redirect bound"),
    ):
        read_public_metadata(
            "edithatogo/australian-mbs-source-archive",
            "42d73b6facac016f14a335d36d83f1a3b630add8",
            "manifest.json",
            client=client,
        )
    assert requests == MAX_REDIRECTS + 1
