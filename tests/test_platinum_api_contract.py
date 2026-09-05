"""Tests for metadata-only, read-only Platinum API observations."""

from __future__ import annotations

import hashlib

import pytest

from global_medicines_atlas.platinum_api_contract import (
    ApiContractError,
    make_api_observation,
)


def test_observation_is_deterministic_and_excludes_response_payload() -> None:
    response = b'{"rows":[{"secret":"payload"}]}'
    observation = make_api_observation(
        method="GET",
        path="/api/v1/evidence",
        canonical_query=b'[["limit","1"]]',
        response_bytes=response,
        status_code=200,
        request_id="api-test",
    )
    assert observation.response_sha256 == hashlib.sha256(response).hexdigest()
    assert observation.canonical_bytes == observation.canonical_bytes
    assert b"secret" not in observation.canonical_bytes
    assert len(observation.observation_sha256) == 64


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/v1/evidence"),
        ("GET", "https://example.test/api/v1/evidence"),
        ("GET", "/api/v1/evidence?secret=x"),
    ],
)
def test_mutating_or_unscoped_requests_fail_closed(method: str, path: str) -> None:
    with pytest.raises(ApiContractError):
        make_api_observation(
            method=method,
            path=path,
            canonical_query=b"",
            response_bytes=b"{}",
            status_code=200,
            request_id="api-test",
        )


def test_invalid_request_identity_and_status_fail_closed() -> None:
    with pytest.raises(ApiContractError, match="request id"):
        make_api_observation(
            method="GET",
            path="/api/v1/health",
            canonical_query=b"",
            response_bytes=b"{}",
            status_code=200,
            request_id="é",
        )
    with pytest.raises(ApiContractError, match="status"):
        make_api_observation(
            method="HEAD",
            path="/api/v1/health",
            canonical_query=b"",
            response_bytes=b"{}",
            status_code=99,
            request_id="api-test",
        )
