"""Source-bound aggregate MBS count observations.

The contract keeps service volumes distinct from counts of distinct people.
It describes a candidate projection shape; a valid instance does not qualify
its source, semantics, rights, or coverage.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenModel

MeasureKind = Literal["service_count", "distinct_patient_count"]
MeasureState = Literal["observed", "suppressed", "not_reported", "unavailable"]
TimeBasis = Literal["claim_processing_date", "service_date", "source_defined"]


class MbsMeasureObservation(FrozenModel):
    """One aggregate count, bound to source identity and semantic evidence."""

    schema_version: Literal["1.0"] = "1.0"
    source_id: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_id: str = Field(min_length=1)
    measure_kind: MeasureKind
    native_measure_name: str = Field(min_length=1)
    measure_definition_evidence: str = Field(min_length=1)
    state: MeasureState
    native_value: str | None = None
    count_value: int | None = None
    period_label: str = Field(min_length=1)
    time_basis: TimeBasis
    period_start: date | None = None
    period_end: date | None = None
    geography_code: str | None = None
    item_number: str | None = None

    @model_validator(mode="after")
    def validate_count_semantics(self) -> MbsMeasureObservation:
        if (
            self.period_start
            and self.period_end
            and self.period_end < self.period_start
        ):
            raise ValueError("measure period end precedes start")

        source_name_tokens = set(
            re.findall(r"[a-z0-9]+", self.native_measure_name.casefold())
        )
        if (
            self.measure_kind == "distinct_patient_count"
            and source_name_tokens & {"service", "services", "claim", "claims"}
        ):
            raise ValueError(
                "service-count field cannot represent distinct patients"
            )

        if self.state == "observed":
            if self.count_value is None or self.native_value is None:
                raise ValueError(
                    "observed measure requires native and typed values"
                )
            if (
                self.measure_kind == "distinct_patient_count"
                and self.count_value < 0
            ):
                raise ValueError("distinct-patient count cannot be negative")
        elif self.count_value is not None:
            raise ValueError("non-observed measure cannot have a typed count")

        if self.state == "suppressed" and self.native_value is None:
            raise ValueError(
                "suppressed measure must preserve its source marker"
            )
        if (
            self.state in {"not_reported", "unavailable"}
            and self.native_value is not None
        ):
            raise ValueError("unreported measure cannot carry a native value")
        return self
