"""Bitemporal evidence, conflict and Arrow contract tests."""

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from global_medicines_atlas.columnar import (
    ASSERTION_SCHEMA,
    TEMPORAL_ASSERTION_SCHEMA,
    materialize_temporal_duckdb,
    normalize_temporal_assertions,
    temporal_assertions_as_of,
    temporal_assertions_to_arrow,
    write_temporal_assertions_parquet,
)
from global_medicines_atlas.migrations import migrate_assertions_v1_to_v2
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
        restrictions=("special-authority",),
        provenance=Provenance(
            source_id="medsafe",
            source_uri="https://example.test/medsafe",
            retrieved_at=observed_from,
            effective_at=valid_from,
            source_path="fixtures/medsafe.csv",
            source_sha256="a" * 64,
            source_version="2025-01-02",
            transformation="medsafe-v1",
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
    assert table.column("observed_from").to_pylist()[0] == OBSERVED_FROM
    assert table.column("restrictions").to_pylist()[0] == ["special-authority"]
    assert table.column("source_sha256").to_pylist()[0] == "a" * 64
    assert table.column("source_effective_at").to_pylist()[0] == VALID_FROM
    assert table.column("transformation").to_pylist()[0] == "medsafe-v1"


def test_temporal_arrow_preserves_empty_iterable_compatibility() -> None:
    table = temporal_assertions_to_arrow([])

    assert table.schema == TEMPORAL_ASSERTION_SCHEMA
    assert table.num_rows == 0


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


def test_polars_reference_transform_is_canonically_ordered() -> None:
    table = temporal_assertions_to_arrow([
        temporal_assertion("z-last"),
        temporal_assertion("a-first"),
    ])

    frame = normalize_temporal_assertions(table)

    assert frame["assertion_id"].to_list() == ["a-first", "z-last"]
    assert frame.columns == TEMPORAL_ASSERTION_SCHEMA.names


def test_temporal_parquet_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.parquet"
    second = tmp_path / "second.parquet"
    assertions = [temporal_assertion("z-last"), temporal_assertion("a-first")]

    write_temporal_assertions_parquet(assertions, first)
    write_temporal_assertions_parquet(reversed(assertions), second)

    first_digest = sha256(first.read_bytes()).digest()
    second_digest = sha256(second.read_bytes()).digest()
    assert first_digest == second_digest
    assert pq.read_table(first).schema == TEMPORAL_ASSERTION_SCHEMA


def test_duckdb_materialization_exposes_deterministic_views(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "temporal.duckdb"
    table = temporal_assertions_to_arrow([
        temporal_assertion("z-last"),
        temporal_assertion("a-first"),
        temporal_assertion(
            "bounded-active",
            valid_to=VALID_FROM + timedelta(days=1),
            observed_to=OBSERVED_FROM + timedelta(days=1),
        ),
    ])

    materialize_temporal_duckdb(
        table,
        destination,
        valid_at=VALID_FROM,
        observed_at=OBSERVED_FROM,
    )

    with duckdb.connect(str(destination), read_only=True) as connection:
        query = """
            SELECT assertion_id
            FROM current_temporal_assertions
            ORDER BY assertion_id
        """
        rows = connection.execute(query).fetchall()
        conflicts = connection.execute(
            "SELECT count(*) FROM temporal_conflicts"
        ).fetchone()
    assert rows == [
        ("a-first",),
        ("bounded-active",),
        ("z-last",),
    ]
    assert conflicts == (0,)


def test_v1_migration_is_deterministic_and_backward_compatible() -> None:
    v1 = pa.Table.from_pylist(
        [
            {
                "assertion_id": "legacy-1",
                "concept_id": "nzmt:123",
                "jurisdiction": "NZL",
                "kind": "regulatory",
                "authority": "Medsafe",
                "status_code": "approved",
                "evidence_status": "confirmed",
                "source_id": "medsafe",
                "source_uri": "https://example.test/medsafe",
            }
        ],
        schema=ASSERTION_SCHEMA,
    )

    first = migrate_assertions_v1_to_v2(
        v1,
        valid_from=VALID_FROM,
        observed_from=OBSERVED_FROM,
    )
    second = migrate_assertions_v1_to_v2(
        v1,
        valid_from=VALID_FROM,
        observed_from=OBSERVED_FROM,
    )

    assert first.equals(second)
    assert first.schema == TEMPORAL_ASSERTION_SCHEMA
    assert first.column("valid_from").to_pylist()[0] == VALID_FROM
    assert first.column("valid_to").to_pylist()[0] is None


def test_v1_migration_requires_explicit_aware_clocks() -> None:
    empty_v1 = pa.Table.from_pylist([], schema=ASSERTION_SCHEMA)

    with pytest.raises(ValueError, match="timezone-aware"):
        migrate_assertions_v1_to_v2(
            empty_v1,
            valid_from=VALID_FROM.replace(tzinfo=None),
            observed_from=OBSERVED_FROM,
        )


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


def test_temporal_wrapper_rejects_mismatched_effective_end() -> None:
    effective_end = VALID_FROM + timedelta(days=2)
    bounded = temporal_assertion(valid_to=effective_end)
    assertion = bounded.assertion
    with pytest.raises(ValidationError, match=r"valid_time\.end"):
        TemporalStatusAssertion(
            assertion=assertion,
            valid_time=TimeInterval(
                start=VALID_FROM,
                end=VALID_FROM + timedelta(days=3),
            ),
            observed_time=TimeInterval(start=OBSERVED_FROM),
        )


def test_temporal_clocks_and_as_of_parameters_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        TimeInterval(start=VALID_FROM.replace(tzinfo=None))

    table = temporal_assertions_to_arrow([temporal_assertion()])
    with pytest.raises(ValueError, match="timezone-aware"):
        temporal_assertions_as_of(
            table,
            valid_at=VALID_FROM.replace(tzinfo=None),
            observed_at=OBSERVED_FROM,
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
