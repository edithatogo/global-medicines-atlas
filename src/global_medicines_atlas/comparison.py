"""Evidence-preserving country comparisons over canonical temporal assertions."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    import polars as pl
    import pyarrow as pa


def compare_countries_as_of(
    table: pa.Table,
    *,
    concept_id: str,
    valid_at: datetime,
    observed_at: datetime,
) -> pl.DataFrame:
    """Compare explicit current evidence without filling absent dimensions."""
    if valid_at.tzinfo is None or observed_at.tzinfo is None:
        msg = "country comparison clocks must be timezone-aware"
        raise ValueError(msg)

    connection = duckdb.connect(":memory:")
    try:
        connection.register("temporal_assertions", table)
        return connection.execute(
            """
            SELECT
                jurisdiction,
                kind,
                CASE
                    WHEN bool_or(evidence_status = 'conflicting')
                        THEN 'conflicting'
                    WHEN bool_or(evidence_status = 'not_covered')
                        THEN 'not_covered'
                    WHEN bool_or(evidence_status = 'confirmed')
                        THEN 'confirmed'
                    ELSE 'explicit_other'
                END AS comparison_state,
                count(*)::BIGINT AS assertion_count,
                list_sort(list_distinct(list(status_code)))
                    AS status_codes,
                list_sort(list_distinct(list(source_id)))
                    AS source_ids,
                list_sort(
                    list_distinct(
                        list_filter(
                            list(conflict_id),
                            value -> value IS NOT NULL
                        )
                    )
                ) AS conflict_ids
            FROM temporal_assertions
            WHERE concept_id = ?
              AND valid_from <= ?
              AND (valid_to IS NULL OR ? < valid_to)
              AND observed_from <= ?
              AND (observed_to IS NULL OR ? < observed_to)
            GROUP BY jurisdiction, kind
            ORDER BY jurisdiction, kind
            """,
            [concept_id, valid_at, valid_at, observed_at, observed_at],
        ).pl()
    finally:
        connection.close()
