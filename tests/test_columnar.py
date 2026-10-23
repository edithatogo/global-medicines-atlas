"""Arrow, Polars, Parquet, and DuckDB integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq
import pytest

from global_medicines_atlas import columnar as columnar_module
from global_medicines_atlas.columnar import (
    ASSERTION_SCHEMA,
    arrow_to_polars,
    coverage_by_jurisdiction,
    records_to_arrow,
    write_assertions_parquet,
)
from global_medicines_atlas.models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    MedicineConcept,
    Provenance,
    StatusAssertion,
)


def record() -> CanonicalMedicineRecord:
    provenance = Provenance(
        source_id="nz-medsafe",
        source_uri="https://example.invalid/record",
    )
    concept = MedicineConcept(
        concept_id="nz:1",
        jurisdiction="NZL",
        level="medicinal-product",
        preferred_name="Example medicine",
    )
    assertions = tuple(
        StatusAssertion(
            assertion_id=f"nz:1:{kind.value}",
            concept_id=concept.concept_id,
            jurisdiction=concept.jurisdiction,
            kind=kind,
            authority="Example authority",
            status_code="active",
            evidence_status=EvidenceStatus.CONFIRMED,
            provenance=provenance,
        )
        for kind in (AssertionKind.REGULATORY, AssertionKind.FUNDING)
    )
    return CanonicalMedicineRecord(
        concept=concept,
        assertions=assertions,
        provenance=(provenance,),
    )


def test_arrow_polars_duckdb_interoperate_without_pandas() -> None:
    table = records_to_arrow([record()])

    assert table.schema == ASSERTION_SCHEMA
    assert arrow_to_polars(table).get_column("kind").to_list() == [
        "regulatory",
        "funding",
    ]
    assert coverage_by_jurisdiction(table).to_dicts() == [
        {
            "jurisdiction": "NZL",
            "regulatory_assertions": 1,
            "funding_assertions": 1,
            "formulary_assertions": 0,
        }
    ]


def test_parquet_round_trip_preserves_schema_metadata(tmp_path: Path) -> None:
    destination = write_assertions_parquet(
        [record()], tmp_path / "assertions.parquet"
    )
    restored = pq.read_table(destination)

    assert restored.schema.metadata == ASSERTION_SCHEMA.metadata
    assert pl.read_parquet(destination).height == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    "case",
    [0, 1],
)
def test_duckdb_empty_arrow_result_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    case: int,
) -> None:
    class Result:
        def to_arrow_table(self) -> None:
            return None

    class Connection:
        def register(self, _name: str, _table: object) -> None:
            pass

        def execute(self, *_args: object) -> Result:
            return Result()

        def sql(self, *_args: object) -> Result:
            return Result()

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        columnar_module.duckdb, "connect", lambda *_: Connection()
    )
    table = records_to_arrow([record()])
    operations = (
        lambda: columnar_module.temporal_assertions_as_of(
            table,
            valid_at=datetime.now(UTC),
            observed_at=datetime.now(UTC),
        ),
        lambda: columnar_module.coverage_by_jurisdiction(table),
    )

    with pytest.raises(RuntimeError, match="no Arrow table"):
        operations[case]()
