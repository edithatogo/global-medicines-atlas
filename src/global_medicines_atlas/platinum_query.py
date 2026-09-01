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
from dataclasses import dataclass
from typing import Literal, Protocol, cast

import duckdb
import polars as pl

from .platinum_resolver import (
    CacheReceipt,
    ProductRead,
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


class QueryAdapter(Protocol):
    """Storage-neutral engine boundary used by the shared query service."""

    name: EngineName

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
        _validate_spec(spec)
        try:
            adapter = self._adapters[engine]
        except KeyError:
            raise ValueError("unsupported query engine") from None
        if adapter.name != engine:
            raise ValueError("query engine adapter identity mismatch")
        with self._resolver.open(resource_id, offline=offline) as read:
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
            metadata = read.metadata
            evidence = QueryEvidence(
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
            return QueryResult(
                status="available",
                engine=adapter.name,
                capabilities=CAPABILITIES,
                rows=rows,
                row_count=len(rows),
                canonical_rows=canonical,
                result_sha256=hashlib.sha256(canonical).hexdigest(),
                evidence=evidence,
                cache_receipt=read.cache_receipt,
            )


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
