"""Coverage-denominator contracts and deterministic columnar aggregation."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import duckdb
import polars as pl
import pyarrow as pa
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from .models import AssertionKind, TimeInterval

COVERAGE_SCHEMA = pa.schema(
    [
        pa.field("jurisdiction", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("receipt_id", pa.string(), nullable=False),
        pa.field("observation_id", pa.string(), nullable=False),
        pa.field("population_partition_id", pa.string(), nullable=False),
        pa.field("dimension", pa.string(), nullable=False),
        pa.field("medicine_concept_id", pa.string()),
        pa.field("assertion_type", pa.string(), nullable=False),
        pa.field("assertion_status", pa.string(), nullable=False),
        pa.field("concept_population", pa.string(), nullable=False),
        pa.field("valid_from", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("valid_to", pa.timestamp("us", tz="UTC")),
        pa.field("observed_from", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("observed_to", pa.timestamp("us", tz="UTC")),
        pa.field("assertion_count", pa.int64(), nullable=False),
        pa.field("concept_numerator", pa.int64(), nullable=False),
        pa.field("eligible_denominator", pa.int64()),
        pa.field("exclusion_count", pa.int64(), nullable=False),
        pa.field("exclusion_reasons", pa.list_(pa.string()), nullable=False),
        pa.field("conflicting_assertion_count", pa.int64(), nullable=False),
    ],
    metadata={
        b"schema_name": b"global-medicines-atlas.temporal-coverage",
        b"schema_version": b"2",
    },
)

_KEY_COLUMNS = [
    "jurisdiction",
    "source_id",
    "receipt_id",
    "observation_id",
    "population_partition_id",
    "dimension",
    "medicine_concept_id",
    "assertion_type",
    "assertion_status",
    "concept_population",
    "valid_from",
    "valid_to",
    "observed_from",
    "observed_to",
]


class CoverageObservation(BaseModel):
    """One source's coverage evidence for one dimension and population."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    jurisdiction: str = Field(min_length=2, max_length=3)
    source_id: str = Field(min_length=1)
    receipt_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    population_partition_id: str = Field(min_length=1)
    dimension: AssertionKind
    medicine_concept_id: str | None = Field(default=None, min_length=1)
    assertion_type: str = Field(min_length=1)
    assertion_status: str = Field(min_length=1)
    concept_population: str = Field(min_length=1)
    valid_time: TimeInterval
    observed_time: TimeInterval
    assertion_count: int = Field(ge=0)
    concept_numerator: int = Field(ge=0)
    eligible_denominator: int | None = Field(default=None, ge=0)
    exclusion_count: int = Field(default=0, ge=0)
    exclusion_reasons: tuple[str, ...] = ()
    conflicting_assertion_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def counts_are_coherent(self) -> CoverageObservation:
        if (
            self.medicine_concept_id is None
            and not self.concept_population.startswith("aggregate:")
        ):
            raise ValueError(
                "medicine_concept_id may be omitted only for an aggregate population"
            )
        if (
            self.eligible_denominator is not None
            and self.concept_numerator > self.eligible_denominator
        ):
            raise ValueError(
                "concept_numerator cannot exceed eligible_denominator"
            )
        if self.exclusion_count > 0 and not self.exclusion_reasons:
            raise ValueError(
                "exclusion reasons are required when exclusions exist"
            )
        if any(not reason.strip() for reason in self.exclusion_reasons):
            raise ValueError("exclusion reasons must not be blank")
        if not self.assertion_type.strip() or not self.assertion_status.strip():
            raise ValueError("assertion identity values must not be blank")
        return self


def _row(observation: CoverageObservation) -> dict[str, object]:
    return {
        "jurisdiction": observation.jurisdiction,
        "source_id": observation.source_id,
        "receipt_id": observation.receipt_id,
        "observation_id": observation.observation_id,
        "population_partition_id": observation.population_partition_id,
        "dimension": observation.dimension.value,
        "medicine_concept_id": observation.medicine_concept_id,
        "assertion_type": observation.assertion_type,
        "assertion_status": observation.assertion_status,
        "concept_population": observation.concept_population,
        "valid_from": observation.valid_time.start,
        "valid_to": observation.valid_time.end,
        "observed_from": observation.observed_time.start,
        "observed_to": observation.observed_time.end,
        "assertion_count": observation.assertion_count,
        "concept_numerator": observation.concept_numerator,
        "eligible_denominator": observation.eligible_denominator,
        "exclusion_count": observation.exclusion_count,
        "exclusion_reasons": sorted(set(observation.exclusion_reasons)),
        "conflicting_assertion_count": observation.conflicting_assertion_count,
    }


def aggregate_coverage(
    observations: Iterable[CoverageObservation],
) -> pl.DataFrame:
    """Normalize disjoint coverage partitions without inventing denominators."""

    materialized = list(observations)
    observation_ids = [item.observation_id for item in materialized]
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError("duplicate observation_id")

    partition_keys = [
        (
            item.jurisdiction,
            item.source_id,
            item.dimension,
            item.medicine_concept_id,
            item.assertion_type,
            item.assertion_status,
            item.concept_population,
            item.valid_time,
            item.observed_time,
            item.population_partition_id,
        )
        for item in materialized
    ]
    if len(partition_keys) != len(set(partition_keys)):
        raise ValueError("duplicate population partition")

    rows = [_row(observation) for observation in materialized]
    if not rows:
        empty = pl.from_arrow(pa.Table.from_pylist([], schema=COVERAGE_SCHEMA))
        return cast("pl.DataFrame", empty)

    frame = pl.from_dicts(rows, schema=pl.Schema(COVERAGE_SCHEMA))
    return frame.select(COVERAGE_SCHEMA.names).sort(
        _KEY_COLUMNS, nulls_last=True
    )


def coverage_as_of(
    coverage: pl.DataFrame,
    *,
    valid_at: AwareDatetime,
    observed_at: AwareDatetime,
) -> pl.DataFrame:
    """Select rows visible at both half-open temporal coordinates."""

    return coverage.filter(
        (pl.col("valid_from") <= valid_at)
        & (pl.col("valid_to").is_null() | (valid_at < pl.col("valid_to")))
        & (pl.col("observed_from") <= observed_at)
        & (
            pl.col("observed_to").is_null()
            | (observed_at < pl.col("observed_to"))
        )
    )


def coverage_to_arrow(
    observations: Iterable[CoverageObservation],
) -> pa.Table:
    """Return deterministic coverage data with versioned Arrow metadata."""

    frame = aggregate_coverage(observations)
    return pa.Table.from_pylist(frame.to_dicts(), schema=COVERAGE_SCHEMA)


def materialize_coverage_duckdb(
    observations: Iterable[CoverageObservation],
    destination: Path,
    *,
    valid_at: AwareDatetime,
    observed_at: AwareDatetime,
) -> Path:
    """Materialize deterministic coverage and explicit-clock views."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    table = coverage_to_arrow(observations)
    connection = duckdb.connect(str(destination))
    try:
        connection.register("incoming_coverage", table)
        connection.execute(
            """
            CREATE TABLE temporal_coverage AS
            SELECT * FROM incoming_coverage
            ORDER BY jurisdiction, source_id, receipt_id, observation_id,
                     population_partition_id, dimension, medicine_concept_id,
                     assertion_type, assertion_status, concept_population,
                     valid_from, observed_from
            """
        )
        connection.execute(
            """
            CREATE TABLE coverage_reference_clock (
                valid_at TIMESTAMPTZ NOT NULL,
                observed_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO coverage_reference_clock VALUES (?, ?)",
            [valid_at, observed_at],
        )
        connection.execute(
            """
            CREATE VIEW current_temporal_coverage AS
            SELECT coverage.*
            FROM temporal_coverage AS coverage
            CROSS JOIN coverage_reference_clock AS reference
            WHERE coverage.valid_from <= reference.valid_at
              AND (
                coverage.valid_to IS NULL
                OR reference.valid_at < coverage.valid_to
              )
              AND coverage.observed_from <= reference.observed_at
              AND (
                coverage.observed_to IS NULL
                OR reference.observed_at < coverage.observed_to
              )
            """
        )
        connection.execute(
            """
            CREATE VIEW coverage_unknown_denominators AS
            SELECT *
            FROM current_temporal_coverage
            WHERE eligible_denominator IS NULL
            """
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    return destination
