"""Generated read-only client. Regenerate; do not edit."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


class ReadOnlyTransport(Protocol):
    """Transport boundary used by generated client methods."""

    def request(
        self, method: str, path: str, query: Mapping[str, str]
    ) -> JsonValue: ...


def _query(values: Mapping[str, str | int | None]) -> dict[str, str]:
    return {
        key: str(value) for key, value in values.items() if value is not None
    }


class GlobalMedicinesAtlasClient:
    """Typed methods generated from committed read-only operations."""

    def __init__(self, transport: ReadOnlyTransport) -> None:
        self._transport = transport

    def comparisons_api_v1_comparisons_get(
        self,
        *,
        concept_id: str | int,
        cursor: str | int | None = None,
        dimensions: str | int | None = None,
        jurisdictions: str | int,
        limit: str | int | None = None,
        observed_at: str | int,
        valid_at: str | int,
    ) -> JsonValue:
        path = "/api/v1/comparisons"
        query = _query({
            "concept_id": concept_id,
            "cursor": cursor,
            "dimensions": dimensions,
            "jurisdictions": jurisdictions,
            "limit": limit,
            "observed_at": observed_at,
            "valid_at": valid_at,
        })
        return self._transport.request("GET", path, query)

    def concepts_api_v1_concepts_get(
        self,
        *,
        cursor: str | int | None = None,
        jurisdictions: str | int | None = None,
        limit: str | int | None = None,
        q: str | int,
    ) -> JsonValue:
        path = "/api/v1/concepts"
        query = _query({
            "cursor": cursor,
            "jurisdictions": jurisdictions,
            "limit": limit,
            "q": q,
        })
        return self._transport.request("GET", path, query)

    def concept_detail_api_v1_concepts__concept_id__get(
        self,
        *,
        concept_id: str,
    ) -> JsonValue:
        path = f"/api/v1/concepts/{concept_id}"
        query = _query({})
        return self._transport.request("GET", path, query)

    def coverage_api_v1_coverage_get(
        self,
        *,
        cursor: str | int | None = None,
        dimensions: str | int | None = None,
        jurisdictions: str | int,
        limit: str | int | None = None,
        observed_at: str | int,
        valid_at: str | int,
    ) -> JsonValue:
        path = "/api/v1/coverage"
        query = _query({
            "cursor": cursor,
            "dimensions": dimensions,
            "jurisdictions": jurisdictions,
            "limit": limit,
            "observed_at": observed_at,
            "valid_at": valid_at,
        })
        return self._transport.request("GET", path, query)

    def evidence_api_v1_evidence_get(
        self,
        *,
        assertion_id: str | int | None = None,
        concept_id: str | int | None = None,
        cursor: str | int | None = None,
        limit: str | int | None = None,
        observed_at: str | int,
        valid_at: str | int,
    ) -> JsonValue:
        path = "/api/v1/evidence"
        query = _query({
            "assertion_id": assertion_id,
            "concept_id": concept_id,
            "cursor": cursor,
            "limit": limit,
            "observed_at": observed_at,
            "valid_at": valid_at,
        })
        return self._transport.request("GET", path, query)

    def health_api_v1_health_get(
        self,
    ) -> JsonValue:
        path = "/api/v1/health"
        query = _query({})
        return self._transport.request("GET", path, query)

    def jurisdictions_api_v1_jurisdictions_get(
        self,
    ) -> JsonValue:
        path = "/api/v1/jurisdictions"
        query = _query({})
        return self._transport.request("GET", path, query)

    def readiness_api_v1_readiness_get(
        self,
    ) -> JsonValue:
        path = "/api/v1/readiness"
        query = _query({})
        return self._transport.request("GET", path, query)

    def sources_api_v1_sources_get(
        self,
        *,
        jurisdiction: str | int | None = None,
    ) -> JsonValue:
        path = "/api/v1/sources"
        query = _query({
            "jurisdiction": jurisdiction,
        })
        return self._transport.request("GET", path, query)


__all__ = ["GlobalMedicinesAtlasClient", "JsonValue", "ReadOnlyTransport"]
