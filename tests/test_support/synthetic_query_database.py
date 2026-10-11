"""Small, deterministic DuckDB fixture shared by service and consumer tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def create_synthetic_query_database(path: Path) -> Path:
    """Create the existing synthetic query fixture without importing pytest."""
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE temporal_assertions (
            assertion_id VARCHAR NOT NULL,
            concept_id VARCHAR NOT NULL,
            jurisdiction VARCHAR NOT NULL,
            kind VARCHAR NOT NULL,
            authority VARCHAR NOT NULL,
            status_code VARCHAR NOT NULL,
            evidence_status VARCHAR NOT NULL,
            restrictions VARCHAR[] NOT NULL,
            valid_from TIMESTAMPTZ NOT NULL,
            valid_to TIMESTAMPTZ,
            observed_from TIMESTAMPTZ NOT NULL,
            observed_to TIMESTAMPTZ,
            supersedes_assertion_id VARCHAR,
            conflict_id VARCHAR,
            source_id VARCHAR NOT NULL,
            source_uri VARCHAR NOT NULL,
            retrieved_at TIMESTAMPTZ,
            source_effective_at TIMESTAMPTZ,
            source_path VARCHAR,
            source_sha256 VARCHAR,
            source_version VARCHAR,
            transformation VARCHAR
        );
        CREATE TABLE temporal_coverage (
            jurisdiction VARCHAR NOT NULL,
            source_id VARCHAR NOT NULL,
            receipt_id VARCHAR NOT NULL,
            observation_id VARCHAR NOT NULL,
            population_partition_id VARCHAR NOT NULL,
            dimension VARCHAR NOT NULL,
            medicine_concept_id VARCHAR,
            assertion_type VARCHAR NOT NULL,
            assertion_status VARCHAR NOT NULL,
            concept_population VARCHAR NOT NULL,
            valid_from TIMESTAMPTZ NOT NULL,
            valid_to TIMESTAMPTZ,
            observed_from TIMESTAMPTZ NOT NULL,
            observed_to TIMESTAMPTZ,
            assertion_count BIGINT NOT NULL,
            concept_numerator BIGINT NOT NULL,
            eligible_denominator BIGINT,
            exclusion_count BIGINT NOT NULL,
            exclusion_reasons VARCHAR[] NOT NULL,
            conflicting_assertion_count BIGINT NOT NULL
        )
        """
    )
    assertions: list[tuple[Any, ...]] = [
        (
            "a-nz-reg",
            "rx:1",
            "NZ",
            "regulatory",
            "Medsafe",
            "approved",
            "confirmed",
            [],
            NOW,
            None,
            NOW,
            None,
            None,
            None,
            "medsafe",
            "https://example.test/medsafe/1",
            NOW,
            None,
            None,
            "a" * 64,
            "2026-07",
            "nz-adapter-v1",
        ),
        (
            "a-nz-fund",
            "rx:1",
            "NZ",
            "funding",
            "Pharmac",
            "funded",
            "confirmed",
            [],
            NOW,
            None,
            NOW,
            None,
            None,
            None,
            "pharmac",
            "https://example.test/pharmac/1",
            NOW,
            None,
            None,
            None,
            "2026-07",
            "nz-adapter-v1",
        ),
        (
            "a-au-reg",
            "rx:1",
            "AU",
            "regulatory",
            "TGA",
            "registered",
            "confirmed",
            [],
            NOW,
            None,
            NOW,
            None,
            None,
            None,
            "artg",
            "https://example.test/artg/1",
            NOW,
            None,
            None,
            None,
            "2026-07",
            "au-adapter-v1",
        ),
    ]
    connection.executemany(
        """
        INSERT INTO temporal_assertions VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        assertions,
    )
    coverage: list[tuple[Any, ...]] = [
        (
            "AU",
            "pbs",
            "receipt-au",
            "obs-au-funding",
            "all",
            "funding",
            "rx:1",
            "medicine",
            "not_covered",
            "all listed medicines",
            NOW,
            None,
            NOW,
            None,
            0,
            0,
            100,
            0,
            [],
            0,
        ),
        (
            "US",
            "fda",
            "receipt-us",
            "obs-us-reg",
            "all",
            "regulatory",
            "rx:1",
            "medicine",
            "unknown",
            "all observed medicines",
            NOW,
            None,
            NOW,
            None,
            0,
            0,
            None,
            0,
            [],
            0,
        ),
    ]
    connection.executemany(
        """
        INSERT INTO temporal_coverage VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        coverage,
    )
    connection.close()
    return path
