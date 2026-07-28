"""Temporal coverage denominator and aggregation tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from global_medicines_atlas.coverage import (
    COVERAGE_SCHEMA,
    CoverageObservation,
    aggregate_coverage,
    coverage_as_of,
    coverage_to_arrow,
    materialize_coverage_duckdb,
)
from global_medicines_atlas.models import AssertionKind, TimeInterval

START = datetime(2026, 1, 1, tzinfo=UTC)
OBSERVED = datetime(2026, 1, 2, tzinfo=UTC)


def observation(
    *,
    dimension: AssertionKind = AssertionKind.REGULATORY,
    valid_end: datetime | None = None,
    observed_end: datetime | None = None,
    numerator: int = 3,
    denominator: int | None = 5,
    exclusions: int = 1,
    reasons: tuple[str, ...] = ("withdrawn",),
    conflicts: int = 0,
    receipt_id: str = "receipt-medsafe-20260102",
    observation_id: str = "observation-1",
    partition_id: str = "partition-1",
    medicine_concept_id: str | None = "nzmt:mp-1",
    concept_population: str = "nzmt-mpu",
    assertion_type: str = "marketing-authorisation",
    assertion_status: str = "approved",
) -> CoverageObservation:
    return CoverageObservation(
        jurisdiction="NZL",
        source_id="medsafe",
        receipt_id=receipt_id,
        observation_id=observation_id,
        population_partition_id=partition_id,
        dimension=dimension,
        medicine_concept_id=medicine_concept_id,
        assertion_type=assertion_type,
        assertion_status=assertion_status,
        concept_population=concept_population,
        valid_time=TimeInterval(start=START, end=valid_end),
        observed_time=TimeInterval(start=OBSERVED, end=observed_end),
        assertion_count=4,
        concept_numerator=numerator,
        eligible_denominator=denominator,
        exclusion_count=exclusions,
        exclusion_reasons=reasons,
        conflicting_assertion_count=conflicts,
    )


def test_arrow_contract_is_versioned_and_keeps_counts_separate() -> None:
    table = coverage_to_arrow([observation(conflicts=2)])

    assert table.schema == COVERAGE_SCHEMA
    assert table.schema.metadata == {
        b"schema_name": b"global-medicines-atlas.temporal-coverage",
        b"schema_version": b"2",
    }
    row = table.to_pylist()[0]
    assert row["concept_numerator"] == 3
    assert row["receipt_id"] == "receipt-medsafe-20260102"
    assert row["observation_id"] == "observation-1"
    assert row["population_partition_id"] == "partition-1"
    assert row["medicine_concept_id"] == "nzmt:mp-1"
    assert row["assertion_type"] == "marketing-authorisation"
    assert row["assertion_status"] == "approved"
    assert row["eligible_denominator"] == 5
    assert row["exclusion_count"] == 1
    assert row["conflicting_assertion_count"] == 2


def test_unknown_denominator_remains_unknown_during_aggregation() -> None:
    frame = aggregate_coverage([
        observation(denominator=5, observation_id="known", partition_id="known"),
        observation(
            denominator=None,
            observation_id="unknown",
            partition_id="unknown",
        ),
    ])

    assert frame.height == 2
    assert (
        frame.filter(frame["observation_id"] == "unknown")[
            "eligible_denominator"
        ].item()
        is None
    )


def test_dimensions_are_never_combined() -> None:
    frame = aggregate_coverage([
        observation(dimension=AssertionKind.REGULATORY),
        observation(
            dimension=AssertionKind.FUNDING,
            observation_id="funding",
            partition_id="funding",
        ),
    ])

    assert frame.height == 2
    assert set(frame["dimension"]) == {"regulatory", "funding"}


def test_half_open_boundaries_apply_to_both_clocks() -> None:
    valid_end = START + timedelta(days=2)
    observed_end = OBSERVED + timedelta(days=2)
    frame = aggregate_coverage([
        observation(valid_end=valid_end, observed_end=observed_end)
    ])

    inside = coverage_as_of(
        frame,
        valid_at=valid_end - timedelta(microseconds=1),
        observed_at=observed_end - timedelta(microseconds=1),
    )
    at_valid_end = coverage_as_of(
        frame,
        valid_at=valid_end,
        observed_at=OBSERVED,
    )
    at_observed_end = coverage_as_of(
        frame,
        valid_at=START,
        observed_at=observed_end,
    )

    assert inside.height == 1
    assert at_valid_end.is_empty()
    assert at_observed_end.is_empty()


def test_disjoint_partitions_remain_independently_traceable() -> None:
    frame = aggregate_coverage([
        observation(numerator=2, conflicts=3),
        observation(
            numerator=1,
            conflicts=4,
            observation_id="observation-2",
            partition_id="partition-2",
        ),
    ])

    assert frame.height == 2
    assert frame["concept_numerator"].sum() == 3
    assert frame["conflicting_assertion_count"].sum() == 7


def test_duplicate_observation_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate observation_id"):
        aggregate_coverage([
            observation(partition_id="partition-1"),
            observation(partition_id="partition-2"),
        ])


def test_duplicate_population_partition_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate population partition"):
        aggregate_coverage([
            observation(observation_id="observation-1"),
            observation(observation_id="observation-2"),
        ])


def test_medicine_identity_is_required_except_for_aggregate_population() -> None:
    with pytest.raises(ValidationError, match="medicine_concept_id"):
        observation(medicine_concept_id=None)

    aggregate = observation(
        medicine_concept_id=None,
        concept_population="aggregate:nzmt-mpu",
    )
    assert aggregate.medicine_concept_id is None


def test_duckdb_views_preserve_unknown_denominators(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "coverage.duckdb"
    materialize_coverage_duckdb(
        [observation(denominator=None)],
        destination,
        valid_at=START,
        observed_at=OBSERVED,
    )

    with duckdb.connect(str(destination), read_only=True) as connection:
        current = connection.execute(
            "SELECT count(*) FROM current_temporal_coverage"
        ).fetchone()
        unknown = connection.execute(
            "SELECT count(*) FROM coverage_unknown_denominators"
        ).fetchone()
    assert current == (1,)
    assert unknown == (1,)


def test_numerator_above_denominator_is_rejected() -> None:
    with pytest.raises(ValidationError, match="concept_numerator"):
        observation(numerator=6, denominator=5)


def test_exclusions_without_reasons_are_rejected() -> None:
    with pytest.raises(ValidationError, match="exclusion reasons"):
        observation(exclusions=1, reasons=())


@given(
    first=st.integers(min_value=0, max_value=1_000),
    second=st.integers(min_value=0, max_value=1_000),
)
@pytest.mark.property
def test_aggregation_is_order_independent(first: int, second: int) -> None:
    observations = [
        observation(
            numerator=first,
            denominator=None,
            observation_id="first",
            partition_id="first",
        ),
        observation(
            numerator=second,
            denominator=None,
            observation_id="second",
            partition_id="second",
        ),
    ]

    forward = aggregate_coverage(observations)
    reverse = aggregate_coverage(reversed(observations))

    assert forward.equals(reverse)
    assert forward["concept_numerator"].sum() == first + second
