"""Source-independent medicine, status, and provenance contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AssertionKind(StrEnum):
    REGULATORY = "regulatory"
    FUNDING = "funding"
    FORMULARY = "formulary"


class EvidenceStatus(StrEnum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"
    NOT_COVERED = "not_covered"
    NOT_APPLICABLE = "not_applicable"


class Identifier(FrozenModel):
    system: str = Field(min_length=1)
    value: str = Field(min_length=1)
    identifier_type: str | None = None


class Provenance(FrozenModel):
    source_id: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    retrieved_at: datetime | None = None
    effective_at: datetime | None = None
    source_path: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_version: str | None = None
    transformation: str | None = None


class MedicineConcept(FrozenModel):
    concept_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    level: str = Field(min_length=1)
    preferred_name: str = Field(min_length=1)
    identifiers: tuple[Identifier, ...] = ()
    related_concept_ids: tuple[str, ...] = ()


class StatusAssertion(FrozenModel):
    assertion_id: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    kind: AssertionKind
    authority: str = Field(min_length=1)
    status_code: str = Field(min_length=1)
    evidence_status: EvidenceStatus
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    restrictions: tuple[str, ...] = ()
    provenance: Provenance


class TimeInterval(FrozenModel):
    """Half-open temporal interval with an optional unbounded end."""

    start: AwareDatetime
    end: AwareDatetime | None = None

    @model_validator(mode="after")
    def end_follows_start(self) -> TimeInterval:
        if self.end is not None and self.end <= self.start:
            raise ValueError("Temporal interval end must follow its start")
        return self


class TemporalStatusAssertion(FrozenModel):
    """A status assertion with independent valid and observation time."""

    assertion: StatusAssertion
    valid_time: TimeInterval
    observed_time: TimeInterval
    supersedes_assertion_id: str | None = None
    conflict_id: str | None = None

    @model_validator(mode="after")
    def temporal_fields_match_assertion(self) -> TemporalStatusAssertion:
        assertion = self.assertion
        if assertion.effective_from != self.valid_time.start:
            message = "valid_time.start must match "
            message += "assertion.effective_from"
            raise ValueError(message)
        if assertion.effective_to != self.valid_time.end:
            raise ValueError("valid_time.end must match assertion.effective_to")
        return self


class EvidenceConflict(FrozenModel):
    """Explicit grouping of materially conflicting source assertions."""

    conflict_id: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    kind: AssertionKind
    assertion_ids: tuple[str, ...] = Field(min_length=2)
    reason: str = Field(min_length=1)
    resolution_status: str = Field(default="unresolved", min_length=1)

    @model_validator(mode="after")
    def assertion_ids_are_unique(self) -> EvidenceConflict:
        if len(self.assertion_ids) != len(set(self.assertion_ids)):
            raise ValueError("Conflict assertion identifiers must be unique")
        return self


class CanonicalMedicineRecord(FrozenModel):
    concept: MedicineConcept
    assertions: tuple[StatusAssertion, ...] = ()
    provenance: tuple[Provenance, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def assertions_target_record_concept(self) -> CanonicalMedicineRecord:
        if any(
            assertion.concept_id != self.concept.concept_id
            for assertion in self.assertions
        ):
            raise ValueError("Every assertion must target the record concept")
        return self
