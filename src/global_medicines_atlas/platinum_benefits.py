"""Bounded shared Australian benefits queries for read-only product surfaces.

Pagination traverses a verified scan window, not an unbounded corpus. At the
window limit completeness remains unknown. Cursor bindings include the exact
query result, so a changed resource or query cannot silently continue a page.
Concrete federation imports are deferred until a configured service is used.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import Field

from .platinum_identity_service import ResolverDatasetIdentityService
from .platinum_surface_contracts import (
    DatasetIdentityEnvelope,
    PlatinumSurfaceModel,
    Sha256,
)

if TYPE_CHECKING:
    from .platinum_resolver import StorageNeutralResolver

Scalar = str | int | float | bool | None
_WINDOW_LIMIT = 1000
_MIN_CURSOR_KEY_BYTES = 32
Column = Annotated[
    str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=128)
]


class BenefitsQuery(PlatinumSurfaceModel):
    """Source-column projection and bounded page of an immutable resource."""

    columns: tuple[Column, ...] = Field(min_length=1, max_length=64)
    limit: int = Field(default=100, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=160)
    offline: bool = False


class BenefitsPage(PlatinumSurfaceModel):
    """Rows with exact identity and explicit limits on interpretability."""

    status: Literal["available", "unavailable"]
    identity: DatasetIdentityEnvelope
    rows: tuple[dict[str, Scalar], ...]
    window_sha256: Sha256 | None
    page_sha256: Sha256 | None
    receipt_sha256: Sha256
    reason: str | None
    next_cursor: str | None
    window_rows: int
    window_limit: Literal[1000] = 1000
    window_complete: bool
    coverage_state: Literal["not_declared"] = "not_declared"
    uncertainty_state: Literal["not_declared"] = "not_declared"
    review_state: Literal["not_declared"] = "not_declared"
    comparison_validity: Literal["not_evaluated"] = "not_evaluated"


class BenefitsLookup(Protocol):
    """Dependency-light interface shared by CLI and HTTP consumers."""

    def query(self, resource_id: str, query: BenefitsQuery) -> BenefitsPage: ...


class BenefitsService:
    """Query already-admitted Australian resources using verified Parquet."""

    def __init__(
        self, resolver: StorageNeutralResolver, *, cursor_key: bytes
    ) -> None:
        if (
            type(cursor_key) is not bytes
            or len(cursor_key) < _MIN_CURSOR_KEY_BYTES
        ):
            raise ValueError("cursor key must contain at least 32 bytes")
        self._resolver = resolver
        self._key = cursor_key

    def query(self, resource_id: str, query: BenefitsQuery) -> BenefitsPage:
        """Read one bounded window; preserve source ordering and semantics."""
        from .platinum_query import (  # ruff: ignore[import-outside-top-level] - optional federation runtime is loaded only for configured queries.
            PlatinumQueryService,
            QuerySpec,
        )

        identity = ResolverDatasetIdentityService(
            self._resolver, jurisdictions={resource_id: "AU"}
        ).identity(resource_id)
        if identity.source_id not in {"au-mbs", "au-pbs"}:
            raise ValueError("resource is not an Australian benefits source")
        result = PlatinumQueryService(self._resolver).query_state(
            resource_id,
            engine="polars",
            spec=QuerySpec(columns=query.columns, limit=_WINDOW_LIMIT),
            offline=query.offline,
        )
        if result.status == "unavailable":
            return BenefitsPage(
                status="unavailable",
                identity=identity,
                rows=(),
                window_sha256=None,
                page_sha256=None,
                receipt_sha256=result.receipt_sha256,
                reason=result.reason,
                next_cursor=None,
                window_rows=0,
                window_complete=False,
            )
        binding = hashlib.sha256(
            json.dumps(
                {
                    "contract": identity.contract_sha256,
                    "semantic": identity.semantic_manifest_sha256,
                    "resource": resource_id,
                    "query": result.query_receipt.query_sha256,
                    "result": result.result_sha256,
                    "limit": query.limit,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        offset = self._offset(query.cursor, binding)
        if offset > len(result.rows):
            raise ValueError("cursor offset exceeds query window")
        rows = result.rows[offset : offset + query.limit]
        end = offset + len(rows)
        return BenefitsPage(
            status="available",
            identity=identity,
            rows=rows,
            window_sha256=result.result_sha256,
            page_sha256=hashlib.sha256(
                json.dumps(
                    rows,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            receipt_sha256=result.query_receipt.receipt_sha256,
            reason=None,
            next_cursor=self._cursor(end, binding)
            if end < len(result.rows)
            else None,
            window_rows=len(result.rows),
            window_complete=len(result.rows) < _WINDOW_LIMIT,
        )

    def _cursor(self, offset: int, binding: str) -> str:
        value = f"{offset}:{binding}"
        return (
            f"{value}:{hmac.digest(self._key, value.encode(), 'sha256').hex()}"
        )

    def _offset(self, cursor: str | None, binding: str) -> int:
        if cursor is None:
            return 0
        try:
            offset, stored_binding, _signature = cursor.split(":")
            number = int(offset)
        except ValueError, TypeError:
            raise ValueError("cursor does not belong to this query") from None
        expected = self._cursor(number, binding)
        if (
            not 0 < number < _WINDOW_LIMIT
            or stored_binding != binding
            or not hmac.compare_digest(cursor, expected)
        ):
            raise ValueError("cursor does not belong to this query")
        return number
