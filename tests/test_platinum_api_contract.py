"""Tests for metadata-only, read-only Platinum API observations."""

from __future__ import annotations

import hashlib

import pytest

from global_medicines_atlas.http_content_negotiation import accepts_json
from global_medicines_atlas.platinum_api_contract import (
    ApiContractError,
    make_api_observation,
    observe_api_exchange,
)


@pytest.mark.parametrize(
    ("accept_header", "expected_acceptance"),
    [
        (None, "accepted"),
        ("", "accepted"),
        ("application/json", "accepted"),
        ("application/json;q=0.4, application/json;q=0.8", "accepted"),
        ("APPLICATION/JSON; charset=utf-8", "accepted"),
        ("application/*", "accepted"),
        ("*/*", "accepted"),
        ("text/html, application/json;q=0.8", "accepted"),
        ("application/json;q=0, */*;q=1", "rejected"),
        ("application/json;q=0.000, application/*;q=0.4", "rejected"),
        ("text/html", "rejected"),
        ("*/*;q=0", "rejected"),
        ("application/json;q=1.001", "rejected"),
        ("application/json;q=NaN", "rejected"),
        ("application/json;q=0.5;q=1", "rejected"),
        ("application/json; unsupported", "rejected"),
    ],
)
def test_json_accept_negotiation_obeys_media_specificity_and_quality(
    accept_header: str | None, expected_acceptance: str
) -> None:
    assert accepts_json(accept_header) is (expected_acceptance == "accepted")


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
def test_mutating_or_unscoped_requests_fail_closed(
    method: str, path: str
) -> None:
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


def test_transport_adapter_binds_completed_exchange_without_retaining_body() -> (
    None
):
    response_body = b'{"rows":[{"value":"fixture"}]}'
    observation = observe_api_exchange(
        method="GET",
        path="/api/v1/evidence",
        canonical_query=b'[["limit","1"]]',
        response_body=response_body,
        status_code=200,
        request_id="transport-test",
    )
    assert (
        observation.response_sha256 == hashlib.sha256(response_body).hexdigest()
    )
    assert response_body not in observation.canonical_bytes
    assert observation.path == "/api/v1/evidence"
