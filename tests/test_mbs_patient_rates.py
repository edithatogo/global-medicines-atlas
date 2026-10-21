"""Patient rates require exact denominator definitions and compatible scope."""

from datetime import date
from fractions import Fraction

import pytest
from pydantic import ValidationError
from test_mbs_measures import (
    _observation,  # ruff: ignore[import-private-name] -- synthetic fixture reuse
)

from global_medicines_atlas.mbs_patient_rates import (
    PatientDenominatorDefinition,
    patient_rate,
)


def definition(**overrides):
    values = {
        "source_sha256": "a" * 64,
        "native_measure_name": "Distinct patients",
        "evidence_sha256": "c" * 64,
        "population": "Synthetic eligible people",
        "deduplication": "Synthetic unique person per period",
        "coverage": "Synthetic complete population",
        "suppression_policy": "Synthetic none",
        "time_basis": "source_defined",
        "period_start": date(2025, 7, 1),
        "period_end": date(2026, 6, 30),
        "geography_code": "FIXTURE",
        "item_number": None,
    }
    return PatientDenominatorDefinition(**(values | overrides))


def service():
    return _observation(
        measure_kind="service_count",
        native_measure_name="Services",
        native_value="1",
        count_value=1,
    )


def test_missing_definition_does_not_erase_service_count():
    result = patient_rate(service(), _observation(), None)
    assert result.state == "unavailable"
    assert result.numerator_count == 1
    assert result.denominator_count is None
    assert result.value is None


def test_missing_denominator_and_service_denominator_are_unavailable():
    assert patient_rate(service(), None, definition()).state == "unavailable"
    assert (
        patient_rate(service(), service(), definition()).state == "unavailable"
    )


def test_exact_scoped_definition_allows_candidate_fraction_without_rounding():
    denominator = _observation(native_value="3", count_value=3)
    result = patient_rate(service(), denominator, definition())
    assert result.value == Fraction(1, 3)
    assert result.state == "available"
    assert result.qualification_state == "candidate_only"


def test_scope_and_identity_mismatches_remain_unavailable():
    denominator = _observation()
    for change in (
        {"source_sha256": "d" * 64},
        {"geography_code": "OTHER"},
        {"period_start": date(2025, 8, 1)},
    ):
        assert (
            patient_rate(service(), denominator, definition(**change)).state
            == "unavailable"
        )
    assert (
        patient_rate(
            service(), _observation(geography_code="OTHER"), definition()
        ).state
        == "unavailable"
    )


def test_zero_and_suppressed_counts_do_not_become_rates():
    assert (
        patient_rate(
            service(),
            _observation(native_value="0", count_value=0),
            definition(),
        ).state
        == "unavailable"
    )
    hidden = _observation(
        state="suppressed", native_value="<5", count_value=None
    )
    assert patient_rate(service(), hidden, definition()).state == "unavailable"
    assert (
        patient_rate(hidden, _observation(), definition()).state
        == "unavailable"
    )


def test_denominator_definition_rejects_reversed_period():
    with pytest.raises(ValidationError, match="precedes"):
        definition(period_end=date(2024, 1, 1))


def test_patient_counts_cannot_be_used_as_service_rate_numerator():
    patients = _observation()
    result = patient_rate(patients, patients, definition())
    assert result.state == "unavailable"
    assert result.value is None
    assert "service" in result.reason.lower()
