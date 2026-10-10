"""Source-neutral aggregate measure contracts use synthetic fixtures only."""

from datetime import date
from io import BytesIO

import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from global_medicines_atlas.mbs_measures import (
    MBS_MEASURE_SCHEMA,
    MbsMeasureObservation,
    observations_to_arrow,
)


def _observation(**overrides: object) -> MbsMeasureObservation:
    values: dict[str, object] = {
        "source_id": "fixture:aggregate-benefits",
        "source_revision": "fixture-revision-1",
        "source_path": "synthetic/aggregate.json#records/0",
        "source_sha256": "a" * 64,
        "source_receipt_sha256": "b" * 64,
        "source_record_id": "fixture-record-1",
        "measure_kind": "distinct_patient_count",
        "native_measure_name": "Distinct patients",
        "measure_definition_evidence": "synthetic fixture contract",
        "state": "observed",
        "native_value": "00123",
        "count_value": 123,
        "period_label": "2025-26",
        "time_basis": "source_defined",
        "time_basis_evidence": "synthetic fixture contract",
        "period_start": date(2025, 7, 1),
        "period_end": date(2026, 6, 30),
        "geography_code": "FIXTURE",
        "item_number": None,
    }
    values.update(overrides)
    return MbsMeasureObservation.model_validate(values)


def test_observed_count_requires_exact_typed_native_value_and_lineage() -> None:
    result = _observation()
    assert result.count_value == 123
    assert result.native_value == "00123"
    assert result.source_sha256 == "a" * 64
    assert result.qualification_state == "candidate_only"
    assert result.admission_performed is False
    assert result.publication_performed is False


@pytest.mark.parametrize("kind", ["service_count", "distinct_patient_count"])
@pytest.mark.parametrize(
    ("native_value", "count_value"), [("123", 124), ("1.2", 1)]
)
def test_observed_count_rejects_inconsistent_native_and_typed_values(
    kind: str, native_value: str, count_value: int
) -> None:
    with pytest.raises(ValidationError, match=r"does not match|integer string"):
        _observation(
            measure_kind=kind,
            native_measure_name=kind,
            native_value=native_value,
            count_value=count_value,
        )


@pytest.mark.parametrize(
    "name", ["services", "claims", "per-item service count"]
)
def test_service_or_claim_field_cannot_be_labeled_as_patients(
    name: str,
) -> None:
    with pytest.raises(
        ValidationError, match="cannot represent distinct patients"
    ):
        _observation(native_measure_name=name)


def test_negative_patients_are_rejected_but_adjustment_services_are_preserved() -> (
    None
):
    with pytest.raises(ValidationError, match="cannot be negative"):
        _observation(native_value="-1", count_value=-1)

    adjusted = _observation(
        measure_kind="service_count",
        native_measure_name="Services",
        native_value="-2",
        count_value=-2,
    )
    assert adjusted.count_value == -2


@pytest.mark.parametrize(
    ("state", "native_value"),
    [("suppressed", "<5"), ("not_reported", None), ("unavailable", None)],
)
def test_non_observed_states_remain_unknown(
    state: str, native_value: str | None
) -> None:
    result = _observation(
        state=state, native_value=native_value, count_value=None
    )
    assert result.count_value is None
    assert result.state == state


def test_period_bounds_must_be_complete_and_ordered() -> None:
    with pytest.raises(ValidationError, match="provided together"):
        _observation(period_end=None)
    with pytest.raises(ValidationError, match="precedes"):
        _observation(
            period_start=date(2026, 7, 1), period_end=date(2026, 6, 30)
        )


def test_arrow_projection_is_typed_deterministic_and_contains_no_person_fields() -> (
    None
):
    values = (
        _observation(),
        _observation(state="suppressed", native_value="<5", count_value=None),
    )
    table = observations_to_arrow(values)
    assert table.schema == MBS_MEASURE_SCHEMA
    assert table.column("state").to_pylist() == ["observed", "suppressed"]
    assert table.column("count_value").to_pylist() == [123, None]
    assert table.column("qualification_state").to_pylist() == [
        "candidate_only",
        "candidate_only",
    ]
    assert table.column("admission_performed").to_pylist() == [False, False]
    assert table.column("publication_performed").to_pylist() == [False, False]
    assert not any("patient_id" in name for name in table.column_names)
    assert observations_to_arrow(values) == table
    buffer = BytesIO()
    pq.write_table(table, buffer)  # pyright: ignore[reportUnknownMemberType]
    restored = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        BytesIO(buffer.getvalue())
    )
    assert restored.schema == MBS_MEASURE_SCHEMA
    assert restored.to_pylist() == table.to_pylist()


def test_extra_patient_level_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _observation(patient_identifier="synthetic-person-id")
