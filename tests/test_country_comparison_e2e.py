"""End-to-end country comparisons through canonical Parquet and DuckDB."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import duckdb
import pyarrow.parquet as pq

from global_medicines_atlas.columnar import (
    materialize_temporal_duckdb,
    write_temporal_assertions_parquet,
)
from global_medicines_atlas.comparison import compare_countries_as_of
from global_medicines_atlas.models import (
    AssertionKind,
    EvidenceStatus,
    Provenance,
    StatusAssertion,
    TemporalStatusAssertion,
    TimeInterval,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "country_comparison"
    / "temporal_assertions.json"
)
VALID_AT = datetime(2025, 3, 1, tzinfo=UTC)
OBSERVED_AT = datetime(2025, 3, 1, tzinfo=UTC)


def load_assertions() -> list[TemporalStatusAssertion]:
    """Load source-shaped fixture rows into canonical temporal models."""
    raw = cast("list[dict[str, Any]]", json.loads(FIXTURE.read_text()))
    assertions: list[TemporalStatusAssertion] = []
    for row in raw:
        valid_from = datetime.fromisoformat(cast("str", row["valid_from"]))
        observed_from = datetime.fromisoformat(
            cast("str", row["observed_from"])
        )
        assertion = StatusAssertion(
            assertion_id=cast("str", row["assertion_id"]),
            concept_id=cast("str", row["concept_id"]),
            jurisdiction=cast("str", row["jurisdiction"]),
            kind=AssertionKind(cast("str", row["kind"])),
            authority=cast("str", row["authority"]),
            status_code=cast("str", row["status_code"]),
            evidence_status=EvidenceStatus(cast("str", row["evidence_status"])),
            effective_from=valid_from,
            provenance=Provenance(
                source_id=cast("str", row["source_id"]),
                source_uri=cast("str", row["source_uri"]),
                retrieved_at=observed_from,
            ),
        )
        assertions.append(
            TemporalStatusAssertion(
                assertion=assertion,
                valid_time=TimeInterval(start=valid_from),
                observed_time=TimeInterval(start=observed_from),
                conflict_id=cast("str | None", row.get("conflict_id")),
            )
        )
    return assertions


def test_parquet_country_comparison_preserves_conflicts_and_scope(
    tmp_path: Path,
) -> None:
    parquet_path = write_temporal_assertions_parquet(
        load_assertions(),
        tmp_path / "country-comparison.parquet",
    )

    comparison = compare_countries_as_of(
        pq.read_table(parquet_path),
        concept_id="rxnorm:860975",
        valid_at=VALID_AT,
        observed_at=OBSERVED_AT,
    )

    assert comparison.to_dicts() == [
        {
            "jurisdiction": "AUS",
            "kind": "regulatory",
            "comparison_state": "conflicting",
            "assertion_count": 2,
            "status_codes": ["cancelled", "registered"],
            "source_ids": ["au-artg", "au-artg-cancellations"],
            "conflict_ids": ["aus-registration-conflict"],
        },
        {
            "jurisdiction": "NZL",
            "kind": "funding",
            "comparison_state": "confirmed",
            "assertion_count": 1,
            "status_codes": ["funded_with_restrictions"],
            "source_ids": ["nz-pharmac"],
            "conflict_ids": [],
        },
        {
            "jurisdiction": "NZL",
            "kind": "regulatory",
            "comparison_state": "confirmed",
            "assertion_count": 1,
            "status_codes": ["approved"],
            "source_ids": ["nz-medsafe"],
            "conflict_ids": [],
        },
        {
            "jurisdiction": "USA",
            "kind": "funding",
            "comparison_state": "not_covered",
            "assertion_count": 1,
            "status_codes": ["no_single_national_funding_determination"],
            "source_ids": ["us-funding-scope-declaration"],
            "conflict_ids": [],
        },
        {
            "jurisdiction": "USA",
            "kind": "regulatory",
            "comparison_state": "confirmed",
            "assertion_count": 1,
            "status_codes": ["approved"],
            "source_ids": ["us-drugs-at-fda"],
            "conflict_ids": [],
        },
    ]


def test_duckdb_comparison_never_infers_missing_funding(
    tmp_path: Path,
) -> None:
    assertions = [
        item
        for item in load_assertions()
        if item.assertion.assertion_id != "usa-funding-scope"
    ]
    parquet_path = write_temporal_assertions_parquet(
        assertions,
        tmp_path / "country-comparison-with-gap.parquet",
    )
    table = pq.read_table(parquet_path)
    database = materialize_temporal_duckdb(
        table,
        tmp_path / "country-comparison.duckdb",
        valid_at=VALID_AT,
        observed_at=OBSERVED_AT,
    )

    comparison = compare_countries_as_of(
        table,
        concept_id="rxnorm:860975",
        valid_at=VALID_AT,
        observed_at=OBSERVED_AT,
    )
    usa_funding = comparison.filter(
        (comparison["jurisdiction"] == "USA")
        & (comparison["kind"] == "funding")
    )
    with duckdb.connect(str(database), read_only=True) as connection:
        persisted_usa_funding = connection.execute(
            """
            SELECT count(*)
            FROM current_temporal_assertions
            WHERE jurisdiction = 'USA' AND kind = 'funding'
            """
        ).fetchone()

    assert usa_funding.is_empty()
    assert persisted_usa_funding == (0,)
