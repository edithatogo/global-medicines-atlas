"""Deterministic compatibility migrations for canonical columnar schemas."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

import polars as pl

from .columnar import (
    ASSERTION_SCHEMA,
    TEMPORAL_ASSERTION_SCHEMA,
    temporal_frame_to_arrow,
)

if TYPE_CHECKING:
    import pyarrow as pa


def migrate_assertions_v1_to_v2(
    table: pa.Table,
    *,
    valid_from: datetime,
    observed_from: datetime,
) -> pa.Table:
    """Promote schema-v1 assertions to v2 using explicit migration clocks.

    V1 contains no temporal bounds. Callers must supply deterministic UTC
    instants from source-effective and snapshot metadata; the migration never
    substitutes wall-clock time.
    """
    if table.schema != ASSERTION_SCHEMA:
        msg = "expected the canonical assertion schema v1"
        raise ValueError(msg)
    if valid_from.tzinfo is None or observed_from.tzinfo is None:
        msg = "migration clocks must be timezone-aware"
        raise ValueError(msg)

    utc_timestamp = pl.Datetime("us", "UTC")
    frame = cast("pl.DataFrame", pl.from_arrow(table)).with_columns(
        pl.lit(valid_from).alias("valid_from"),
        pl.lit(None, dtype=utc_timestamp).alias("valid_to"),
        pl.lit(observed_from).alias("observed_from"),
        pl.lit(None, dtype=utc_timestamp).alias("observed_to"),
        pl.lit(None, dtype=pl.String).alias("supersedes_assertion_id"),
        pl.lit(None, dtype=pl.String).alias("conflict_id"),
        pl.lit([], dtype=pl.List(pl.String)).alias("restrictions"),
        pl.lit(None, dtype=utc_timestamp).alias("retrieved_at"),
        pl.lit(None, dtype=utc_timestamp).alias("source_effective_at"),
        pl.lit(None, dtype=pl.String).alias("source_path"),
        pl.lit(None, dtype=pl.String).alias("source_sha256"),
        pl.lit(None, dtype=pl.String).alias("source_version"),
        pl.lit(None, dtype=pl.String).alias("transformation"),
    )
    selected = frame.select(TEMPORAL_ASSERTION_SCHEMA.names)
    return temporal_frame_to_arrow(selected)
