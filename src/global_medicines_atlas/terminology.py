"""Tiered RxNorm/RxNav-compatible terminology resolution."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, cast

import httpx
from pydantic import AnyUrl, Field

from .models import FrozenModel, Provenance
from .receipts import RightsState
from .rxnorm_lineage import (
    RxNormEndpointClass,
    RxNormLineage,
    RxNormQueryMethod,
)


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
    lineage: RxNormLineage
    candidate_only: Literal[True] = True


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
    def __init__(
        self,
        concepts: Mapping[str, tuple[str, str]],
        *,
        release_identity: str = "bootstrap-v1",
        source_uri: str = "local://fixtures/rxnorm-bootstrap-v1",
        retrieved_at: datetime | None = None,
        rights_state: RightsState = RightsState.UNKNOWN,
        rights_reference: AnyUrl | None = None,
        payload: bytes | None = None,
    ) -> None:
        self._concepts = {
            normalize_name(alias): (rxcui, display)
            for alias, (rxcui, display) in concepts.items()
        }
        self._source_uri = source_uri
        canonical_payload = (
            payload
            or json.dumps(
                concepts,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        )
        self._lineage = RxNormLineage.from_payload(
            payload=canonical_payload,
            release_identity=release_identity,
            query_method=RxNormQueryMethod.NORMALIZED_EXACT,
            endpoint_class=RxNormEndpointClass.LOCAL_FIXTURE,
            source_uri=source_uri,
            retrieved_at=retrieved_at or datetime(1970, 1, 1, tzinfo=UTC),
            rights_state=rights_state,
            rights_reference=rights_reference,
        )

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
                    source_uri=self._source_uri,
                    retrieved_at=self._lineage.retrieved_at,
                    source_sha256=self._lineage.payload_sha256,
                    source_version=self._lineage.release_identity,
                    transformation="normalized-exact-match",
                ),
                lineage=self._lineage,
            ),
        )


class RxNavApiResolver:
    def __init__(
        self,
        *,
        base_url: str = "https://rxnav.nlm.nih.gov/REST",
        timeout_seconds: float = 3.0,
        transport: httpx.BaseTransport | None = None,
        endpoint_class: RxNormEndpointClass = (
            RxNormEndpointClass.PUBLIC_RXNAV
        ),
        release_identity: str = "unverified-current",
        rights_state: RightsState = RightsState.UNKNOWN,
        rights_reference: AnyUrl | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport,
            headers={"User-Agent": "global-medicines-atlas/0.1"},
        )
        self._endpoint_class = endpoint_class
        self._release_identity = release_identity
        self._rights_state = rights_state
        self._rights_reference = rights_reference

    def close(self) -> None:
        self._client.close()

    def resolve(self, query: str) -> tuple[TerminologyMatch, ...]:
        normalized = normalize_name(query)
        response = self._client.get(
            "/rxcui.json", params={"name": query, "search": 2}
        )
        response.raise_for_status()
        response_bytes = response.content
        payload = _string_mapping(cast("object", response.json()))
        id_group = _string_mapping(payload.get("idGroup")) if payload else None
        ids_value = id_group.get("rxnormId") if id_group else None
        if not isinstance(ids_value, list):
            return ()
        ids = cast("list[object]", ids_value)
        retrieved_at = datetime.now(UTC)
        lineage = RxNormLineage.from_payload(
            payload=response_bytes,
            release_identity=self._release_identity,
            query_method=RxNormQueryMethod.FIND_RXCUI_BY_STRING,
            endpoint_class=self._endpoint_class,
            source_uri=str(response.request.url),
            retrieved_at=retrieved_at,
            rights_state=self._rights_state,
            rights_reference=self._rights_reference,
        )
        return tuple(
            TerminologyMatch(
                query=query,
                normalized_query=normalized,
                code=str(rxcui),
                display=query,
                method=MatchMethod.REMOTE,
                confidence=0.9,
                provenance=Provenance(
                    source_id=(
                        "local-rxnav-compatible"
                        if self._endpoint_class
                        is RxNormEndpointClass.LOCAL_RXNAV
                        else "nlm-rxnav-api"
                    ),
                    source_uri=str(response.request.url),
                    retrieved_at=retrieved_at,
                    source_sha256=lineage.payload_sha256,
                    source_version=self._release_identity,
                    transformation="findRxcuiByString-search-2",
                ),
                lineage=lineage,
            )
            for rxcui in ids
            if str(rxcui)
        )


class TieredResolver:
    def __init__(
        self,
        local: TerminologyResolver,
        local_rxnav: TerminologyResolver | None = None,
        public_rxnav: TerminologyResolver | None = None,
    ) -> None:
        self._local = local
        self._fallbacks = tuple(
            resolver
            for resolver in (local_rxnav, public_rxnav)
            if resolver is not None
        )

    def resolve(self, query: str) -> tuple[TerminologyMatch, ...]:
        local = self._local.resolve(query)
        if local:
            return local
        for resolver in self._fallbacks:
            try:
                matches = resolver.resolve(query)
            except httpx.HTTPError, TimeoutError:
                continue
            if matches:
                return matches
        return ()


def bootstrap_rxnorm_resolver(
    local_rxnav: TerminologyResolver | None = None,
    public_rxnav: TerminologyResolver | None = None,
) -> TieredResolver:
    fixture_path = Path(__file__).with_name("data") / "rxnorm_bootstrap.json"
    payload_bytes = fixture_path.read_bytes()
    payload = json.loads(payload_bytes)
    concepts = {
        alias: (values[0], values[1])
        for alias, values in payload["concepts"].items()
    }
    local = LocalRxNormResolver(
        concepts,
        release_identity=str(payload["fixture_version"]),
        payload=payload_bytes,
    )
    return TieredResolver(local, local_rxnav, public_rxnav)
