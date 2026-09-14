"""Read-only v2 comparison adapter over the canonical temporal tables."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from .platinum_v2_contracts import (
    V2ComparisonQuery,
    V2ComparisonResponse,
    V2Conclusion,
    V2EvidenceDimension,
    V2EvidenceItem,
    V2EvidenceQuery,
    V2EvidenceResponse,
    V2ResponseMetadata,
)
from .product_contracts import (
    AsOfClocks,
    EvidenceAvailability,
    PageMetadata,
    ProductState,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)
from .query_service import ReadOnlyQueryService


class V2ReadOnlyQueryService(ReadOnlyQueryService):
    """Expose five independent dimensions without changing the v1 surface."""

    def v2_evidence(self, query: V2EvidenceQuery) -> V2EvidenceResponse:
        """Return the complete selected V2 assertion stream in bounded pages."""
        fingerprint = self._fingerprint(
            "v2_evidence", cast("Any", query), exclude_cursor=True
        )
        after = self._decode_cursor(query.cursor, fingerprint)
        parameters: list[object] = [
            query.concept_id,
            query.jurisdiction,
            query.dimension.value,
            query.valid_at,
            query.valid_at,
            query.observed_at,
            query.observed_at,
        ]
        keyset = ""
        if after is not None:
            parameters.extend(after)
            keyset = "AND assertion_id > ?"
        parameters.append(query.limit + 1)
        with self._connection() as connection:
            rows = self._fetch_dicts(
                connection,
                f"""
                SELECT assertion_id, concept_id, jurisdiction, kind, authority,
                       status_code, evidence_status, source_id, source_uri,
                       CAST(retrieved_at AS VARCHAR) AS retrieved_at,
                       CAST(observed_from AS VARCHAR) AS observed_from,
                       source_sha256, source_version, transformation
                FROM temporal_assertions
                WHERE concept_id = ?
                  AND jurisdiction = ?
                  AND kind = ?
                  AND valid_from <= ?
                  AND (valid_to IS NULL OR ? < valid_to)
                  AND observed_from <= ?
                  AND (observed_to IS NULL OR ? < observed_to)
                  {keyset}
                ORDER BY assertion_id
                LIMIT ?
                """,  # ruff: ignore[hardcoded-sql-expression]
                parameters,
            )
        items = [self._v2_evidence_item(query, row) for row in rows]
        has_more = len(items) > query.limit
        page = items[: query.limit]
        next_cursor = (
            self._encode_cursor(fingerprint, (page[-1].assertion_id,))
            if has_more and page
            else None
        )
        return V2EvidenceResponse(
            metadata=V2ResponseMetadata(
                generated_at=datetime.now(UTC),
                clocks=AsOfClocks(
                    valid_at=query.valid_at, observed_at=query.observed_at
                ),
                page=PageMetadata(
                    limit=query.limit,
                    returned=len(page),
                    next_cursor=next_cursor,
                ),
            ),
            evidence=tuple(page),
        )

    def v2_comparisons(self, query: V2ComparisonQuery) -> V2ComparisonResponse:
        fingerprint = self._fingerprint(
            "v2_comparisons", cast("Any", query), exclude_cursor=True
        )
        after = self._decode_cursor(query.cursor, fingerprint)
        jurisdictions = sorted(query.jurisdictions)
        dimensions = sorted(dimension.value for dimension in query.dimensions)
        with self._connection() as connection:
            assertions = self._comparison_assertions(
                connection, cast("Any", query), jurisdictions, dimensions
            )
            coverage = self._comparison_coverage(
                connection, cast("Any", query), jurisdictions, dimensions
            )
            candidate_keys = self._v2_comparison_page_keys(
                connection, query, jurisdictions, dimensions, after
            )
        page_keys = set(candidate_keys[: query.limit])
        conclusions = [
            item
            for item in self._build_v2_conclusions(query, assertions, coverage)
            if (item.jurisdiction, item.dimension.value, item.concept_id)
            in page_keys
        ]
        has_more = len(candidate_keys) > query.limit
        next_cursor = (
            self._encode_cursor(fingerprint, candidate_keys[query.limit - 1])
            if has_more and candidate_keys
            else None
        )
        return V2ComparisonResponse(
            metadata=V2ResponseMetadata(
                generated_at=datetime.now(UTC),
                clocks=AsOfClocks(
                    valid_at=query.valid_at, observed_at=query.observed_at
                ),
                page=PageMetadata(
                    limit=query.limit,
                    returned=len(conclusions),
                    next_cursor=next_cursor,
                ),
            ),
            conclusions=tuple(conclusions),
        )

    def _build_v2_conclusions(
        self,
        query: V2ComparisonQuery,
        assertion_rows: Sequence[Mapping[str, Any]],
        coverage_rows: Sequence[Mapping[str, Any]],
    ) -> list[V2Conclusion]:
        grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        for row in assertion_rows:
            grouped.setdefault(
                (str(row["jurisdiction"]), str(row["kind"])), []
            ).append(row)
        covered = {
            (str(row["jurisdiction"]), str(row["dimension"])): row
            for row in coverage_rows
        }
        output: list[V2Conclusion] = []
        for jurisdiction in query.jurisdictions:
            for dimension in query.dimensions:
                rows = grouped.get((jurisdiction, dimension.value), [])
                if rows:
                    output.append(self._v2_assertion_conclusion(query, rows))
                elif coverage_row := covered.get((
                    jurisdiction,
                    dimension.value,
                )):
                    output.append(
                        self._v2_coverage_conclusion(
                            query, jurisdiction, dimension, coverage_row
                        )
                    )
                else:
                    output.append(
                        self._v2_missing_conclusion(
                            query, jurisdiction, dimension
                        )
                    )
        return output

    @staticmethod
    def _v2_comparison_page_keys(
        connection: Any,
        query: V2ComparisonQuery,
        jurisdictions: list[str],
        dimensions: list[str],
        after: tuple[str, ...] | None,
    ) -> list[tuple[str, str, str]]:
        parameters: list[object] = [
            query.concept_id,
            jurisdictions,
            dimensions,
        ]
        keyset = ""
        if after is not None:
            parameters.extend(after)
            keyset = (
                "WHERE (jurisdiction, dimension, concept_id) > ($4, $5, $6)"
            )
        parameters.append(query.limit + 1)
        rows = connection.execute(
            f"""
            WITH requested AS (
                SELECT jurisdiction, dimension
                FROM unnest($2) AS jurisdictions(jurisdiction)
                CROSS JOIN unnest($3) AS dimensions(dimension)
            )
            SELECT jurisdiction, dimension, $1 AS concept_id
            FROM requested
            {keyset}
            ORDER BY jurisdiction, dimension, concept_id
            LIMIT ${len(parameters)}
            """,  # ruff: ignore[hardcoded-sql-expression]
            parameters,
        ).fetchall()
        return [
            (str(jurisdiction), str(dimension), str(concept_id))
            for jurisdiction, dimension, concept_id in rows
        ]

    @staticmethod
    def _v2_missing_conclusion(
        query: V2ComparisonQuery,
        jurisdiction: str,
        dimension: V2EvidenceDimension,
    ) -> V2Conclusion:
        return V2Conclusion(
            concept_id=query.concept_id,
            jurisdiction=jurisdiction,
            dimension=dimension,
            state=ProductState.UNKNOWN,
            terminology=Terminology(
                native_code=dimension.value,
                native_label=dimension.value.replace("_", " "),
                native_system="global-medicines-atlas",
                canonical_code=query.concept_id,
                canonical_label=query.concept_id,
                canonical_system="global-medicines-atlas",
            ),
            evidence_availability=EvidenceAvailability.UNAVAILABLE,
            evidence_unavailable_reason=(
                "No source assertion or coverage observation is available for "
                "this requested dimension."
            ),
            uncertainty=Uncertainty(
                level=UncertaintyLevel.UNKNOWN,
                reason="Missing coverage is not evidence of a negative status.",
            ),
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )

    def _v2_assertion_conclusion(
        self,
        query: V2ComparisonQuery,
        rows: Sequence[Mapping[str, Any]],
    ) -> V2Conclusion:
        first = rows[0]
        state = self._state(str(first["evidence_status"]))
        if (
            int(first["has_conflicting_state"])
            or int(first["distinct_status_total"]) > 1
        ):
            state = ProductState.CONFLICTING
        dimension = V2EvidenceDimension(str(first["kind"]))
        uncertainty = (
            Uncertainty(
                level=UncertaintyLevel.MEDIUM,
                reason="Comparison provenance is capped; use V2 evidence paging.",
            )
            if int(first["evidence_total"]) > len(rows)
            else self._uncertainty(state)
        )
        return V2Conclusion(
            concept_id=query.concept_id,
            jurisdiction=str(first["jurisdiction"]),
            dimension=dimension,
            state=state,
            status_code=(
                None
                if state in {ProductState.UNKNOWN, ProductState.NOT_COVERED}
                else str(first["status_code"])
            ),
            terminology=self._terminology(first),
            provenance=tuple(self._provenance(row) for row in rows),
            evidence_availability=EvidenceAvailability.AVAILABLE,
            uncertainty=uncertainty,
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )

    def _v2_evidence_item(
        self, query: V2EvidenceQuery, row: Mapping[str, Any]
    ) -> V2EvidenceItem:
        state = self._state(str(row["evidence_status"]))
        return V2EvidenceItem(
            assertion_id=str(row["assertion_id"]),
            concept_id=str(row["concept_id"]),
            jurisdiction=str(row["jurisdiction"]),
            dimension=V2EvidenceDimension(str(row["kind"])),
            state=state,
            status_code=str(row["status_code"]),
            terminology=self._terminology(row),
            provenance=self._provenance(row),
            uncertainty=self._uncertainty(state),
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )

    def _v2_coverage_conclusion(
        self,
        query: V2ComparisonQuery,
        jurisdiction: str,
        dimension: V2EvidenceDimension,
        row: Mapping[str, Any],
    ) -> V2Conclusion:
        explicit = str(row["assertion_status"]).casefold()
        state = (
            ProductState.NOT_COVERED
            if explicit == ProductState.NOT_COVERED.value
            else ProductState.UNKNOWN
        )
        return V2Conclusion(
            concept_id=query.concept_id,
            jurisdiction=jurisdiction,
            dimension=dimension,
            state=state,
            terminology=Terminology(
                native_code=explicit,
                native_label=explicit.replace("_", " "),
                native_system=str(row["source_id"]),
                canonical_code=query.concept_id,
                canonical_label=query.concept_id,
                canonical_system="global-medicines-atlas",
            ),
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
