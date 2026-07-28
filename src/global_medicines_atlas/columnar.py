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
        pa.field("valid_from", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("valid_to", pa.timestamp("us", tz="UTC"), nullable=True),
        pa.field("observed_from", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("observed_to", pa.timestamp("us", tz="UTC"), nullable=True),
        pa.field("supersedes_assertion_id", pa.string(), nullable=True),
        pa.field("conflict_id", pa.string(), nullable=True),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("source_uri", pa.string(), nullable=False),
    ],
    metadata={
        b"schema_name": b"global-medicines-atlas.temporal-assertions",
        b"schema_version": b"2",
    },
)


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
            "valid_from": item.valid_time.start,
            "valid_to": item.valid_time.end,
            "observed_from": item.observed_time.start,
            "observed_to": item.observed_time.end,
            "supersedes_assertion_id": item.supersedes_assertion_id,
            "conflict_id": item.conflict_id,
            "source_id": item.assertion.provenance.source_id,
            "source_uri": item.assertion.provenance.source_uri,
        }
        for item in assertions
    ]
    return pa.Table.from_pylist(rows, schema=TEMPORAL_ASSERTION_SCHEMA)


def temporal_assertions_as_of(
    table: pa.Table,
    *,
    valid_at: datetime,
    observed_at: datetime,
) -> pl.DataFrame:
    """Return assertions valid and observable at the two requested instants."""
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
