"""Arrow-native materialisation and embedded analytical queries."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import cast

import duckdb
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from .models import CanonicalMedicineRecord, TemporalStatusAssertion

ASSERTION_SCHEMA = pa.schema(
    [
        pa.field("assertion_id", pa.string(), nullable=False),
        pa.field("concept_id", pa.string(), nullable=False),
        pa.field("jurisdiction", pa.string(), nullable=False),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("authority", pa.string(), nullable=False),
        pa.field("status_code", pa.string(), nullable=False),
        pa.field("evidence_status", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("source_uri", pa.string(), nullable=False),
    ],
    metadata={
        b"schema_name": b"global-medicines-atlas.assertions",
        b"schema_version": b"1",
    },
)

TEMPORAL_ASSERTION_SCHEMA = pa.schema(
    [
        pa.field("assertion_id", pa.string(), nullable=False),
        pa.field("concept_id", pa.string(), nullable=False),
        pa.field("jurisdiction", pa.string(), nullable=False),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("authority", pa.string(), nullable=False),
        pa.field("status_code", pa.string(), nullable=False),
        pa.field("evidence_status", pa.string(), nullable=False),
        pa.field("restrictions", pa.list_(pa.string()), nullable=False),
        pa.field("valid_from", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("valid_to", pa.timestamp("us", tz="UTC"), nullable=True),
        pa.field("observed_from", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("observed_to", pa.timestamp("us", tz="UTC"), nullable=True),
        pa.field("supersedes_assertion_id", pa.string(), nullable=True),
        pa.field("conflict_id", pa.string(), nullable=True),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("source_uri", pa.string(), nullable=False),
        pa.field("retrieved_at", pa.timestamp("us", tz="UTC"), nullable=True),
        pa.field(
            "source_effective_at",
            pa.timestamp("us", tz="UTC"),
            nullable=True,
        ),
        pa.field("source_path", pa.string(), nullable=True),
        pa.field("source_sha256", pa.string(), nullable=True),
        pa.field("source_version", pa.string(), nullable=True),
        pa.field("transformation", pa.string(), nullable=True),
    ],
    metadata={
        b"schema_name": b"global-medicines-atlas.temporal-assertions",
        b"schema_version": b"2",
    },
)

TEMPORAL_SORT_COLUMNS = [
    "jurisdiction",
    "concept_id",
    "kind",
    "valid_from",
    "observed_from",
    "assertion_id",
]


def records_to_arrow(
    records: Iterable[CanonicalMedicineRecord],
) -> pa.Table:
    """Flatten validated records into a versioned Arrow assertion table."""
    rows = [
        {
            "assertion_id": assertion.assertion_id,
            "concept_id": assertion.concept_id,
            "jurisdiction": assertion.jurisdiction,
            "kind": assertion.kind.value,
            "authority": assertion.authority,
            "status_code": assertion.status_code,
            "evidence_status": assertion.evidence_status.value,
            "source_id": assertion.provenance.source_id,
            "source_uri": assertion.provenance.source_uri,
        }
        for record in records
        for assertion in record.assertions
    ]
    return pa.Table.from_pylist(rows, schema=ASSERTION_SCHEMA)


def temporal_assertions_to_arrow(
    assertions: Iterable[TemporalStatusAssertion],
) -> pa.Table:
    """Materialise bitemporal assertions into the versioned Arrow v2 schema."""
    rows = [
        {
            "assertion_id": item.assertion.assertion_id,
            "concept_id": item.assertion.concept_id,
            "jurisdiction": item.assertion.jurisdiction,
            "kind": item.assertion.kind.value,
            "authority": item.assertion.authority,
            "status_code": item.assertion.status_code,
            "evidence_status": item.assertion.evidence_status.value,
            "restrictions": list(item.assertion.restrictions),
            "valid_from": item.valid_time.start,
            "valid_to": item.valid_time.end,
            "observed_from": item.observed_time.start,
            "observed_to": item.observed_time.end,
            "supersedes_assertion_id": item.supersedes_assertion_id,
            "conflict_id": item.conflict_id,
            "source_id": item.assertion.provenance.source_id,
            "source_uri": item.assertion.provenance.source_uri,
            "retrieved_at": item.assertion.provenance.retrieved_at,
            "source_effective_at": item.assertion.provenance.effective_at,
            "source_path": item.assertion.provenance.source_path,
            "source_sha256": item.assertion.provenance.source_sha256,
            "source_version": item.assertion.provenance.source_version,
            "transformation": item.assertion.provenance.transformation,
        }
        for item in assertions
    ]
    if not rows:
        return pa.Table.from_pylist([], schema=TEMPORAL_ASSERTION_SCHEMA)
    return temporal_frame_to_arrow(
        pl.DataFrame(
            rows,
            schema_overrides={
                "valid_from": pl.Datetime("us", "UTC"),
                "valid_to": pl.Datetime("us", "UTC"),
                "observed_from": pl.Datetime("us", "UTC"),
                "observed_to": pl.Datetime("us", "UTC"),
                "retrieved_at": pl.Datetime("us", "UTC"),
                "source_effective_at": pl.Datetime("us", "UTC"),
            },
        )
    )


def normalize_temporal_assertions(table: pa.Table) -> pl.DataFrame:
    """Apply the canonical Polars projection and deterministic row ordering."""
    missing = set(TEMPORAL_ASSERTION_SCHEMA.names) - set(table.column_names)
    if missing:
        joined = ", ".join(sorted(missing))
        msg = f"temporal assertion table is missing columns: {joined}"
        raise ValueError(msg)

    frame = cast("pl.DataFrame", pl.from_arrow(table))
    selected = frame.select(TEMPORAL_ASSERTION_SCHEMA.names)
    return selected.sort(TEMPORAL_SORT_COLUMNS)


def temporal_frame_to_arrow(frame: pl.DataFrame) -> pa.Table:
    """Convert a Polars temporal frame to the canonical Arrow v2 contract."""
    table = frame.to_arrow()
    normalized = normalize_temporal_assertions(table)
    return pa.Table.from_pylist(
        normalized.to_dicts(),
        schema=TEMPORAL_ASSERTION_SCHEMA,
    )


def temporal_assertions_as_of(
    table: pa.Table,
    *,
    valid_at: datetime,
    observed_at: datetime,
) -> pl.DataFrame:
    """Return assertions valid and observable at the two requested instants."""
    if valid_at.tzinfo is None or observed_at.tzinfo is None:
        msg = "as-of query clocks must be timezone-aware"
        raise ValueError(msg)
    connection = duckdb.connect(":memory:")
    try:
        connection.register("temporal_assertions", table)
        return connection.execute(
            """
            SELECT *
            FROM temporal_assertions
            WHERE valid_from <= ?
              AND (valid_to IS NULL OR ? < valid_to)
              AND observed_from <= ?
              AND (observed_to IS NULL OR ? < observed_to)
            ORDER BY jurisdiction, concept_id, kind, assertion_id
            """,
            [valid_at, valid_at, observed_at, observed_at],
        ).pl()
    finally:
        connection.close()


def write_temporal_assertions_parquet(
    assertions: Iterable[TemporalStatusAssertion],
    destination: Path,
) -> Path:
    """Write canonical assertions as deterministic Parquet."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        temporal_assertions_to_arrow(assertions),
        destination,
        compression="zstd",
        compression_level=9,
        use_dictionary=False,
        write_statistics=True,
        data_page_version="2.0",
    )
    return destination


def materialize_temporal_duckdb(
    table: pa.Table,
    destination: Path,
    *,
    valid_at: datetime,
    observed_at: datetime,
) -> Path:
    """Create reproducible DuckDB tables and current-evidence view."""
    if valid_at.tzinfo is None or observed_at.tzinfo is None:
        msg = "DuckDB materialization clocks must be timezone-aware"
        raise ValueError(msg)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    normalized = temporal_frame_to_arrow(normalize_temporal_assertions(table))
    connection = duckdb.connect(str(destination))
    try:
        connection.register("incoming_temporal_assertions", normalized)
        connection.execute(
            """
            CREATE TABLE temporal_assertions AS
            SELECT * FROM incoming_temporal_assertions
            ORDER BY jurisdiction, concept_id, kind, valid_from,
                     observed_from, assertion_id
            """
        )
        connection.execute(
            """
            CREATE TABLE temporal_reference_clock (
                valid_at TIMESTAMPTZ NOT NULL,
                observed_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO temporal_reference_clock VALUES (?, ?)",
            [valid_at, observed_at],
        )
        connection.execute(
            """
            CREATE VIEW current_temporal_assertions AS
            SELECT assertions.*
            FROM temporal_assertions AS assertions
            CROSS JOIN temporal_reference_clock AS reference
            WHERE assertions.valid_from <= reference.valid_at
              AND (
                assertions.valid_to IS NULL
                OR reference.valid_at < assertions.valid_to
              )
              AND assertions.observed_from <= reference.observed_at
              AND (
                assertions.observed_to IS NULL
                OR reference.observed_at < assertions.observed_to
              )
            """
        )
        connection.execute(
            """
            CREATE VIEW temporal_conflicts AS
            SELECT *
            FROM temporal_assertions
            WHERE conflict_id IS NOT NULL
            """
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    return destination


def arrow_to_polars(table: pa.Table) -> pl.DataFrame:
    """Expose the canonical table through the Rust-native Polars engine."""
    return cast("pl.DataFrame", pl.from_arrow(table))


def write_assertions_parquet(
    records: Iterable[CanonicalMedicineRecord],
    destination: Path,
) -> Path:
    """Write deterministic, compressed portable assertion data."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        records_to_arrow(records),
        destination,
        compression="zstd",
        write_statistics=True,
    )
    return destination


def coverage_by_jurisdiction(table: pa.Table) -> pl.DataFrame:
    """Compute regulatory/funding/formulary counts with embedded DuckDB."""
    connection = duckdb.connect(":memory:")
    try:
        connection.register("assertions", table)
        return connection.sql(
            """
            SELECT
                jurisdiction,
                count(*) FILTER (WHERE kind = 'regulatory')::BIGINT
                    AS regulatory_assertions,
                count(*) FILTER (WHERE kind = 'funding')::BIGINT
                    AS funding_assertions,
                count(*) FILTER (WHERE kind = 'formulary')::BIGINT
                    AS formulary_assertions
            FROM assertions
            GROUP BY jurisdiction
            ORDER BY jurisdiction
            """
        ).pl()
    finally:
        connection.close()
