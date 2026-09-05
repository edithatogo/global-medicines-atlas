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
import math
from typing import TYPE_CHECKING, Annotated, Literal, Protocol, cast

from pydantic import Field, field_validator

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
MAX_FILTERS = 16
MAX_FILTER_TEXT = 1024
MAX_FILTER_JSON = 16384


class BenefitsFilter(PlatinumSurfaceModel):
    """One typed scalar predicate, combined with other predicates using AND."""

    column: Column
    operator: Literal["=", "!=", "<", "<=", ">", ">="]
    value: Scalar

    @field_validator("value", mode="before")
    @classmethod
    def scalar_is_bounded(cls, value: object) -> object:
        """Reject coercion, nested values, nonfinite numbers and huge scalars."""
        if value is None or type(value) is bool:
            return value
        if type(value) is str and len(value) <= MAX_FILTER_TEXT:
            return value
        if type(value) is int and -(2**63) <= value < 2**63:
            return value
        if type(value) is float and math.isfinite(value):
            return value
        raise ValueError("filter value must be a bounded finite scalar")


def parse_benefits_filters(encoded: str | None) -> tuple[BenefitsFilter, ...]:
    """Parse the same bounded JSON predicate array for CLI and GET requests."""
    if encoded is None:
        return ()
    if type(encoded) is not str or len(encoded) > MAX_FILTER_JSON:
        raise ValueError("filter JSON exceeds input bound")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate filter JSON key")
            result[key] = value
        return result

    try:
        parsed = json.loads(encoded, object_pairs_hook=unique)
    except RecursionError:
        raise ValueError("filter JSON nesting exceeds input bound") from None
    if type(parsed) is not list:
        raise ValueError("filters require a bounded JSON array")
    items = cast("list[object]", parsed)
    if len(items) > MAX_FILTERS:
        raise ValueError("filters require a bounded JSON array")
    return tuple(BenefitsFilter.model_validate(item) for item in items)


class BenefitsQuery(PlatinumSurfaceModel):
    """Source-column projection and bounded page of an immutable resource."""

    columns: tuple[Column, ...] = Field(min_length=1, max_length=64)
    filters: tuple[BenefitsFilter, ...] = Field(
        default=(), max_length=MAX_FILTERS
    )
    limit: int = Field(default=100, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=160)
    offline: bool = False


class BenefitsPage(PlatinumSurfaceModel):
    """Rows with exact identity and explicit limits on interpretability."""

    status: Literal["available", "unavailable"]
    applied_filters: tuple[BenefitsFilter, ...] = ()
    query_sha256: Sha256
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
        if set(vars(query)) - set(BenefitsQuery.model_fields):
            raise ValueError("unknown copied query fields")
        if type(query.filters) is not tuple:
            raise ValueError("copied filters must be a typed tuple")
        for item in query.filters:
            if type(item) is not BenefitsFilter:
                raise ValueError("copied filters must be typed predicates")
            if set(vars(item)) - set(BenefitsFilter.model_fields):
                raise ValueError("unknown copied filter fields")
        query = BenefitsQuery.model_validate(query.model_dump(warnings=False))
        from .platinum_query import (  # ruff: ignore[import-outside-top-level] - optional federation runtime is loaded only for configured queries.
            PlatinumQueryService,
            QueryFilter,
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
            spec=QuerySpec(
                columns=query.columns,
                limit=_WINDOW_LIMIT,
                filters=tuple(
                    QueryFilter(item.column, item.operator, item.value)
                    for item in query.filters
                ),
            ),
            offline=query.offline,
        )
        if result.status == "unavailable":
            return BenefitsPage(
                status="unavailable",
                applied_filters=query.filters,
                query_sha256=result.query_sha256,
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
            applied_filters=query.filters,
            query_sha256=result.query_receipt.query_sha256,
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
