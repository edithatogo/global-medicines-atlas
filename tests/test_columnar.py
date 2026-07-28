"""Arrow, Polars, Parquet, and DuckDB integration tests."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pyarrow.parquet as pq

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
    destination = write_assertions_parquet([record()], tmp_path / "assertions.parquet")
    restored = pq.read_table(destination)

    assert restored.schema.metadata == ASSERTION_SCHEMA.metadata
    assert pl.read_parquet(destination).height == 2
