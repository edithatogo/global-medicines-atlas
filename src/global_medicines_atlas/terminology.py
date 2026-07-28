"""Tiered RxNorm/RxNav-compatible terminology resolution."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Protocol, cast

import httpx
from pydantic import Field

from .models import FrozenModel, Provenance


class MatchMethod(StrEnum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    REMOTE = "remote"


class TerminologyMatch(FrozenModel):
    query: str = Field(min_length=1)
    normalized_query: str = Field(min_length=1)
    system: str = "http://www.nlm.nih.gov/research/umls/rxnorm"
    code: str = Field(min_length=1)
    display: str = Field(min_length=1)
    method: MatchMethod
    confidence: float = Field(ge=0, le=1)
    provenance: Provenance


class TerminologyResolver(Protocol):
    def resolve(self, query: str) -> tuple[TerminologyMatch, ...]: ...


def normalize_name(value: str) -> str:
    return re.sub(
        r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())
    ).strip()


def _string_mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    candidate = cast("Mapping[object, object]", value)
    if not all(isinstance(key, str) for key in candidate):
        return None
    return cast("Mapping[str, object]", value)


class LocalRxNormResolver:
    def __init__(self, concepts: Mapping[str, tuple[str, str]]) -> None:
        self._concepts = {
            normalize_name(alias): (rxcui, display)
            for alias, (rxcui, display) in concepts.items()
        }

    def resolve(self, query: str) -> tuple[TerminologyMatch, ...]:
        normalized = normalize_name(query)
        concept = self._concepts.get(normalized)
        if concept is None:
            return ()
        rxcui, display = concept
        return (
            TerminologyMatch(
                query=query,
                normalized_query=normalized,
                code=rxcui,
                display=display,
                method=(
                    MatchMethod.EXACT
                    if query.casefold() == display.casefold()
                    else MatchMethod.NORMALIZED
                ),
                confidence=1.0,
                provenance=Provenance(
                    source_id="rxnorm-bootstrap-fixture",
                    source_uri="local://fixtures/rxnorm-bootstrap-v1",
                    source_version="v1",
                    transformation="normalized-exact-match",
                ),
            ),
        )


class RxNavApiResolver:
    def __init__(
        self,
        *,
        base_url: str = "https://rxnav.nlm.nih.gov/REST",
        timeout_seconds: float = 3.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport,
            headers={"User-Agent": "global-medicines-atlas/0.1"},
        )

    def close(self) -> None:
        self._client.close()

    def resolve(self, query: str) -> tuple[TerminologyMatch, ...]:
        normalized = normalize_name(query)
        response = self._client.get(
            "/rxcui.json", params={"name": query, "search": 2}
        )
        response.raise_for_status()
        payload = _string_mapping(cast("object", response.json()))
        id_group = _string_mapping(payload.get("idGroup")) if payload else None
        ids_value = id_group.get("rxnormId") if id_group else None
        if not isinstance(ids_value, list):
            return ()
        ids = cast("list[object]", ids_value)
        return tuple(
            TerminologyMatch(
                query=query,
                normalized_query=normalized,
                code=str(rxcui),
                display=query,
                method=MatchMethod.REMOTE,
                confidence=0.9,
                provenance=Provenance(
                    source_id="nlm-rxnav-api",
                    source_uri=str(response.request.url),
                    transformation="findRxcuiByString-search-2",
                ),
            )
            for rxcui in ids
            if str(rxcui)
        )


class TieredResolver:
    def __init__(
        self,
        local: TerminologyResolver,
        remote: TerminologyResolver | None = None,
    ) -> None:
        self._local = local
        self._remote = remote

    def resolve(self, query: str) -> tuple[TerminologyMatch, ...]:
        local = self._local.resolve(query)
        if local or self._remote is None:
            return local
        try:
            return self._remote.resolve(query)
        except httpx.HTTPError, TimeoutError:
            return ()


def bootstrap_rxnorm_resolver(
    remote: TerminologyResolver | None = None,
) -> TieredResolver:
    fixture_path = Path(__file__).with_name("data") / "rxnorm_bootstrap.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    concepts = {
        alias: (values[0], values[1])
        for alias, values in payload["concepts"].items()
    }
    return TieredResolver(LocalRxNormResolver(concepts), remote)
