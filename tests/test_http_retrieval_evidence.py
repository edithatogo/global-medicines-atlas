"""HTTP acquisition receipts are evidence-grade and never store secrets."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from tests.test_source_acquisition import acquire
from tests.test_source_receipts import retrieval

from global_medicines_atlas.receipts import (
    HttpRetrievalEvidence,
    SourceReceipt,
    http_retrieval_from_response,
    redact_http_headers,
)
from global_medicines_atlas.version import __version__

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/http-retrieval-evidence-v1.json"
PAYLOAD = b"governed fixture"


@pytest.mark.unit
def test_sensitive_headers_are_omitted_not_redacted_in_place() -> None:
    cleaned = redact_http_headers({
        "Authorization": "Bearer super-secret",
        "X-Api-Key": "abc123",
        "Cookie": "session=1",
        "ETag": '"abc"',
        "Content-Type": "application/zip",
        "Last-Modified": "Wed, 19 Aug 2026 00:00:00 GMT",
    })
    blob = json.dumps(cleaned)
    assert "Bearer" not in blob
    assert "super-secret" not in blob
    assert "abc123" not in blob
    assert "session=1" not in blob
    assert cleaned["etag"] == '"abc"'
    assert "authorization" not in cleaned
    assert "cookie" not in cleaned


@pytest.mark.unit
def test_http_fields_are_optional_when_not_supplied() -> None:
    evidence = HttpRetrievalEvidence(
        original_uri="https://example.test/a",
    )
    assert evidence.final_uri is None
    assert evidence.redirect_history == ()
    assert evidence.http_method is None
    assert evidence.http_status is None
    assert evidence.etag is None
    assert evidence.last_modified is None
    assert evidence.content_type is None
    assert evidence.content_encoding is None
    assert evidence.content_length is None
    assert evidence.observed_byte_length is None
    assert evidence.source_native_version is None
    assert evidence.source_native_date is None
    assert evidence.acquisition_agent_version is None


@pytest.mark.unit
def test_http_retrieval_canonical_json_is_deterministic() -> None:
    first = HttpRetrievalEvidence(
        original_uri="https://example.test/a",
        final_uri="https://example.test/b",
        redirect_history=("https://example.test/a",),
        http_method="GET",
        http_status=200,
        etag='"1"',
        observed_byte_length=12,
        acquisition_agent_version="1.0.0",
    )
    second = HttpRetrievalEvidence.model_validate(
        dict(reversed(list(first.model_dump(mode="json").items())))
    )
    assert first.canonical_json() == second.canonical_json()
    assert first.digest() == second.digest()


@pytest.mark.unit
def test_http_schema_accepts_optional_evidence() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        HttpRetrievalEvidence(
            original_uri="https://example.test/a",
        ).model_dump(mode="json")
    )


@pytest.mark.unit
def test_acquire_source_records_http_evidence_and_payload_digest(
    tmp_path: Path,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/zip; charset=utf-8",
                "etag": '"v1"',
                "last-modified": "Wed, 19 Aug 2026 00:00:00 GMT",
                "content-encoding": "identity",
                "content-length": str(len(PAYLOAD)),
            },
            content=PAYLOAD,
        )

    receipt = acquire(tmp_path, handler)
    assert isinstance(receipt, SourceReceipt)
    http = receipt.retrieval.http
    assert http is not None
    assert str(http.original_uri).rstrip("/") == (
        "https://example.test/medicines.zip"
    )
    assert http.http_method == "GET"
    assert http.http_status == 200
    assert http.etag == '"v1"'
    assert http.last_modified == "Wed, 19 Aug 2026 00:00:00 GMT"
    assert http.content_type == "application/zip"
    assert http.content_encoding == "identity"
    assert http.content_length == len(PAYLOAD)
    assert http.observed_byte_length == len(PAYLOAD)
    assert http.acquisition_agent_version == __version__
    assert receipt.payload.matches(PAYLOAD)
    encoded = receipt.canonical_json().decode()
    assert "secret-token" not in encoded
    assert "Bearer" not in encoded


@pytest.mark.unit
def test_redirect_history_uses_original_and_final_uri() -> None:
    request = httpx.Request("GET", "https://example.test/start")
    redirected = httpx.Response(
        302,
        headers={"location": "https://cdn.example.test/final"},
        request=request,
    )
    final = httpx.Response(
        200,
        headers={"content-type": "application/json", "etag": '"n"'},
        content=b"{}",
        request=httpx.Request("GET", "https://cdn.example.test/final"),
        history=[redirected],
    )
    evidence = http_retrieval_from_response(
        final,
        original_uri="https://example.test/start",
        observed_byte_length=2,
        agent_version="0+test",
    )
    assert str(evidence.original_uri).rstrip("/") == (
        "https://example.test/start"
    )
    assert str(evidence.final_uri).rstrip("/") == (
        "https://cdn.example.test/final"
    )
    history = tuple(str(item).rstrip("/") for item in evidence.redirect_history)
    assert history == ("https://example.test/start",)
    dumped = json.dumps(evidence.model_dump(mode="json"))
    assert "authorization" not in dumped.lower()


@pytest.mark.unit
def test_unknown_and_non_numeric_headers_are_dropped() -> None:
    cleaned = redact_http_headers({
        "X-Request-Id": "trace-1",
        "Content-Length": "not-a-number",
        "ETag": '"keep"',
    })
    assert "x-request-id" not in cleaned
    assert cleaned["etag"] == '"keep"'
    request = httpx.Request("GET", "https://example.test/a")
    response = httpx.Response(
        200,
        headers={"content-length": "not-a-number", "etag": '"keep"'},
        content=b"{}",
        request=request,
    )
    evidence = http_retrieval_from_response(
        response,
        original_uri="https://example.test/a",
        observed_byte_length=2,
        agent_version="0+test",
    )
    assert evidence.content_length is None
    assert evidence.etag == '"keep"'


@pytest.mark.edge
def test_http_evidence_forbids_unknown_secret_fields() -> None:
    with pytest.raises(ValidationError):
        HttpRetrievalEvidence.model_validate({
            "original_uri": "https://example.test/a",
            "authorization": "Bearer leaked",
        })


@pytest.mark.property
@given(st.text(min_size=1, max_size=40))
def test_authorization_values_never_enter_retrieval_json(secret: str) -> None:
    cleaned = redact_http_headers({
        "Authorization": f"Bearer {secret}",
        "ETag": '"ok"',
    })
    dumped = json.dumps(cleaned)
    assert f"Bearer {secret}" not in dumped
    assert "Authorization" not in dumped
    evidence = retrieval()
    assert evidence.http is None
