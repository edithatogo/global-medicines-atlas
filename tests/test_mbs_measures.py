"""Keep aggregate MBS patient measures distinct from service counts."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from global_medicines_atlas.mbs_measures import MbsMeasureObservation


def _observation(**overrides: object) -> MbsMeasureObservation:
    values: dict[str, object] = {
        "source_id": "au-health-medicare-statistics",
        "source_revision": "sha256:revision-marker",
        "source_path": "annual/state-territory.xlsx#patients",
        "source_sha256": "a" * 64,
        "source_receipt_sha256": "b" * 64,
        "source_record_id": "sheet:patients!A2",
        "measure_kind": "distinct_patient_count",
        "native_measure_name": "Patients",
        "measure_definition_evidence": "https://example.invalid/measure-notes",
        "state": "observed",
        "native_value": "123",
        "count_value": 123,
        "period_label": "2025-26",
        "time_basis": "claim_processing_date",
        "period_start": date(2025, 7, 1),
        "period_end": date(2026, 6, 30),
        "geography_code": "AUS",
        "item_number": None,
    }
    values.update(overrides)
    return MbsMeasureObservation.model_validate(values)


def test_patient_count_requires_explicit_semantics_and_source_lineage() -> None:
    result = _observation()

    assert result.measure_kind == "distinct_patient_count"
    assert result.count_value == 123
    assert result.source_sha256 == "a" * 64
    assert result.measure_definition_evidence
    assert "distinct_patient_count" in str(
        MbsMeasureObservation.model_json_schema()
    )


@pytest.mark.parametrize(
    "native_name",
    ["Services", "service_count", "Claims", "per-item service total"],
)
def test_service_measure_cannot_be_relabelled_as_distinct_patients(
    native_name: str,
) -> None:
    with pytest.raises(ValidationError, match="service-count field"):
        _observation(native_measure_name=native_name)


def test_negative_patient_counts_are_rejected_but_adjusted_services_are_retained() -> (
    None
):
    with pytest.raises(ValidationError, match="cannot be negative"):
        _observation(count_value=-1, native_value="-1")

    services = _observation(
        measure_kind="service_count",
        native_measure_name="Services",
        measure_definition_evidence="https://example.invalid/service-notes",
        count_value=-2,
        native_value="-2",
    )
    assert services.count_value == -2


@pytest.mark.parametrize(
    ("state", "native_value", "count_value"),
    [
        ("suppressed", "<5", None),
        ("not_reported", None, None),
        ("unavailable", None, None),
    ],
)
def test_non_observed_measures_never_become_zero(
    state: str, native_value: str | None, count_value: int | None
) -> None:
    result = _observation(
        state=state,
        native_value=native_value,
        count_value=count_value,
    )

    assert result.count_value is None
    assert result.state == state


@pytest.mark.parametrize(
    ("state", "native_value", "count_value", "message"),
    [
        ("observed", None, 123, "observed measure requires"),
        ("observed", "123", None, "observed measure requires"),
        ("suppressed", None, None, "suppressed measure must preserve"),
        ("not_reported", "123", None, "unreported measure cannot carry"),
        ("unavailable", "123", None, "unreported measure cannot carry"),
        ("not_reported", None, 123, "non-observed measure cannot have"),
    ],
)
def test_inconsistent_measure_states_are_rejected(
    state: str,
    native_value: str | None,
    count_value: int | None,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _observation(
            state=state,
            native_value=native_value,
            count_value=count_value,
        )


def test_period_and_unmodeled_patient_identifiers_fail_closed() -> None:
    with pytest.raises(ValidationError, match="period end precedes start"):
        _observation(
            period_start=date(2026, 7, 1), period_end=date(2026, 6, 30)
        )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        _observation(patient_identifier="must-not-be-retained")
