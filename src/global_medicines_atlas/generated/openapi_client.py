"""Generated read-only client. Regenerate; do not edit."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, cast
from urllib.parse import quote

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type QueryScalar = str | int | float | bool
type QueryValue = QueryScalar | Sequence[QueryScalar] | None
type QueryPairs = tuple[tuple[str, str], ...]
_HTTP_SUCCESS_MIN = 200
_HTTP_SUCCESS_LIMIT = 300


class ReadOnlyTransport(Protocol):
    """Transport boundary used by generated client methods."""

    def request(
        self, method: str, path: str, query: Sequence[tuple[str, str]]
    ) -> JsonValue: ...


class ClientResponse(Protocol):
    """Minimal response shape shared by HTTPX and FastAPI TestClient."""

    status_code: int

    def json(self) -> object: ...


class RequestClient(Protocol):
    """Minimal synchronous HTTP client accepted by ClientTransport."""

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Sequence[tuple[str, str]],
    ) -> ClientResponse: ...


class ClientTransportError(RuntimeError):
    """A generated client request returned a non-success response."""


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        values = cast("list[object]", value)
        return [_json_value(item) for item in values]
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        result: dict[str, JsonValue] = {}
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            result[key] = _json_value(item)
        return result
    raise TypeError(f"unsupported JSON response value: {type(value).__name__}")


def _query_scalar(value: QueryScalar) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _query(values: Sequence[tuple[str, QueryValue]]) -> QueryPairs:
    pairs: list[tuple[str, str]] = []
    for key, value in values:
        if value is None:
            continue
        if isinstance(value, str | int | float | bool):
            pairs.append((key, _query_scalar(value)))
            continue
        pairs.extend((key, _query_scalar(item)) for item in value)
    return tuple(pairs)


class ClientTransport:
    """HTTPX/FastAPI-TestClient-compatible synchronous transport."""

    def __init__(self, client: RequestClient) -> None:
        self._client = client

    def request(
        self, method: str, path: str, query: Sequence[tuple[str, str]]
    ) -> JsonValue:
        response = self._client.request(method, path, params=query)
        if not _HTTP_SUCCESS_MIN <= response.status_code < _HTTP_SUCCESS_LIMIT:
            raise ClientTransportError(
                f"{method} {path} returned HTTP {response.status_code}"
            )
        return _json_value(response.json())


class GlobalMedicinesAtlasClient:
    """Typed methods generated from committed read-only operations."""

    def __init__(self, transport: ReadOnlyTransport) -> None:
        self._transport = transport

    def comparisons_api_v1_comparisons_get(
        self,
        *,
        concept_id: str,
        cursor: str | None = None,
        dimensions: Sequence[Literal["regulatory", "funding", "formulary"]]
        | None = None,
        jurisdictions: Sequence[str],
        limit: int | None = None,
        observed_at: str,
        valid_at: str,
    ) -> JsonValue:
        path = "/api/v1/comparisons"
        query = _query((
            ("concept_id", concept_id),
            ("cursor", cursor),
            ("dimensions", dimensions),
            ("jurisdictions", jurisdictions),
            ("limit", limit),
            ("observed_at", observed_at),
            ("valid_at", valid_at),
        ))
        return self._transport.request("GET", path, query)

    def concepts_api_v1_concepts_get(
        self,
        *,
        cursor: str | None = None,
        jurisdictions: Sequence[str] | None = None,
        limit: int | None = None,
        q: str,
    ) -> JsonValue:
        path = "/api/v1/concepts"
        query = _query((
            ("cursor", cursor),
            ("jurisdictions", jurisdictions),
            ("limit", limit),
            ("q", q),
        ))
        return self._transport.request("GET", path, query)

    def concept_detail_api_v1_concepts__concept_id__get(
        self,
        *,
        concept_id: str,
    ) -> JsonValue:
        encoded_concept_id = quote(str(concept_id), safe="")
        path = f"/api/v1/concepts/{encoded_concept_id}"
        query = _query(())
        return self._transport.request("GET", path, query)

    def coverage_api_v1_coverage_get(
        self,
        *,
        cursor: str | None = None,
        dimensions: Sequence[Literal["regulatory", "funding", "formulary"]]
        | None = None,
        jurisdictions: Sequence[str],
        limit: int | None = None,
        observed_at: str,
        valid_at: str,
    ) -> JsonValue:
        path = "/api/v1/coverage"
        query = _query((
            ("cursor", cursor),
            ("dimensions", dimensions),
            ("jurisdictions", jurisdictions),
            ("limit", limit),
            ("observed_at", observed_at),
            ("valid_at", valid_at),
        ))
        return self._transport.request("GET", path, query)

    def evidence_api_v1_evidence_get(
        self,
        *,
        assertion_id: str | None = None,
        concept_id: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
        observed_at: str,
        valid_at: str,
    ) -> JsonValue:
        path = "/api/v1/evidence"
        query = _query((
            ("assertion_id", assertion_id),
            ("concept_id", concept_id),
            ("cursor", cursor),
            ("limit", limit),
            ("observed_at", observed_at),
            ("valid_at", valid_at),
        ))
        return self._transport.request("GET", path, query)

    def health_api_v1_health_get(
        self,
    ) -> JsonValue:
        path = "/api/v1/health"
        query = _query(())
        return self._transport.request("GET", path, query)

    def jurisdictions_api_v1_jurisdictions_get(
        self,
    ) -> JsonValue:
        path = "/api/v1/jurisdictions"
        query = _query(())
        return self._transport.request("GET", path, query)

    def readiness_api_v1_readiness_get(
        self,
    ) -> JsonValue:
        path = "/api/v1/readiness"
        query = _query(())
        return self._transport.request("GET", path, query)

    def sources_api_v1_sources_get(
        self,
        *,
        jurisdiction: str | None = None,
    ) -> JsonValue:
        path = "/api/v1/sources"
        query = _query((("jurisdiction", jurisdiction),))
        return self._transport.request("GET", path, query)


__all__ = [
    "ClientTransport",
    "ClientTransportError",
    "GlobalMedicinesAtlasClient",
    "JsonValue",
    "ReadOnlyTransport",
]
