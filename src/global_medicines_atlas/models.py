"""Source-independent medicine, status, and provenance contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
