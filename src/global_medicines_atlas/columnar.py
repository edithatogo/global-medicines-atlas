"""Arrow-native materialisation and embedded analytical queries."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import duckdb
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from .models import CanonicalMedicineRecord

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
