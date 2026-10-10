"""Source-bound aggregate count contracts, separate from patient-level data.

These candidates keep service counts distinct from distinct-patient counts.
A valid record does not qualify a source, its semantics, rights, coverage, or
the measure for publication.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import Literal

import pyarrow as pa
from pydantic import Field, model_validator

from .models import FrozenModel

MeasureKind = Literal["service_count", "distinct_patient_count"]
MeasureState = Literal["observed", "suppressed", "not_reported", "unavailable"]
TimeBasis = Literal["claim_processing_date", "service_date", "source_defined"]
QualificationState = Literal["candidate_only"]

MBS_MEASURE_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("source_revision", pa.string(), nullable=False),
        pa.field("source_path", pa.string(), nullable=False),
        pa.field("source_sha256", pa.string(), nullable=False),
        pa.field("source_receipt_sha256", pa.string(), nullable=False),
        pa.field("source_record_id", pa.string(), nullable=False),
        pa.field("measure_kind", pa.string(), nullable=False),
        pa.field("native_measure_name", pa.string(), nullable=False),
        pa.field("measure_definition_evidence", pa.string(), nullable=False),
        pa.field("state", pa.string(), nullable=False),
        pa.field("native_value", pa.string()),
        pa.field("count_value", pa.int64()),
        pa.field("period_label", pa.string(), nullable=False),
        pa.field("time_basis", pa.string(), nullable=False),
        pa.field("time_basis_evidence", pa.string()),
        pa.field("period_start", pa.date32()),
        pa.field("period_end", pa.date32()),
        pa.field("geography_code", pa.string()),
        pa.field("item_number", pa.string()),
        pa.field("qualification_state", pa.string(), nullable=False),
        pa.field("admission_performed", pa.bool_(), nullable=False),
        pa.field("publication_performed", pa.bool_(), nullable=False),
    ],
    metadata={
        b"gma.contract": b"mbs-aggregate-measures-v1",
        b"gma.qualification": b"candidate_only",
    },
)


class MbsMeasureObservation(FrozenModel):
    """One aggregate count bound to source identity and semantic evidence."""

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
    time_basis_evidence: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    geography_code: str | None = None
    item_number: str | None = None
    qualification_state: QualificationState = "candidate_only"
    admission_performed: Literal[False] = False
    publication_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_measure_contract(self) -> MbsMeasureObservation:
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("period bounds must be provided together")
        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_end < self.period_start
        ):
            raise ValueError("measure period end precedes start")
        if self.time_basis == "source_defined" and not self.time_basis_evidence:
            raise ValueError("source-defined time basis requires evidence")

        name_tokens = set(
            re.findall(r"[a-z0-9]+", self.native_measure_name.casefold())
        )
        if self.measure_kind == "distinct_patient_count" and name_tokens & {
            "service",
            "services",
            "claim",
            "claims",
        }:
            raise ValueError(
                "service or claim measure cannot represent distinct patients"
            )

        if self.state == "observed":
            if self.count_value is None or self.native_value is None:
                raise ValueError(
                    "observed measure requires native and typed values"
                )
            if re.fullmatch(r"[+-]?[0-9]+", self.native_value) is None:
                raise ValueError(
                    "observed native count must be an integer string"
                )
            if int(self.native_value) != self.count_value:
                raise ValueError("native count does not match typed count")
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


def observations_to_arrow(
    observations: Sequence[MbsMeasureObservation],
) -> pa.Table:
    """Create a typed source-faithful table without patient-level identifiers."""
    return pa.Table.from_pylist(
        [item.model_dump(mode="python") for item in observations],
        schema=MBS_MEASURE_SCHEMA,
    )
