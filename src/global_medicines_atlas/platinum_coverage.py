"""Read-only Platinum coverage envelope over temporal coverage results."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from pydantic import AwareDatetime, Field

from .platinum_surface_contracts import (
    DatasetIdentityEnvelope,
    PlatinumSurfaceModel,
    Sha256,
)
from .product_contracts import AsOfClocks, CoverageItem, CoverageResponse


class CoverageEnvelope(PlatinumSurfaceModel):
    """A bounded coverage page whose absence never means non-coverage."""

    schema_version: str = "1.0"
    generated_at: AwareDatetime
    clocks: AsOfClocks
    coverage: tuple[CoverageItem, ...]
    page_limit: int = Field(ge=1)
    next_cursor: str | None = None
    page_sha256: Sha256
    coverage_complete: bool = False
    missing_coverage_is_negative_evidence: bool = False
    temporal_selection: str = "valid_and_observed_half_open"


class FederatedCoverageEnvelope(CoverageEnvelope):
    """Coverage that is explicitly bound to one admitted dataset identity."""

    identity: DatasetIdentityEnvelope


class CoverageLookup(Protocol):
    def coverage(self, query: object) -> CoverageResponse: ...


def _digest(response: CoverageResponse) -> str:
    payload = {
        "clocks": response.metadata.clocks.model_dump(mode="json"),
        "coverage": [
            item.model_dump(mode="json") for item in response.coverage
        ],
        "page": response.metadata.page.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_coverage_envelope(response: CoverageResponse) -> CoverageEnvelope:
    """Translate an existing temporal response without adding source claims."""
    if response.metadata.page.returned != len(response.coverage):
        raise ValueError("returned count must match coverage")
    return CoverageEnvelope(
        generated_at=response.metadata.generated_at,
        clocks=response.metadata.clocks,
        coverage=response.coverage,
        page_limit=response.metadata.page.limit,
        next_cursor=response.metadata.page.next_cursor,
        page_sha256=_digest(response),
    )


def bind_federated_coverage(
    response: CoverageResponse, identity: DatasetIdentityEnvelope
) -> FederatedCoverageEnvelope:
    """Bind a coverage page only when every item cites the admitted source."""
    envelope = build_coverage_envelope(response)
    for item in envelope.coverage:
        if item.jurisdiction != identity.jurisdiction:
            raise ValueError(
                "coverage jurisdiction differs from resource identity"
            )
        if not item.provenance or any(
            link.source_id != identity.source_id for link in item.provenance
        ):
            raise ValueError(
                "coverage provenance differs from resource identity"
            )
    return FederatedCoverageEnvelope(**envelope.model_dump(), identity=identity)


__all__ = [
    "CoverageEnvelope",
    "CoverageLookup",
    "FederatedCoverageEnvelope",
    "bind_federated_coverage",
    "build_coverage_envelope",
]
