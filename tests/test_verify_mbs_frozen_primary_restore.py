"""Primary MBS restore is bounded, value-free, and hosted-only in production."""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

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


def test_hosted_restore_checks_all_exact_objects_and_records_only_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_SHA", commit)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    paths = ["raw/one.xml", "raw/two.xml", "raw/three.xml"]
    objects = [
        {
            "dataset": "test/dataset",
            "revision": "b" * 40,
            "path": path,
            "sha256": DIGEST,
            "byte_count": len(PAYLOAD),
            "status": "passed",
        }
        for path in paths
    ]
    monkeypatch.setattr(
        restore.replays,
        "build",
        lambda: {"summary": {"exact_replays_passed": 3}, "objects": objects},
    )
    requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, content=PAYLOAD)

    client = _client(httpx.MockTransport(respond))
    monkeypatch.setattr(restore.httpx, "Client", lambda **_kwargs: client)
    result = restore.hosted_restore(commit=commit)

    assert [item["path"] for item in result["objects"]] == paths
    assert len(requests) == 3
    assert all(
        url.startswith("https://huggingface.co/datasets/test/dataset/resolve/")
        for url in requests
    )
    assert all(
        item["sha256"] == DIGEST and item["memory_buffer_closed"]
        for item in result["objects"]
    )
    assert result["workflow_commit"] == commit
    assert result["workflow_run"] == "123"
    assert result["boundaries"] == {
        "primary_copy_only": True,
        "independent_recovery_established": False,
        "participant_or_cohort_data_accessed": False,
        "dataset_added_or_published": False,
        "v4_admission_or_consumer_canary": False,
    }
    assert PAYLOAD.decode() not in json.dumps(result)


def test_main_writes_metadata_receipt_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "receipt.json"
    monkeypatch.setattr(
        restore,
        "hosted_restore",
        lambda *, commit: {"objects": [], "commit": commit},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["restore", "--workflow-commit", "test", "--output", str(path)],
    )
    assert restore.main() == 0
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "objects": [],
        "commit": "test",
    }
    assert "restored 0 existing MBS objects" in capsys.readouterr().out
