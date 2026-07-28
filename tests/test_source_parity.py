from __future__ import annotations

import pytest

from global_medicines_atlas.ingestors import ProjectionOutcome
from global_medicines_atlas.models import (
    CanonicalMedicineRecord,
    MedicineConcept,
    Provenance,
)
from global_medicines_atlas.parity import ParityStatus, compare_projections


def record(concept_id: str, name: str = "Medicine") -> CanonicalMedicineRecord:
    return CanonicalMedicineRecord(
        concept=MedicineConcept(
            concept_id=concept_id,
            jurisdiction="CAN",
            level="product",
            preferred_name=name,
        ),
        provenance=(
            Provenance(
                source_id="health-canada-dpd",
                source_uri="https://example.test/dpd",
            ),
        ),
    )


def outcome(
    *records: CanonicalMedicineRecord,
    source_id: str = "health-canada-dpd-api",
    population_id: str = "all-active-products",
    projection_id: str = "dpd-v1",
    schema_fingerprint: str = "a" * 64,
) -> ProjectionOutcome:
    return ProjectionOutcome(
        source_id=source_id,
        jurisdiction="CAN",
        projection_id=projection_id,
        population_id=population_id,
        payload_set_digest="b" * 64,
        receipt_ids=(f"receipt-{source_id}",),
        schema_fingerprint=schema_fingerprint,
        records=records,
    )


@pytest.mark.unit
def test_equal_api_and_bulk_projections_are_equivalent() -> None:
    api = outcome(record("ca:1"), source_id="dpd-api")
    bulk = outcome(record("ca:1"), source_id="dpd-bulk")

    result = compare_projections(api, bulk)

    assert result.status is ParityStatus.EQUIVALENT
    assert result.is_equivalent
    assert not result.only_left
    assert not result.changed


@pytest.mark.unit
def test_parity_reports_missing_and_changed_records() -> None:
    left = outcome(record("ca:1"), record("ca:2"))
    right = outcome(record("ca:1", "Renamed"), record("ca:3"))

    result = compare_projections(left, right)

    assert result.status is ParityStatus.DIFFERENT
    assert result.only_left == ("ca:2",)
    assert result.only_right == ("ca:3",)
    assert result.changed == ("ca:1",)


@pytest.mark.edge
@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("population_id", "approved-products-only", "populations"),
        ("projection_id", "dpd-v2", "projection versions"),
        ("schema_fingerprint", "c" * 64, "logical schemas"),
    ],
)
def test_parity_refuses_incompatible_claims(
    field: str,
    value: str,
    reason: str,
) -> None:
    baseline = outcome(record("ca:1"))
    changed = baseline.model_copy(update={field: value})

    result = compare_projections(baseline, changed)

    assert result.status is ParityStatus.NOT_COMPARABLE
    assert any(reason in item for item in result.reasons)
    assert not result.is_equivalent


@pytest.mark.edge
def test_parity_refuses_cross_jurisdiction_comparison() -> None:
    baseline = outcome(record("ca:1"))
    australian_record = record("au:1").model_copy(
        update={
            "concept": record("au:1").concept.model_copy(
                update={"jurisdiction": "AUS"}
            )
        }
    )
    australian = baseline.model_copy(
        update={
            "jurisdiction": "AUS",
            "records": (australian_record,),
        }
    )

    result = compare_projections(baseline, australian)

    assert result.status is ParityStatus.NOT_COMPARABLE
    assert "jurisdictions differ" in result.reasons
