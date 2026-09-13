"""Read-only Platinum coverage envelope over temporal coverage results."""

from __future__ import annotations

import hashlib
import json

from pydantic import AwareDatetime, Field

from .platinum_query import QueryReceipt
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
    query_receipt_sha256: Sha256


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
    response: CoverageResponse,
    identity: DatasetIdentityEnvelope,
    query_receipt: QueryReceipt,
) -> FederatedCoverageEnvelope:
    """Bind coverage to the exact resource proven by its query receipt.

    A source label alone is insufficient because an authority can publish
    several revisions.  The receipt is emitted by the verified resolver query
    path and binds the queried result to its immutable resource and admitted
    contract/semantic digests before this product envelope exposes identity.
    """
    envelope = build_coverage_envelope(response)
    if (
        query_receipt.resource_id != identity.resource_id
        or query_receipt.object_sha256 != identity.object_sha256
        or query_receipt.contract_sha256 != identity.contract_sha256
        or query_receipt.semantic_manifest_sha256
        != identity.semantic_manifest_sha256
    ):
        raise ValueError("query receipt differs from resource identity")
    if query_receipt.result_sha256 != envelope.page_sha256:
        raise ValueError("query receipt differs from coverage payload")
    for item in envelope.coverage:
        if item.jurisdiction != identity.jurisdiction:
            raise ValueError(
                "coverage jurisdiction differs from resource identity"
            )
        if item.provenance and any(
            link.source_id != identity.source_id for link in item.provenance
        ):
            raise ValueError(
                "coverage provenance differs from resource identity"
            )
    return FederatedCoverageEnvelope(
        **envelope.model_dump(),
        identity=identity,
        query_receipt_sha256=query_receipt.receipt_sha256,
    )


__all__ = [
    "CoverageEnvelope",
    "FederatedCoverageEnvelope",
    "bind_federated_coverage",
    "build_coverage_envelope",
]
