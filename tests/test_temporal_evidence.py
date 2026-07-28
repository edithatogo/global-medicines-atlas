"""Bitemporal evidence, conflict and Arrow contract tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pyarrow as pa
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from global_medicines_atlas.columnar import (
    TEMPORAL_ASSERTION_SCHEMA,
    temporal_assertions_as_of,
    temporal_assertions_to_arrow,
)
from global_medicines_atlas.models import (
    AssertionKind,
    EvidenceConflict,
    EvidenceStatus,
    Provenance,
    StatusAssertion,
    TemporalStatusAssertion,
    TimeInterval,
)

VALID_FROM = datetime(2025, 1, 1, tzinfo=UTC)
OBSERVED_FROM = datetime(2025, 1, 2, tzinfo=UTC)


def temporal_assertion(
    assertion_id: str = "nz-reg-1",
    *,
    valid_from: datetime = VALID_FROM,
    valid_to: datetime | None = None,
    observed_from: datetime = OBSERVED_FROM,
    observed_to: datetime | None = None,
) -> TemporalStatusAssertion:
    assertion = StatusAssertion(
        assertion_id=assertion_id,
        concept_id="nzmt:123",
        jurisdiction="NZL",
        kind=AssertionKind.REGULATORY,
        authority="Medsafe",
        status_code="approved",
        evidence_status=EvidenceStatus.CONFIRMED,
        effective_from=valid_from,
        effective_to=valid_to,
        provenance=Provenance(
            source_id="medsafe",
            source_uri="https://example.test/medsafe",
            retrieved_at=observed_from,
        ),
    )
    return TemporalStatusAssertion(
        assertion=assertion,
        valid_time=TimeInterval(start=valid_from, end=valid_to),
        observed_time=TimeInterval(start=observed_from, end=observed_to),
    )


def test_temporal_arrow_schema_is_versioned_and_preserves_both_clocks() -> None:
    table = temporal_assertions_to_arrow([temporal_assertion()])

    assert table.schema == TEMPORAL_ASSERTION_SCHEMA
    assert table.schema.metadata == {
        b"schema_name": b"global-medicines-atlas.temporal-assertions",
        b"schema_version": b"2",
    }
    assert pa.types.is_timestamp(table.schema.field("valid_from").type)
    assert table.column("observed_from")[0].as_py() == OBSERVED_FROM


def test_as_of_query_uses_half_open_valid_and_observed_intervals() -> None:
    table = temporal_assertions_to_arrow([
        temporal_assertion(
            valid_to=VALID_FROM + timedelta(days=10),
            observed_to=OBSERVED_FROM + timedelta(days=20),
        )
    ])

    visible = temporal_assertions_as_of(
        table,
        valid_at=VALID_FROM + timedelta(days=9),
        observed_at=OBSERVED_FROM + timedelta(days=19),
    )
    expired = temporal_assertions_as_of(
        table,
        valid_at=VALID_FROM + timedelta(days=10),
        observed_at=OBSERVED_FROM + timedelta(days=19),
    )

    assert visible["assertion_id"].to_list() == ["nz-reg-1"]
    assert expired.is_empty()


def test_conflicts_require_two_unique_assertions() -> None:
    with pytest.raises(ValidationError, match="at least 2"):
        EvidenceConflict(
            conflict_id="conflict-1",
            concept_id="nzmt:123",
            kind=AssertionKind.REGULATORY,
            assertion_ids=("a",),
            reason="Source disagreement",
        )
    with pytest.raises(ValidationError, match="must be unique"):
        EvidenceConflict(
            conflict_id="conflict-1",
            concept_id="nzmt:123",
            kind=AssertionKind.REGULATORY,
            assertion_ids=("a", "a"),
            reason="Source disagreement",
        )


def test_temporal_wrapper_rejects_mismatched_source_effective_time() -> None:
    with pytest.raises(ValidationError, match=r"valid_time\.start"):
        TemporalStatusAssertion(
            assertion=temporal_assertion().assertion,
            valid_time=TimeInterval(start=VALID_FROM + timedelta(days=1)),
            observed_time=TimeInterval(start=OBSERVED_FROM),
        )


@given(st.integers(min_value=1, max_value=10_000))
def test_half_open_intervals_accept_positive_duration(seconds: int) -> None:
    interval = TimeInterval(
        start=VALID_FROM,
        end=VALID_FROM + timedelta(seconds=seconds),
    )
    assert interval.end is not None
    assert interval.end > interval.start


@given(st.integers(min_value=0, max_value=10_000))
def test_intervals_reject_non_positive_duration(seconds: int) -> None:
    with pytest.raises(ValidationError, match="must follow"):
        TimeInterval(
            start=VALID_FROM + timedelta(seconds=seconds),
            end=VALID_FROM,
        )
