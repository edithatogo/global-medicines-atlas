"""Bounded source-structure evidence reads for the additive Platinum surface."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Literal, Protocol

from pydantic import Field

from .platinum_identity_service import (
    ResolverDatasetIdentityService,
    UnknownPlatinumResourceError,
)
from .platinum_query import PlatinumQueryService, QuerySpec, Scalar
from .platinum_resolver import StorageNeutralResolver
from .platinum_surface_contracts import (
    DatasetIdentityV2Envelope,
    PlatinumSurfaceModel,
)

Column = str


class SourceStructureQuery(PlatinumSurfaceModel):
    """Small projection and limit for a pinned structural evidence object."""

    columns: tuple[Column, ...] = Field(min_length=1, max_length=64)
    limit: int = Field(default=100, ge=1, le=100)
    offline: bool = False


class SourceStructurePage(PlatinumSurfaceModel):
    """Source-structure rows paired with exact v2 identity and query receipt."""

    status: Literal["available", "unavailable"]
    identity: DatasetIdentityV2Envelope
    rows: tuple[dict[str, Scalar], ...] = ()
    query_sha256: str
    query_receipt_sha256: str | None
    query_receipt_json: str
    reason: str | None
    coverage_state: Literal["not_declared"] = "not_declared"
    comparison_validity: Literal["not_evaluated"] = "not_evaluated"


class SourceStructureService:
    """Read only an already-admitted source-structure resource via resolver."""

    def __init__(
        self,
        resolver: StorageNeutralResolver,
        *,
        jurisdictions: Mapping[str, str],
    ) -> None:
        self._resolver = resolver
        self._identities = ResolverDatasetIdentityService(
            resolver, jurisdictions=jurisdictions
        )

    def query(
        self, resource_id: str, query: SourceStructureQuery
    ) -> SourceStructurePage:
        """Verify v2 structure identity before returning bounded source rows."""
        identity = self._identities.identity_v2(resource_id)
        if identity.semantic_dimension != "source_structure":
            raise ValueError("resource is not source-structure evidence")
        result = PlatinumQueryService(self._resolver).query_state(
            resource_id,
            engine="polars",
            spec=QuerySpec(columns=query.columns, limit=query.limit),
            offline=query.offline,
        )
        if result.status == "unavailable":
            receipt_document = json.loads(result.canonical_bytes)
            receipt_document["receipt_sha256"] = result.receipt_sha256
            return SourceStructurePage(
                status="unavailable",
                identity=identity,
                query_sha256=result.query_sha256,
                query_receipt_sha256=result.receipt_sha256,
                query_receipt_json=json.dumps(
                    receipt_document, sort_keys=True, separators=(",", ":")
                ),
                reason=result.reason,
            )
        if (
            result.evidence.object_sha256 != identity.object_sha256
            or result.evidence.semantic_dimension != identity.semantic_dimension
        ):
            raise ValueError("query result identity differs from v2 identity")
        receipt = result.query_receipt
        receipt_document = {
            "cache_receipt_sha256": receipt.cache_receipt_sha256,
            "canonical_query": receipt.canonical_query.decode("utf-8"),
            "contract_sha256": receipt.contract_sha256,
            "engine": receipt.engine,
            "object_sha256": receipt.object_sha256,
            "query_sha256": receipt.query_sha256,
            "receipt_sha256": receipt.receipt_sha256,
            "resource_id": receipt.resource_id,
            "result_sha256": receipt.result_sha256,
            "row_count": receipt.row_count,
            "semantic_manifest_sha256": receipt.semantic_manifest_sha256,
            "version": "1.0",
        }
        return SourceStructurePage(
            status="available",
            identity=identity,
            rows=result.rows,
            query_sha256=result.query_receipt.query_sha256,
            query_receipt_sha256=result.query_receipt.receipt_sha256,
            query_receipt_json=json.dumps(
                receipt_document, sort_keys=True, separators=(",", ":")
            ),
            reason=None,
        )


class SourceStructureLookup(Protocol):
    """Structural query dependency used by the server-rendered Atlas."""

    def query(
        self, resource_id: str, query: SourceStructureQuery
    ) -> SourceStructurePage: ...


__all__ = [
    "SourceStructureLookup",
    "SourceStructurePage",
    "SourceStructureQuery",
    "SourceStructureService",
    "UnknownPlatinumResourceError",
]
