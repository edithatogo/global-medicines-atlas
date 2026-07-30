"""Read-only, evidence-preserving product queries over canonical DuckDB data."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal, TypeGuard, cast

import duckdb

from .product_contracts import (
    AsOfClocks,
    ComparisonQuery,
    ComparisonResponse,
    CoverageItem,
    CoverageQuery,
    CoverageResponse,
    EvidenceAvailability,
    EvidenceDimension,
    EvidenceItem,
    EvidenceQuery,
    EvidenceResponse,
    PageMetadata,
    ProductConclusion,
    ProductState,
    ProvenanceLink,
    ResponseMetadata,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)

_CURSOR_VERSION: Final = 1
_MINIMUM_SECRET_BYTES: Final = 16
_CURSOR_SIGNATURE_BYTES: Final = 32
_REQUIRED_ASSERTION_COLUMNS: Final = frozenset({
    "assertion_id",
    "concept_id",
    "jurisdiction",
    "kind",
    "authority",
    "status_code",
    "evidence_status",
    "valid_from",
    "valid_to",
    "observed_from",
    "observed_to",
    "source_id",
    "source_uri",
    "retrieved_at",
    "source_sha256",
    "source_version",
    "transformation",
})
_REQUIRED_COVERAGE_COLUMNS: Final = frozenset({
    "jurisdiction",
    "source_id",
    "receipt_id",
    "dimension",
    "medicine_concept_id",
    "assertion_status",
    "valid_from",
    "valid_to",
    "observed_from",
    "observed_to",
    "concept_numerator",
    "eligible_denominator",
})
_REQUIRED_KEY_TYPES: Final = {
    ("temporal_assertions", "assertion_id"): "VARCHAR",
    ("temporal_assertions", "concept_id"): "VARCHAR",
    ("temporal_assertions", "jurisdiction"): "VARCHAR",
    ("temporal_assertions", "kind"): "VARCHAR",
    ("temporal_coverage", "jurisdiction"): "VARCHAR",
    ("temporal_coverage", "dimension"): "VARCHAR",
    ("temporal_coverage", "assertion_status"): "VARCHAR",
}


@dataclass(frozen=True, slots=True)
class QueryPlanEvidence:
    """Deterministic evidence that pagination is executed by DuckDB."""

    operation: Literal["coverage", "evidence"]
    requested_limit: int
    fetch_limit: int
    keyset_applied: bool
    schema_identity: str
    plan: str


class QueryServiceError(ValueError):
    """Base class for safe public-query failures."""


class InvalidCursorError(QueryServiceError):
    """The cursor is malformed, altered, or belongs to another query."""


class InvalidDatabaseError(QueryServiceError):
    """The configured database is unsafe or lacks the canonical schema."""


def _is_string_list(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and all(
        isinstance(item, str) for item in cast("list[object]", value)
    )


class ReadOnlyQueryService:
    """Request-scoped, read-only access to a canonical local DuckDB database."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        cursor_secret: bytes,
        allowed_root: str | Path | None = None,
    ) -> None:
        if len(cursor_secret) < _MINIMUM_SECRET_BYTES:
            raise ValueError("cursor_secret must contain at least 16 bytes")
        supplied = Path(database_path).expanduser()
        if not supplied.is_absolute():
            raise InvalidDatabaseError("database_path must be absolute")
        resolved = supplied.resolve(strict=True)
        if not resolved.is_file():
            raise InvalidDatabaseError("database_path must be a regular file")
        if resolved.suffix.casefold() not in {".duckdb", ".db"}:
            raise InvalidDatabaseError("database_path must be a DuckDB file")
        if allowed_root is not None:
            root = Path(allowed_root).expanduser().resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise InvalidDatabaseError(
                    "database_path is outside allowed_root"
                )
        self._database_path = resolved
        self._cursor_secret = bytes(cursor_secret)
        with self._connection() as connection:
            self._schema_identity = self._validate_schema(connection)

    @property
    def database_path(self) -> Path:
        """Return the validated canonical database path."""
        return self._database_path

    @property
    def schema_identity(self) -> str:
        """Return the deterministic identity of the compatible query schema."""
        return self._schema_identity

    @contextmanager
    def _connection(self) -> Generator[duckdb.DuckDBPyConnection]:
        connection: duckdb.DuckDBPyConnection | None = None
        try:
            connection = duckdb.connect(
                str(self._database_path), read_only=True
            )
            yield connection
        except duckdb.Error, OSError:
            raise QueryServiceError(
                "The read-only query service is unavailable"
            ) from None
        finally:
            if connection is not None:
                with suppress(duckdb.Error):
                    connection.close()

    def readiness_probe(self) -> None:
        """Verify that the canonical database remains readable."""
        with self._connection() as connection:
            current_identity = self._validate_schema(connection)
            if current_identity != self._schema_identity:
                raise InvalidDatabaseError(
                    "canonical DuckDB schema identity changed at runtime"
                )
            connection.execute("SELECT 1").fetchone()

    @staticmethod
    def _columns(
        connection: duckdb.DuckDBPyConnection, table: str
    ) -> frozenset[str]:
        rows = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table],
        ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    @staticmethod
    def _schema_columns(
        connection: duckdb.DuckDBPyConnection,
    ) -> list[tuple[str, str, str, int]]:
        rows = connection.execute(
            """
            SELECT table_name, column_name, data_type, ordinal_position
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name IN ('temporal_assertions', 'temporal_coverage')
            ORDER BY table_name, ordinal_position
            """
        ).fetchall()
        return [
            (str(table), str(column), str(data_type), int(position))
            for table, column, data_type, position in rows
        ]

    def _validate_schema(self, connection: duckdb.DuckDBPyConnection) -> str:
        assertions = self._columns(connection, "temporal_assertions")
        coverage = self._columns(connection, "temporal_coverage")
        missing_assertions = _REQUIRED_ASSERTION_COLUMNS - assertions
        missing_coverage = _REQUIRED_COVERAGE_COLUMNS - coverage
        if missing_assertions or missing_coverage:
            parts: list[str] = []
            if missing_assertions:
                parts.append(
                    "temporal_assertions: "
                    + ", ".join(sorted(missing_assertions))
                )
            if missing_coverage:
                parts.append(
                    "temporal_coverage: " + ", ".join(sorted(missing_coverage))
                )
            raise InvalidDatabaseError(
                "canonical DuckDB schema is incomplete ("
                + "; ".join(parts)
                + ")"
            )
        columns = self._schema_columns(connection)
        actual_types = {
            (table, column): data_type
            for table, column, data_type, _position in columns
        }
        incompatible = [
            f"{table}.{column}: expected {expected}, got {actual_types.get((table, column))}"
            for (table, column), expected in _REQUIRED_KEY_TYPES.items()
            if actual_types.get((table, column)) != expected
        ]
        if incompatible:
            raise InvalidDatabaseError(
                "canonical DuckDB schema has incompatible type ("
                + "; ".join(incompatible)
                + ")"
            )
        canonical = json.dumps(columns, separators=(",", ":")).encode()
        return hashlib.sha256(canonical).hexdigest()

    def comparisons(self, query: ComparisonQuery) -> ComparisonResponse:
        """Return explicit assertions plus coverage-supported absent states."""
        fingerprint = self._fingerprint(
            "comparisons", query, exclude_cursor=True
        )
        after = self._decode_cursor(query.cursor, fingerprint)
        jurisdictions = sorted(query.jurisdictions)
        dimensions = sorted(dimension.value for dimension in query.dimensions)
        with self._connection() as connection:
            candidate_keys = self._comparison_page_keys(
                connection,
                query,
                jurisdictions,
                dimensions,
                after,
            )
            page_keys = candidate_keys[: query.limit]
            pairs = [(key[0], key[1]) for key in page_keys]
            assertion_rows = self._comparison_assertions(
                connection, query, jurisdictions, dimensions, pairs
            )
            coverage_rows = self._comparison_coverage(
                connection, query, jurisdictions, dimensions, pairs
            )

        conclusions = self._build_conclusions(
            query, assertion_rows, coverage_rows
        )
        conclusions.sort(key=self._conclusion_key)
        has_more = len(candidate_keys) > query.limit
        next_cursor = (
            self._encode_cursor(fingerprint, candidate_keys[query.limit - 1])
            if has_more and candidate_keys
            else None
        )
        return ComparisonResponse(
            metadata=self._metadata(
                query, len(conclusions), query.limit, next_cursor
            ),
            conclusions=tuple(conclusions),
        )

    def coverage(self, query: CoverageQuery) -> CoverageResponse:
        """Return explicit coverage observations without invented denominators."""
        fingerprint = self._fingerprint("coverage", query, exclude_cursor=True)
        after = self._decode_cursor(query.cursor, fingerprint)
        jurisdictions = sorted(query.jurisdictions)
        dimensions = sorted(dimension.value for dimension in query.dimensions)
        parameters: list[object] = [
            jurisdictions,
            query.valid_at,
            query.valid_at,
            query.observed_at,
            query.observed_at,
        ]
        if dimensions:
            parameters.append(dimensions)
            dimension_filter = "AND dimension IN (SELECT unnest(?))"
        else:
            dimension_filter = ""
        keyset_filter = ""
        if after is not None:
            parameters.extend(after)
            keyset_filter = """
                WHERE (jurisdiction, dimension, assertion_status) > (?, ?, ?)
            """
        parameters.append(query.limit + 1)
        sql = f"""
            WITH grouped AS (
                SELECT jurisdiction, dimension, assertion_status,
                       sum(concept_numerator)::BIGINT AS covered_count,
                       CASE
                           WHEN bool_or(eligible_denominator IS NULL) THEN NULL
                           ELSE sum(eligible_denominator)::BIGINT
                       END AS denominator
                FROM temporal_coverage
                WHERE jurisdiction IN (SELECT unnest(?))
                  AND valid_from <= ?
                  AND (valid_to IS NULL OR ? < valid_to)
                  AND observed_from <= ?
                  AND (observed_to IS NULL OR ? < observed_to)
                  {dimension_filter}
                GROUP BY jurisdiction, dimension, assertion_status
            )
            SELECT *
            FROM grouped
            {keyset_filter}
            ORDER BY jurisdiction, dimension, assertion_status
            LIMIT ?
            """  # ruff: ignore[hardcoded-sql-expression]
        with self._connection() as connection:
            rows = self._fetch_dicts(connection, sql, parameters)
        items = [self._coverage_item(query, row) for row in rows]
        page, next_cursor = self._page_from_sql(
            items, query.limit, fingerprint, self._coverage_key
        )
        return CoverageResponse(
            metadata=self._metadata(query, len(page), query.limit, next_cursor),
            coverage=tuple(page),
        )

    def evidence(self, query: EvidenceQuery) -> EvidenceResponse:
        """Return assertion-level evidence with deterministic pagination."""
        fingerprint = self._fingerprint("evidence", query, exclude_cursor=True)
        after = self._decode_cursor(query.cursor, fingerprint)
        lookup_value = query.assertion_id or query.concept_id
        predicate = (
            "assertion_id = ?"
            if query.assertion_id is not None
            else "concept_id = ?"
        )
        column: Literal["assertion_id", "concept_id"] = (
            "assertion_id" if predicate == "assertion_id = ?" else "concept_id"
        )
        sql, parameters = self._evidence_page_statement(column, query, after)
        with self._connection() as connection:
            parameters[0] = lookup_value
            rows = self._fetch_dicts(connection, sql, parameters)
        items = [self._evidence_item(query, row) for row in rows]
        page, next_cursor = self._page_from_sql(
            items, query.limit, fingerprint, self._evidence_key
        )
        return EvidenceResponse(
            metadata=self._metadata(query, len(page), query.limit, next_cursor),
            evidence=tuple(page),
        )

    def _comparison_assertions(
        self,
        connection: duckdb.DuckDBPyConnection,
        query: ComparisonQuery,
        jurisdictions: list[str],
        dimensions: list[str],
        pairs: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        if not pairs:
            return []
        pair_sql, pair_parameters = self._pair_predicate(
            pairs, dimension_column="kind"
        )
        return self._fetch_dicts(
            connection,
            f"""
            SELECT assertion_id, concept_id, jurisdiction, kind, authority,
                   status_code, evidence_status, source_id, source_uri,
                   CAST(retrieved_at AS VARCHAR) AS retrieved_at,
                   CAST(observed_from AS VARCHAR) AS observed_from,
                   source_sha256, source_version, transformation
            FROM temporal_assertions
            WHERE concept_id = ?
              AND jurisdiction IN (SELECT unnest(?))
              AND kind IN (SELECT unnest(?))
              AND valid_from <= ?
              AND (valid_to IS NULL OR ? < valid_to)
              AND observed_from <= ?
              AND (observed_to IS NULL OR ? < observed_to)
              AND ({pair_sql})
            ORDER BY jurisdiction, kind, assertion_id
            """,  # ruff: ignore[hardcoded-sql-expression]
            [
                query.concept_id,
                jurisdictions,
                dimensions,
                query.valid_at,
                query.valid_at,
                query.observed_at,
                query.observed_at,
                *pair_parameters,
            ],
        )

    def _comparison_coverage(
        self,
        connection: duckdb.DuckDBPyConnection,
        query: ComparisonQuery,
        jurisdictions: list[str],
        dimensions: list[str],
        pairs: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        if not pairs:
            return []
        pair_sql, pair_parameters = self._pair_predicate(
            pairs, dimension_column="dimension"
        )
        return self._fetch_dicts(
            connection,
            f"""
            SELECT jurisdiction, source_id, receipt_id, observation_id,
                   dimension, medicine_concept_id, assertion_status
            FROM temporal_coverage
            WHERE jurisdiction IN (SELECT unnest(?))
              AND dimension IN (SELECT unnest(?))
              AND (
                  medicine_concept_id = ?
                  OR medicine_concept_id IS NULL
              )
              AND valid_from <= ?
              AND (valid_to IS NULL OR ? < valid_to)
              AND observed_from <= ?
              AND (observed_to IS NULL OR ? < observed_to)
              AND ({pair_sql})
            ORDER BY jurisdiction, dimension, medicine_concept_id NULLS LAST,
                     observation_id
            """,  # ruff: ignore[hardcoded-sql-expression]
            [
                jurisdictions,
                dimensions,
                query.concept_id,
                query.valid_at,
                query.valid_at,
                query.observed_at,
                query.observed_at,
                *pair_parameters,
            ],
        )

    @staticmethod
    def _pair_predicate(
        pairs: Sequence[tuple[str, str]],
        *,
        dimension_column: Literal["kind", "dimension"],
    ) -> tuple[str, list[object]]:
        clauses = [
            f"(jurisdiction = ? AND {dimension_column} = ?)" for _pair in pairs
        ]
        parameters: list[object] = [
            value for pair in pairs for value in (pair[0], pair[1])
        ]
        return " OR ".join(clauses), parameters

    def _comparison_page_keys(
        self,
        connection: duckdb.DuckDBPyConnection,
        query: ComparisonQuery,
        jurisdictions: list[str],
        dimensions: list[str],
        after: tuple[str, ...] | None,
    ) -> list[tuple[str, str, str]]:
        parameters: list[object] = [
            query.concept_id,
            jurisdictions,
            dimensions,
            query.valid_at,
            query.valid_at,
            query.observed_at,
            query.observed_at,
            query.concept_id,
            jurisdictions,
            dimensions,
            query.concept_id,
            query.valid_at,
            query.valid_at,
            query.observed_at,
            query.observed_at,
        ]
        keyset = ""
        if after is not None:
            parameters.extend(after)
            keyset = "WHERE (jurisdiction, dimension, concept_id) > (?, ?, ?)"
        parameters.append(query.limit + 1)
        sql = f"""
            WITH candidate_keys AS (
                SELECT DISTINCT jurisdiction, kind AS dimension, concept_id
                FROM temporal_assertions
                WHERE concept_id = ?
                  AND jurisdiction IN (SELECT unnest(?))
                  AND kind IN (SELECT unnest(?))
                  AND valid_from <= ?
                  AND (valid_to IS NULL OR ? < valid_to)
                  AND observed_from <= ?
                  AND (observed_to IS NULL OR ? < observed_to)
                UNION
                SELECT DISTINCT jurisdiction, dimension, ? AS concept_id
                FROM temporal_coverage
                WHERE jurisdiction IN (SELECT unnest(?))
                  AND dimension IN (SELECT unnest(?))
                  AND (medicine_concept_id = ? OR medicine_concept_id IS NULL)
                  AND valid_from <= ?
                  AND (valid_to IS NULL OR ? < valid_to)
                  AND observed_from <= ?
                  AND (observed_to IS NULL OR ? < observed_to)
            )
            SELECT jurisdiction, dimension, concept_id
            FROM candidate_keys
            {keyset}
            ORDER BY jurisdiction, dimension, concept_id
            LIMIT ?
            """  # ruff: ignore[hardcoded-sql-expression]
        rows = connection.execute(sql, parameters).fetchall()
        return [
            (str(jurisdiction), str(dimension), str(concept_id))
            for jurisdiction, dimension, concept_id in rows
        ]

    @staticmethod
    def _evidence_sql_by_assertion() -> str:
        return ReadOnlyQueryService._evidence_sql("assertion_id")

    @staticmethod
    def _evidence_sql_by_concept() -> str:
        return ReadOnlyQueryService._evidence_sql("concept_id")

    @staticmethod
    def _evidence_sql(column: Literal["assertion_id", "concept_id"]) -> str:
        # The caller chooses from this closed literal set; user input is always bound.
        return f"""
            SELECT assertion_id, concept_id, jurisdiction, kind, authority,
                   status_code, evidence_status, source_id, source_uri,
                   CAST(retrieved_at AS VARCHAR) AS retrieved_at,
                   CAST(observed_from AS VARCHAR) AS observed_from,
                   source_sha256, source_version, transformation
            FROM temporal_assertions
            WHERE {column} = ?
              AND valid_from <= ?
              AND (valid_to IS NULL OR ? < valid_to)
              AND observed_from <= ?
              AND (observed_to IS NULL OR ? < observed_to)
            ORDER BY jurisdiction, kind, assertion_id
            """  # ruff: ignore[hardcoded-sql-expression]

    @classmethod
    def _evidence_page_statement(
        cls,
        column: Literal["assertion_id", "concept_id"],
        query: EvidenceQuery,
        after: tuple[str, ...] | None,
    ) -> tuple[str, list[object]]:
        parameters: list[object] = [
            query.assertion_id or query.concept_id,
            query.valid_at,
            query.valid_at,
            query.observed_at,
            query.observed_at,
        ]
        keyset = ""
        if after is not None:
            parameters.extend(after)
            keyset = "AND (jurisdiction, kind, assertion_id) > (?, ?, ?)"
        parameters.append(query.limit + 1)
        sql = cls._evidence_sql(column).replace(
            "ORDER BY jurisdiction, kind, assertion_id",
            f"{keyset}\nORDER BY jurisdiction, kind, assertion_id\nLIMIT ?",
        )
        return sql, parameters

    def query_plan_evidence(
        self, query: CoverageQuery | EvidenceQuery
    ) -> QueryPlanEvidence:
        """Return an explain-plan receipt for one paginated SQL operation."""
        if isinstance(query, EvidenceQuery):
            operation: Literal["coverage", "evidence"] = "evidence"
            fingerprint = self._fingerprint(
                operation, query, exclude_cursor=True
            )
            after = self._decode_cursor(query.cursor, fingerprint)
            column: Literal["assertion_id", "concept_id"] = (
                "assertion_id"
                if query.assertion_id is not None
                else "concept_id"
            )
            sql, parameters = self._evidence_page_statement(
                column, query, after
            )
        else:
            raise NotImplementedError(
                "coverage plan receipts are not yet exposed"
            )
        with self._connection() as connection:
            rows = connection.execute(
                f"EXPLAIN {sql}",
                parameters,
            ).fetchall()
        return QueryPlanEvidence(
            operation=operation,
            requested_limit=query.limit,
            fetch_limit=query.limit + 1,
            keyset_applied=after is not None,
            schema_identity=self.schema_identity,
            plan="\n".join(str(row[-1]) for row in rows),
        )

    def _build_conclusions(
        self,
        query: ComparisonQuery,
        assertion_rows: Sequence[Mapping[str, Any]],
        coverage_rows: Sequence[Mapping[str, Any]],
    ) -> list[ProductConclusion]:
        grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        for row in assertion_rows:
            grouped.setdefault(
                (str(row["jurisdiction"]), str(row["kind"])), []
            ).append(row)
        explicit_coverage: dict[tuple[str, str], Mapping[str, Any]] = {}
        for row in coverage_rows:
            key = (str(row["jurisdiction"]), str(row["dimension"]))
            current = explicit_coverage.get(key)
            if current is None or (
                current["medicine_concept_id"] is None
                and row["medicine_concept_id"] is not None
            ):
                explicit_coverage[key] = row

        conclusions: list[ProductConclusion] = []
        for jurisdiction in query.jurisdictions:
            for dimension in query.dimensions:
                key = (jurisdiction, dimension.value)
                rows = grouped.get(key, [])
                if rows:
                    conclusions.append(self._assertion_conclusion(query, rows))
                    continue
                coverage = explicit_coverage.get(key)
                if coverage is not None:
                    conclusions.append(
                        self._coverage_conclusion(
                            query, jurisdiction, dimension, coverage
                        )
                    )
        return conclusions

    def _assertion_conclusion(
        self,
        query: ComparisonQuery,
        rows: Sequence[Mapping[str, Any]],
    ) -> ProductConclusion:
        states = {str(row["evidence_status"]) for row in rows}
        state = (
            ProductState.CONFLICTING
            if "conflicting" in states
            or len({row["status_code"] for row in rows}) > 1
            else self._state(next(iter(states)))
        )
        first = rows[0]
        uncertainty = self._uncertainty(state)
        return ProductConclusion(
            concept_id=query.concept_id,
            jurisdiction=str(first["jurisdiction"]),
            dimension=EvidenceDimension(str(first["kind"])),
            state=state,
            status_code=str(first["status_code"]),
            terminology=self._terminology(first),
            provenance=tuple(self._provenance(row) for row in rows),
            evidence_availability=EvidenceAvailability.AVAILABLE,
            uncertainty=uncertainty,
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )

    def _coverage_conclusion(
        self,
        query: ComparisonQuery,
        jurisdiction: str,
        dimension: EvidenceDimension,
        row: Mapping[str, Any],
    ) -> ProductConclusion:
        explicit = str(row["assertion_status"]).casefold()
        state = (
            ProductState.NOT_COVERED
            if explicit == ProductState.NOT_COVERED.value
            else ProductState.UNKNOWN
        )
        source_id = str(row["source_id"])
        return ProductConclusion(
            concept_id=query.concept_id,
            jurisdiction=jurisdiction,
            dimension=dimension,
            state=state,
            status_code=None,
            terminology=Terminology(
                native_code=explicit,
                native_label=explicit.replace("_", " "),
                native_system=source_id,
                canonical_code=query.concept_id,
                canonical_label=query.concept_id,
                canonical_system="global-medicines-atlas",
            ),
            provenance=(),
            evidence_availability=EvidenceAvailability.UNAVAILABLE,
            evidence_unavailable_reason=(
                f"Coverage evidence {row['observation_id']} explicitly classifies "
                f"this dimension as {state.value}; no assertion evidence is present."
            ),
            uncertainty=self._uncertainty(state),
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )

    @staticmethod
    def _terminology(row: Mapping[str, Any]) -> Terminology:
        status = str(row["status_code"])
        return Terminology(
            native_code=status,
            native_label=status.replace("_", " ").replace("-", " "),
            native_system=str(row["authority"]),
            canonical_code=str(row["concept_id"]),
            canonical_label=str(row["concept_id"]),
            canonical_system="global-medicines-atlas",
        )

    @staticmethod
    def _provenance(row: Mapping[str, Any]) -> ProvenanceLink:
        retrieved = datetime.fromisoformat(
            str(row.get("retrieved_at") or row["observed_from"])
        )
        return ProvenanceLink(
            source_id=str(row["source_id"]),
            source_uri=str(row["source_uri"]),
            retrieved_at=retrieved,
            source_version=row.get("source_version"),
            source_sha256=row.get("source_sha256"),
            transformation_id=row.get("transformation"),
        )

    def _evidence_item(
        self, query: EvidenceQuery, row: Mapping[str, Any]
    ) -> EvidenceItem:
        state = self._state(str(row["evidence_status"]))
        return EvidenceItem(
            assertion_id=str(row["assertion_id"]),
            concept_id=str(row["concept_id"]),
            jurisdiction=str(row["jurisdiction"]),
            dimension=EvidenceDimension(str(row["kind"])),
            state=state,
            status_code=str(row["status_code"]),
            terminology=self._terminology(row),
            provenance=self._provenance(row),
            uncertainty=self._uncertainty(state),
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )

    def _coverage_item(
        self, query: CoverageQuery, row: Mapping[str, Any]
    ) -> CoverageItem:
        state = self._state(str(row["assertion_status"]))
        return CoverageItem(
            jurisdiction=str(row["jurisdiction"]),
            dimension=EvidenceDimension(str(row["dimension"])),
            state=state,
            covered_count=int(row["covered_count"]),
            denominator=(
                None if row["denominator"] is None else int(row["denominator"])
            ),
            provenance=(),
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )

    @staticmethod
    def _state(value: str) -> ProductState:
        try:
            return ProductState(value.casefold())
        except ValueError:
            return ProductState.UNKNOWN

    @staticmethod
    def _uncertainty(state: ProductState) -> Uncertainty:
        if state is ProductState.CONFIRMED:
            return Uncertainty(level=UncertaintyLevel.NONE, confidence=1.0)
        if state is ProductState.INFERRED:
            return Uncertainty(
                level=UncertaintyLevel.MEDIUM,
                reason="The source assertion is explicitly classified as inferred.",
            )
        return Uncertainty(
            level=UncertaintyLevel.UNKNOWN,
            reason=f"The evidence state is explicitly {state.value}.",
        )

    @staticmethod
    def _fetch_dicts(
        connection: duckdb.DuckDBPyConnection,
        sql: str,
        parameters: Sequence[object],
    ) -> list[dict[str, Any]]:
        cursor = connection.execute(sql, list(parameters))
        names = [str(item[0]) for item in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def _conclusion_key(item: ProductConclusion) -> tuple[str, ...]:
        return (item.jurisdiction, item.dimension.value, item.concept_id)

    @staticmethod
    def _coverage_key(item: CoverageItem) -> tuple[str, ...]:
        return (item.jurisdiction, item.dimension.value, item.state.value)

    @staticmethod
    def _evidence_key(item: EvidenceItem) -> tuple[str, ...]:
        return (item.jurisdiction, item.dimension.value, item.assertion_id)

    def _paginate(
        self,
        items: list[Any],
        limit: int,
        after: tuple[str, ...] | None,
        fingerprint: str,
        key: Any,
    ) -> tuple[list[Any], str | None]:
        if after is not None:
            items = [item for item in items if key(item) > after]
        page = items[:limit]
        has_more = len(items) > limit
        cursor = (
            self._encode_cursor(fingerprint, key(page[-1]))
            if has_more and page
            else None
        )
        return page, cursor

    def _page_from_sql(
        self,
        items: list[Any],
        limit: int,
        fingerprint: str,
        key: Any,
    ) -> tuple[list[Any], str | None]:
        has_more = len(items) > limit
        page = items[:limit]
        cursor = (
            self._encode_cursor(fingerprint, key(page[-1]))
            if has_more and page
            else None
        )
        return page, cursor

    def _fingerprint(
        self,
        operation: str,
        query: ComparisonQuery | CoverageQuery | EvidenceQuery,
        *,
        exclude_cursor: bool,
    ) -> str:
        payload = query.model_dump(
            mode="json", exclude={"cursor"} if exclude_cursor else set()
        )
        canonical = json.dumps(
            {"operation": operation, "query": payload},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def _encode_cursor(self, fingerprint: str, key: tuple[str, ...]) -> str:
        payload = json.dumps(
            {"v": _CURSOR_VERSION, "fingerprint": fingerprint, "after": key},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        signature = hmac.digest(self._cursor_secret, payload, "sha256")
        return (
            base64.urlsafe_b64encode(payload + signature).rstrip(b"=").decode()
        )

    def _decode_cursor(
        self, token: str | None, fingerprint: str
    ) -> tuple[str, ...] | None:
        if token is None:
            return None
        try:
            decoded, signature, payload = self._parse_cursor(token)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            raise InvalidCursorError("cursor is malformed") from error
        expected = hmac.digest(self._cursor_secret, payload, "sha256")
        if not hmac.compare_digest(signature, expected):
            raise InvalidCursorError("cursor signature is invalid")
        after: object = decoded.get("after")
        if (
            decoded.get("v") != _CURSOR_VERSION
            or decoded.get("fingerprint") != fingerprint
            or not _is_string_list(after)
        ):
            raise InvalidCursorError("cursor does not belong to this query")
        return tuple(after)

    @staticmethod
    def _parse_cursor(token: str) -> tuple[dict[str, object], bytes, bytes]:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.b64decode(padded.encode(), altchars=b"-_", validate=True)
        if len(raw) <= _CURSOR_SIGNATURE_BYTES:
            raise ValueError("cursor payload is empty")
        payload = raw[:-_CURSOR_SIGNATURE_BYTES]
        signature = raw[-_CURSOR_SIGNATURE_BYTES:]
        decoded_object = cast("object", json.loads(payload))
        if not isinstance(decoded_object, dict):
            raise TypeError("cursor payload must be an object")
        decoded = cast("dict[str, object]", decoded_object)
        return decoded, signature, payload

    @staticmethod
    def _metadata(
        query: ComparisonQuery | CoverageQuery | EvidenceQuery,
        returned: int,
        limit: int,
        cursor: str | None,
    ) -> ResponseMetadata:
        return ResponseMetadata(
            generated_at=datetime.now(UTC),
            clocks=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
            page=PageMetadata(
                limit=limit, returned=returned, next_cursor=cursor
            ),
        )


QueryOperation = Literal["comparisons", "coverage", "evidence"]
