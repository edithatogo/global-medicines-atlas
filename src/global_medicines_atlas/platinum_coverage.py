"""Read-only Platinum coverage envelope over temporal coverage results."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from pydantic import AwareDatetime, Field

from .platinum_surface_contracts import PlatinumSurfaceModel, Sha256
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


__all__ = ["CoverageEnvelope", "CoverageLookup", "build_coverage_envelope"]
