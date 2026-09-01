"""Bounded query adapters over exact, verified Platinum Parquet resources.

The adapters use only the context-owned transient stream returned by the v4
resolver. They neither discover nor publish datasets and never make a query
engine an evidentiary authority. DuckDB uses an immediately removed temporary
Parquet file; Polars scans the verified stream directly.
"""

from __future__ import annotations

import datetime as dt
import decimal
import hashlib
import json
import math
import re
import shutil
import tempfile
import time
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Literal, Protocol, cast

import duckdb
import polars as pl

from .platinum_resolver import (
    CacheReceipt,
    ProductRead,
    ResolvedResource,
    StorageNeutralResolver,
)

EngineName = Literal["duckdb", "polars"]
Operator = Literal["=", "!=", "<", "<=", ">", ">="]
Scalar = str | int | float | bool | None
CAPABILITIES = (
    "column_projection",
    "predicate_pushdown",
    "bounded_limit",
)
MAX_COLUMNS = 64
MAX_FILTERS = 16
MAX_ROWS = 1000
MAX_RESULT_BYTES = 1024 * 1024
MAX_RUNTIME_SECONDS = 30.0
_COLUMN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_OPERATORS = {"=", "!=", "<", "<=", ">", ">="}


@dataclass(frozen=True)
class QueryFilter:
    """One scalar comparison against a named Parquet column."""

    column: str
    operator: Operator
    value: Scalar


@dataclass(frozen=True)
class QuerySpec:
    """A deliberately small projection/filter/limit query contract."""

    columns: tuple[str, ...]
    filters: tuple[QueryFilter, ...] = ()
    limit: int = 100
    max_result_bytes: int = MAX_RESULT_BYTES
    timeout_seconds: float = MAX_RUNTIME_SECONDS


@dataclass(frozen=True)
class QueryEvidence:
    """Exact source identity and conservative semantic result metadata."""

    resource_id: str
    dataset: str
    revision: str
    path: str
    object_sha256: str
    contract_sha256: str
    semantic_dimension: str
    entity_granularity: str
    source_id: str
    acquisition_id: str
    layer: str
    schema_era: str
    comparison_cohort: str
    effective_date: str | None
    retrieved_at: str
    coverage_state: Literal["not_declared"] = "not_declared"
    uncertainty_state: Literal["not_declared"] = "not_declared"
    review_state: Literal["not_declared"] = "not_declared"
    comparison_validity: Literal["not_evaluated"] = "not_evaluated"


@dataclass(frozen=True)
class QueryResult:
    """Deterministic bounded rows paired with immutable evidence identity."""

    status: Literal["available"]
    engine: EngineName
    capabilities: tuple[str, ...]
    rows: tuple[dict[str, Scalar], ...]
    row_count: int
    canonical_rows: bytes
    result_sha256: str
    evidence: QueryEvidence
    cache_receipt: CacheReceipt
    query_receipt: QueryReceipt


@dataclass(frozen=True)
class QueryReceipt:
    """Content-addressed binding of a plan, result and exact evidence."""

    resource_id: str
    engine: EngineName
    canonical_query: bytes
    query_sha256: str
    result_sha256: str
    row_count: int
    object_sha256: str
    contract_sha256: str
    cache_receipt_sha256: str

    @property
    def canonical_bytes(self) -> bytes:
        """Encode the receipt deterministically without its own digest."""
        return json.dumps(
            {
                "cache_receipt_sha256": self.cache_receipt_sha256,
                "contract_sha256": self.contract_sha256,
                "engine": self.engine,
                "object_sha256": self.object_sha256,
                "query_sha256": self.query_sha256,
                "resource_id": self.resource_id,
                "result_sha256": self.result_sha256,
                "row_count": self.row_count,
                "version": "1.0",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    @property
    def receipt_sha256(self) -> str:
        """Return the content address of the exact query observation."""
        return hashlib.sha256(self.canonical_bytes).hexdigest()


UnavailableReason = Literal[
    "unknown_resource",
    "offline_cache_unavailable",
    "offline_contract_expired",
    "verified_resource_unavailable",
]


@dataclass(frozen=True)
class QueryUnavailable:
    """Typed fail-closed state for a valid query whose bytes are unavailable."""

    status: Literal["unavailable"]
    reason: UnavailableReason
    resource_id: str
    engine: EngineName
    evidence: QueryEvidence | None
    cache_receipt: CacheReceipt | None

    @property
    def canonical_bytes(self) -> bytes:
        """Encode an unavailable observation with exact known evidence."""
        return json.dumps(
            {
                "cache_receipt_sha256": (
                    self.cache_receipt.receipt_sha256
                    if self.cache_receipt is not None
                    else None
                ),
                "engine": self.engine,
                "evidence": (
                    _evidence_document(self.evidence)
                    if self.evidence is not None
                    else None
                ),
                "reason": self.reason,
                "resource_id": self.resource_id,
                "status": self.status,
                "version": "1.0",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    @property
    def receipt_sha256(self) -> str:
        """Return the content address of this exact unavailable state."""
        return hashlib.sha256(self.canonical_bytes).hexdigest()


class QueryAdapter(Protocol):
    """Storage-neutral engine boundary used by the shared query service."""

    @property
    def name(self) -> EngineName:
        """Return the immutable engine identity implemented by the adapter."""
        ...

    def execute(
        self, read: ProductRead, spec: QuerySpec
    ) -> tuple[dict[str, Scalar], ...]:
        """Execute a validated bounded query over one verified Parquet stream."""
        ...


class DuckDBQueryAdapter:
    """DuckDB Parquet scanner with SQL projection and predicate pushdown."""

    name: Literal["duckdb"] = "duckdb"

    def execute(
        self, read: ProductRead, spec: QuerySpec
    ) -> tuple[dict[str, Scalar], ...]:
        started = time.monotonic()
        read.verified.stream.seek(0)
        with tempfile.NamedTemporaryFile(suffix=".parquet") as parquet:
            shutil.copyfileobj(read.verified.stream, parquet)
            parquet.flush()
            with duckdb.connect(":memory:") as connection:
                cursor = connection.execute(
                    "SELECT * FROM read_parquet(?) LIMIT 0", [parquet.name]
                )
                available = {item[0] for item in cursor.description}
                _known_columns(spec, available)
                projection = ", ".join(_quote(item) for item in spec.columns)
                predicates = " AND ".join(
                    f"{_quote(item.column)} {item.operator} ?"
                    for item in spec.filters
                )
                # Identifiers and operators passed strict allowlists above;
                # values and the transient path remain bound parameters.
                sql = f"SELECT {projection} FROM read_parquet(?)"  # ruff: ignore[hardcoded-sql-expression]
                if predicates:
                    sql += f" WHERE {predicates}"
                sql += " LIMIT ?"
                parameters: list[object] = [parquet.name]
                parameters.extend(item.value for item in spec.filters)
                parameters.append(spec.limit)
                result = connection.execute(sql, parameters)
                names = [item[0] for item in result.description]
                rows = tuple(
                    {
                        name: _scalar(value)
                        for name, value in zip(names, row, strict=True)
                    }
                    for row in result.fetchall()
                )
        _runtime(started, spec.timeout_seconds)
        return rows


class PolarsQueryAdapter:
    """Polars lazy Parquet scanner with projection and predicate pushdown."""

    name: Literal["polars"] = "polars"

    def execute(
        self, read: ProductRead, spec: QuerySpec
    ) -> tuple[dict[str, Scalar], ...]:
        started = time.monotonic()
        read.verified.stream.seek(0)
        frame = pl.scan_parquet(read.verified.stream)
        _known_columns(spec, set(frame.collect_schema().names()))
        for item in spec.filters:
            expression = _polars_predicate(item)
            frame = frame.filter(expression)
        frame = frame.select(spec.columns).limit(spec.limit)
        rows = tuple(
            {name: _scalar(value) for name, value in row.items()}
            for row in frame.collect().to_dicts()
        )
        _runtime(started, spec.timeout_seconds)
        return rows


class PlatinumQueryService:
    """Resolve, verify, scan and envelope one bounded Platinum query."""

    def __init__(
        self,
        resolver: StorageNeutralResolver,
        *,
        adapters: Mapping[str, QueryAdapter] | None = None,
    ) -> None:
        self._resolver = resolver
        self._adapters = dict(
            adapters
            if adapters is not None
            else {
                "duckdb": DuckDBQueryAdapter(),
                "polars": PolarsQueryAdapter(),
            }
        )

    def query(
        self,
        resource_id: str,
        *,
        engine: str,
        spec: QuerySpec,
        offline: bool = False,
    ) -> QueryResult:
        """Return bounded deterministic rows or fail closed before overclaim."""
        adapter = self._adapter(engine, spec)
        with self._resolver.open(resource_id, offline=offline) as read:
            return _available(adapter, read, spec)

    def query_state(
        self,
        resource_id: str,
        *,
        engine: str,
        spec: QuerySpec,
        offline: bool = False,
    ) -> QueryResult | QueryUnavailable:
        """Return typed unavailability only for valid resource-read failures."""
        adapter = self._adapter(engine, spec)
        try:
            metadata = self._resolver.resolve(resource_id)
        except ValueError:
            return QueryUnavailable(
                status="unavailable",
                reason="unknown_resource",
                resource_id=resource_id,
                engine=adapter.name,
                evidence=None,
                cache_receipt=None,
            )
        evidence = _evidence(metadata)
        receipt = self._resolver.cache_receipt(resource_id)
        if offline and receipt.status != "verified_exact_digest":
            return QueryUnavailable(
                status="unavailable",
                reason=(
                    "offline_contract_expired"
                    if receipt.status == "contract_expired"
                    else "offline_cache_unavailable"
                ),
                resource_id=resource_id,
                engine=adapter.name,
                evidence=evidence,
                cache_receipt=receipt,
            )
        stack = ExitStack()
        try:
            read = stack.enter_context(
                self._resolver.open(resource_id, offline=offline)
            )
        except ValueError:
            stack.close()
            return QueryUnavailable(
                status="unavailable",
                reason="verified_resource_unavailable",
                resource_id=resource_id,
                engine=adapter.name,
                evidence=evidence,
                cache_receipt=self._resolver.cache_receipt(resource_id),
            )
        with stack:
            return _available(adapter, read, spec)

    def _adapter(self, engine: str, spec: QuerySpec) -> QueryAdapter:
        _validate_spec(spec)
        try:
            adapter = self._adapters[engine]
        except KeyError:
            raise ValueError("unsupported query engine") from None
        if adapter.name != engine:
            raise ValueError("query engine adapter identity mismatch")
        return adapter


def _available(
    adapter: QueryAdapter, read: ProductRead, spec: QuerySpec
) -> QueryResult:
    rows = adapter.execute(read, spec)
    canonical = json.dumps(
        rows,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if len(canonical) > spec.max_result_bytes:
        raise ValueError("query result exceeds byte budget")
    evidence = _evidence(read.metadata)
    result_sha256 = hashlib.sha256(canonical).hexdigest()
    canonical_query = _canonical_query(spec)
    query_receipt = QueryReceipt(
        resource_id=read.metadata.resource_id,
        engine=adapter.name,
        canonical_query=canonical_query,
        query_sha256=hashlib.sha256(canonical_query).hexdigest(),
        result_sha256=result_sha256,
        row_count=len(rows),
        object_sha256=read.metadata.sha256,
        contract_sha256=read.metadata.contract_sha256,
        cache_receipt_sha256=read.cache_receipt.receipt_sha256,
    )
    return QueryResult(
        status="available",
        engine=adapter.name,
        capabilities=CAPABILITIES,
        rows=rows,
        row_count=len(rows),
        canonical_rows=canonical,
        result_sha256=result_sha256,
        evidence=evidence,
        cache_receipt=read.cache_receipt,
        query_receipt=query_receipt,
    )


def _evidence(metadata: ResolvedResource) -> QueryEvidence:
    return QueryEvidence(
        resource_id=metadata.resource_id,
        dataset=metadata.dataset,
        revision=metadata.revision,
        path=metadata.path,
        object_sha256=metadata.sha256,
        contract_sha256=metadata.contract_sha256,
        semantic_dimension=metadata.semantic_dimension,
        entity_granularity=metadata.entity_granularity,
        source_id=metadata.source_id,
        acquisition_id=metadata.acquisition_id,
        layer=metadata.layer,
        schema_era=metadata.schema_era,
        comparison_cohort=metadata.comparison_cohort,
        effective_date=metadata.effective_date,
        retrieved_at=metadata.retrieved_at,
    )


def _evidence_document(evidence: QueryEvidence) -> dict[str, object]:
    return {
        "acquisition_id": evidence.acquisition_id,
        "comparison_cohort": evidence.comparison_cohort,
        "comparison_validity": evidence.comparison_validity,
        "contract_sha256": evidence.contract_sha256,
        "coverage_state": evidence.coverage_state,
        "dataset": evidence.dataset,
        "effective_date": evidence.effective_date,
        "entity_granularity": evidence.entity_granularity,
        "layer": evidence.layer,
        "object_sha256": evidence.object_sha256,
        "path": evidence.path,
        "resource_id": evidence.resource_id,
        "retrieved_at": evidence.retrieved_at,
        "review_state": evidence.review_state,
        "revision": evidence.revision,
        "schema_era": evidence.schema_era,
        "semantic_dimension": evidence.semantic_dimension,
        "source_id": evidence.source_id,
        "uncertainty_state": evidence.uncertainty_state,
    }


def _canonical_query(spec: QuerySpec) -> bytes:
    return json.dumps(
        {
            "columns": spec.columns,
            "filters": [
                {
                    "column": item.column,
                    "operator": item.operator,
                    "value": item.value,
                }
                for item in spec.filters
            ],
            "limit": spec.limit,
            "max_result_bytes": spec.max_result_bytes,
            "timeout_seconds": spec.timeout_seconds,
            "version": "1.0",
        },
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _validate_spec(spec: QuerySpec) -> None:
    if not spec.columns or len(spec.columns) > MAX_COLUMNS:
        raise ValueError("query columns exceed budget")
    if len(set(spec.columns)) != len(spec.columns):
        raise ValueError("query columns must be unique")
    if len(spec.filters) > MAX_FILTERS:
        raise ValueError("query filters exceed budget")
    if type(spec.limit) is not int or not 1 <= spec.limit <= MAX_ROWS:
        raise ValueError("query limit exceeds budget")
    if (
        type(spec.max_result_bytes) is not int
        or not 1 <= spec.max_result_bytes <= MAX_RESULT_BYTES
    ):
        raise ValueError("query result byte budget is invalid")
    if (
        not math.isfinite(spec.timeout_seconds)
        or not 0 < spec.timeout_seconds <= MAX_RUNTIME_SECONDS
    ):
        raise ValueError("query timeout budget is invalid")
    for name in (*spec.columns, *(item.column for item in spec.filters)):
        if type(name) is not str or _COLUMN.fullmatch(name) is None:
            raise ValueError("invalid query column")
    for item in spec.filters:
        if item.operator not in _OPERATORS:
            raise ValueError("invalid query operator")
        if not _is_scalar(item.value):
            raise ValueError("invalid query scalar")


def _known_columns(spec: QuerySpec, available: set[str]) -> None:
    selected = {*spec.columns, *(item.column for item in spec.filters)}
    if not selected <= available:
        raise ValueError("unknown query column")


def _quote(name: str) -> str:
    return f'"{name}"'


def _polars_predicate(item: QueryFilter) -> pl.Expr:
    column = pl.col(item.column)
    value = item.value
    if item.operator == "=":
        return column == value
    if item.operator == "!=":
        return column != value
    if item.operator == "<":
        return column < value
    if item.operator == "<=":
        return column <= value
    if item.operator == ">":
        return column > value
    return column >= value


def _runtime(started: float, limit: float) -> None:
    if time.monotonic() - started > limit:
        raise ValueError("query runtime exceeds budget")


def _is_scalar(value: object) -> bool:
    if value is None or type(value) in {str, int, bool}:
        return True
    return type(value) is float and math.isfinite(value)


def _scalar(value: object) -> Scalar:
    if _is_scalar(value):
        return cast("Scalar", value)
    if isinstance(value, dt.datetime | dt.date | dt.time | decimal.Decimal):
        return str(value)
    raise ValueError("query result contains unsupported scalar")
