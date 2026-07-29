"""Read-only, evidence-preserving product queries over canonical DuckDB data."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager, suppress
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
            self._validate_schema(connection)

    @property
    def database_path(self) -> Path:
        """Return the validated canonical database path."""
        return self._database_path

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
            self._validate_schema(connection)
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

    def _validate_schema(self, connection: duckdb.DuckDBPyConnection) -> None:
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

    def comparisons(self, query: ComparisonQuery) -> ComparisonResponse:
        """Return explicit assertions plus coverage-supported absent states."""
        fingerprint = self._fingerprint(
            "comparisons", query, exclude_cursor=True
        )
        after = self._decode_cursor(query.cursor, fingerprint)
        jurisdictions = sorted(query.jurisdictions)
        dimensions = sorted(dimension.value for dimension in query.dimensions)
        with self._connection() as connection:
            assertion_rows = self._comparison_assertions(
                connection, query, jurisdictions, dimensions
            )
            coverage_rows = self._comparison_coverage(
                connection, query, jurisdictions, dimensions
            )

        conclusions = self._build_conclusions(
            query, assertion_rows, coverage_rows
        )
        conclusions.sort(key=self._conclusion_key)
        page, next_cursor = self._paginate(
            conclusions, query.limit, after, fingerprint, self._conclusion_key
        )
        return ComparisonResponse(
            metadata=self._metadata(query, len(page), query.limit, next_cursor),
            conclusions=tuple(page),
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
            sql = """
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
                  AND dimension IN (SELECT unnest(?))
                GROUP BY jurisdiction, dimension, assertion_status
                ORDER BY jurisdiction, dimension, assertion_status
                """
        else:
            sql = """
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
                GROUP BY jurisdiction, dimension, assertion_status
                ORDER BY jurisdiction, dimension, assertion_status
                """
        with self._connection() as connection:
            rows = self._fetch_dicts(connection, sql, parameters)
        items = [self._coverage_item(query, row) for row in rows]
        page, next_cursor = self._paginate(
            items, query.limit, after, fingerprint, self._coverage_key
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
        if predicate == "assertion_id = ?":
            sql = self._evidence_sql_by_assertion()
        else:
            sql = self._evidence_sql_by_concept()
        with self._connection() as connection:
            rows = self._fetch_dicts(
                connection,
                sql,
                [
                    lookup_value,
                    query.valid_at,
                    query.valid_at,
                    query.observed_at,
                    query.observed_at,
                ],
            )
        items = [self._evidence_item(query, row) for row in rows]
        page, next_cursor = self._paginate(
            items, query.limit, after, fingerprint, self._evidence_key
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
    ) -> list[dict[str, Any]]:
        return self._fetch_dicts(
            connection,
            """
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
            ORDER BY jurisdiction, kind, assertion_id
            """,
            [
                query.concept_id,
                jurisdictions,
                dimensions,
                query.valid_at,
                query.valid_at,
                query.observed_at,
                query.observed_at,
            ],
        )

    def _comparison_coverage(
        self,
        connection: duckdb.DuckDBPyConnection,
        query: ComparisonQuery,
        jurisdictions: list[str],
        dimensions: list[str],
    ) -> list[dict[str, Any]]:
        return self._fetch_dicts(
            connection,
            """
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
            ORDER BY jurisdiction, dimension, medicine_concept_id NULLS LAST,
                     observation_id
            """,
            [
                jurisdictions,
                dimensions,
                query.concept_id,
                query.valid_at,
                query.valid_at,
                query.observed_at,
                query.observed_at,
            ],
        )

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
