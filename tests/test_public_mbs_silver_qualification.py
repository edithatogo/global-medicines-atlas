"""Hosted-only public MBS candidate qualifier controls."""

from __future__ import annotations

import hashlib
from functools import partial
from typing import Any, cast

import httpx
import pytest
from scripts import qualify_public_mbs_silver as command


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):
        yield self.payload


class _Client:
    def __init__(self, payload: bytes, **kwargs: object) -> None:
        assert kwargs["follow_redirects"] is True
        assert kwargs["trust_env"] is False
        assert isinstance(kwargs["timeout"], httpx.Timeout)
        assert kwargs["timeout"].read == 60
        assert kwargs["transport"] is not None
        self.payload = payload

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def stream(self, method: str, url: str) -> _Response:
        assert method == "GET"
        assert url == command.SOURCE_URI
        return _Response(self.payload)


def _client_factory(payload: bytes) -> Any:
    return cast("Any", partial(_Client, payload))


def test_qualifies_only_digest_bound_public_bytes_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(command.httpx, "Client", _client_factory(payload))

    result = command.qualify()

    qualification = cast("dict[str, object]", result["qualification"])
    assert qualification["source_record_count"] == 1
    tables = cast("list[dict[str, object]]", qualification["tables"])
    assert sum(cast("int", table["field_count"]) for table in tables) == 40
    assert qualification["promotion_status"] == "candidate_only"
    assert qualification["blockers"] == [
        "public_v4_identity_unverified",
        "real_source_era_unqualified",
    ]
    assert result["publication_performed"] is False
    assert result["source_bytes_retained"] is False
    assert "payload" not in result


@pytest.mark.parametrize(
    ("actual_bytes", "expected_bytes", "expected_sha", "message"),
    [
        (b"abc", 4, hashlib.sha256(b"abc").hexdigest(), "byte count"),
        (b"abc", 3, "0" * 64, "digest"),
    ],
)
def test_rejects_public_object_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
    actual_bytes: bytes,
    expected_bytes: int,
    expected_sha: str,
    message: str,
) -> None:
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", expected_bytes)
    monkeypatch.setattr(command, "LEGACY_MBS_SHA256", expected_sha)
    monkeypatch.setattr(command.httpx, "Client", _client_factory(actual_bytes))

    with pytest.raises(ValueError, match=message):
        command.qualify()


def test_workflow_is_exact_main_read_only_and_never_publishes() -> None:
    workflow = (
        command.ROOT
        / ".github/workflows/australian-mbs-silver-qualification.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "REQUESTED_COMMIT" in workflow
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in workflow
    assert "permissions: {}" in workflow
    assert "contents: read" in workflow
    assert "issue" not in workflow.lower()
    assert "publish" not in workflow.lower()
    assert "source-retained" not in workflow.lower()
