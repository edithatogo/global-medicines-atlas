"""Primary MBS restore is bounded, value-free, and hosted-only in production."""

from __future__ import annotations

import gzip
import hashlib
import json

import httpx
import pytest
import scripts.verify_mbs_frozen_primary_restore as restore

PAYLOAD = b"synthetic public schedule bytes"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
URL = "https://huggingface.co/datasets/test/revision/object"


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(
        transport=handler, trust_env=False, follow_redirects=False
    )


def test_restore_reconstructs_exact_bytes_and_closes_memory_buffer() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=PAYLOAD)
    )
    with _client(transport) as client:
        result = restore.restore_in_memory(
            client, URL, expected_sha256=DIGEST, expected_bytes=len(PAYLOAD)
        )
    assert result == {
        "sha256": DIGEST,
        "byte_count": len(PAYLOAD),
        "restore_medium": "memory",
        "memory_buffer_closed": True,
        "source_values_interpreted_or_emitted": False,
        "source_payload_files_written": False,
    }
    assert PAYLOAD.decode() not in json.dumps(result)


@pytest.mark.parametrize(
    ("payload", "expected_size", "expected_digest", "message"),
    [
        (PAYLOAD, len(PAYLOAD) - 1, DIGEST, "exceeds byte bound"),
        (PAYLOAD, len(PAYLOAD) + 1, DIGEST, "byte count differs"),
        (PAYLOAD, len(PAYLOAD), "0" * 64, "digest differs"),
    ],
)
def test_restore_rejects_incorrect_bytes(
    payload: bytes, expected_size: int, expected_digest: str, message: str
) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=payload)
    )
    with _client(transport) as client, pytest.raises(ValueError, match=message):
        restore.restore_in_memory(
            client,
            URL,
            expected_sha256=expected_digest,
            expected_bytes=expected_size,
        )


def test_restore_rejects_redirect_outside_allowed_hosts() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(
            302, headers={"Location": "https://example.invalid/private"}
        )

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="unapproved hosted digest destination"),
    ):
        restore.restore_in_memory(
            client, URL, expected_sha256=DIGEST, expected_bytes=len(PAYLOAD)
        )
    assert requests == [URL]


def test_restore_rejects_non_identity_content_encoding() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={"Content-Encoding": "gzip"},
            content=gzip.compress(PAYLOAD),
        )
    )
    with (
        _client(transport) as client,
        pytest.raises(ValueError, match="encoding differs"),
    ):
        restore.restore_in_memory(
            client, URL, expected_sha256=DIGEST, expected_bytes=len(PAYLOAD)
        )


def test_hosted_restore_refuses_local_invocation_before_loading_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def unexpected() -> None:
        raise AssertionError("local invocation must not load source candidates")

    monkeypatch.setattr(restore.replays, "build", unexpected)
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        restore.hosted_restore(commit="a" * 40)


def test_hosted_restore_rejects_invalid_run_identity_before_loading_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "0")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")

    def unexpected() -> None:
        raise AssertionError("invalid hosted identity must not load candidates")

    monkeypatch.setattr(restore.replays, "build", unexpected)
    with pytest.raises(ValueError, match="missing run identity"):
        restore.hosted_restore(commit="a" * 40)
