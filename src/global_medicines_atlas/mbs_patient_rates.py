"""Candidate patient-rate availability with explicit denominator evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from typing import Literal

from pydantic import Field, model_validator

from .mbs_measures import MbsMeasureObservation, TimeBasis
from .models import FrozenModel
from .silver_field_semantics import Digest


class PatientDenominatorDefinition(FrozenModel):
    """Declared source-specific definition; construction does not review it."""

    source_sha256: Digest
    native_measure_name: str = Field(min_length=1)
    evidence_sha256: Digest
    population: str = Field(min_length=1)
    deduplication: str = Field(min_length=1)
    coverage: str = Field(min_length=1)
    suppression_policy: str = Field(min_length=1)
    time_basis: TimeBasis
    period_start: date
    period_end: date
    geography_code: str | None
    item_number: str | None

    @model_validator(mode="after")
    def ordered_period(self) -> PatientDenominatorDefinition:
        if self.period_end < self.period_start:
            raise ValueError("denominator period end precedes start")
        return self


@dataclass(frozen=True)
class PatientRateAvailability:
    """Unavailable is never zero; available arithmetic remains candidate-only."""

    state: Literal["available", "unavailable"]
    numerator_count: int | None
    denominator_count: int | None
    value: Fraction | None
    reason: str
    qualification_state: Literal["candidate_only"] = "candidate_only"


def _scope(
    value: MbsMeasureObservation | PatientDenominatorDefinition,
) -> tuple[TimeBasis, date | None, date | None, str | None, str | None]:
    return (
        value.time_basis,
        value.period_start,
        value.period_end,
        value.geography_code,
        value.item_number,
    )


def patient_rate(
    numerator: MbsMeasureObservation,
    denominator: MbsMeasureObservation | None,
    definition: PatientDenominatorDefinition | None,
) -> PatientRateAvailability:
    """Keep services visible while withholding unsupported service-per-patient rates.

    This conservative operation supports measures in the same immutable source
    record and exact population scope. Cross-source or cross-record cohorts
    need a separate qualified linkage and are not silently assumed here.
    """
    numerator = MbsMeasureObservation.model_validate(numerator.model_dump())

    def unavailable(reason: str) -> PatientRateAvailability:
        return PatientRateAvailability(
            "unavailable", numerator.count_value, None, None, reason
        )

    if numerator.measure_kind != "service_count":
        return unavailable(
            "A service-per-patient rate requires a service numerator"
        )
    if denominator is None or definition is None:
        return unavailable("Patient denominator or definition is unavailable")
    denominator = MbsMeasureObservation.model_validate(denominator.model_dump())
    definition = PatientDenominatorDefinition.model_validate(
        definition.model_dump()
    )
    if denominator.measure_kind != "distinct_patient_count":
        return unavailable("A service count cannot supply distinct patients")
    if (
        numerator.state != "observed"
        or denominator.state != "observed"
        or numerator.count_value is None
        or denominator.count_value is None
        or denominator.count_value <= 0
    ):
        return unavailable(
            "Observed counts and positive denominator are required"
        )
    definition_identity = (
        definition.source_sha256,
        definition.native_measure_name,
        _scope(definition),
    )
    denominator_identity = (
        denominator.source_sha256,
        denominator.native_measure_name,
        _scope(denominator),
    )
    numerator_record = (
        numerator.source_sha256,
        numerator.source_record_id,
        numerator.source_revision,
        _scope(numerator),
    )
    denominator_record = (
        denominator.source_sha256,
        denominator.source_record_id,
        denominator.source_revision,
        _scope(denominator),
    )
    if (
        definition_identity != denominator_identity
        or numerator_record != denominator_record
    ):
        return unavailable(
            "Denominator definition or source scope does not match"
        )
    return PatientRateAvailability(
        "available",
        numerator.count_value,
        denominator.count_value,
        Fraction(numerator.count_value, denominator.count_value),
        "Candidate arithmetic using an explicit scoped denominator definition",
    )
