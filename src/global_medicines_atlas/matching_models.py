"""Review-first contracts for cross-jurisdiction medicine matching."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from .models import FrozenModel, Identifier


class MappingLevel(StrEnum):
    INGREDIENT = "ingredient"
    CLINICAL_DRUG = "clinical_drug"
    MEDICINAL_PRODUCT = "medicinal_product"
    PRESENTATION = "presentation"
    PACK = "pack"


class CandidateMethod(StrEnum):
    IDENTIFIER = "identifier"
    LEXICAL = "lexical"
    RXNORM = "rxnorm"
    SEMANTIC = "semantic"
    ENSEMBLE = "ensemble"


class ReviewState(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_INFORMATION = "needs_information"
    SUPERSEDED = "superseded"


class AbstentionReason(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    AMBIGUOUS_CANDIDATES = "ambiguous_candidates"
    CONFLICTING_IDENTIFIERS = "conflicting_identifiers"
    INCOMPATIBLE_LEVEL = "incompatible_level"
    MISSING_REQUIRED_ATTRIBUTE = "missing_required_attribute"
    OUTSIDE_INDEX_COVERAGE = "outside_index_coverage"


class EvaluationClass(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    AMBIGUOUS = "ambiguous"


class MappingEndpoint(FrozenModel):
    concept_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    level: MappingLevel
    preferred_name: str = Field(min_length=1)
    language: str = Field(min_length=2)
    identifiers: tuple[Identifier, ...] = ()
    provenance_ids: tuple[str, ...] = Field(min_length=1)


class FeatureContribution(FrozenModel):
    feature: str = Field(min_length=1)
    value: float
    contribution: float
    explanation: str = Field(min_length=1)


class MappingCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    source: MappingEndpoint
    target: MappingEndpoint
    method: CandidateMethod
    features: tuple[FeatureContribution, ...] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    calibration_version: str = Field(min_length=1)
    index_version: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    review_state: Literal[ReviewState.PENDING_REVIEW] = (
        ReviewState.PENDING_REVIEW
    )
    abstention_reason: AbstentionReason | None = None
    generated_at: AwareDatetime
    is_therapeutic_equivalence_claim: bool = False

    @model_validator(mode="after")
    def enforce_matching_boundaries(self) -> MappingCandidate:
        if self.source.jurisdiction == self.target.jurisdiction:
            raise ValueError("Candidate endpoints must cross jurisdictions")
        if self.source.level is not self.target.level:
            raise ValueError(
                "Candidate endpoints must use the same mapping level"
            )
        names = [feature.feature for feature in self.features]
        if len(names) != len(set(names)):
            raise ValueError("Feature names must be unique and ordered")
        if self.is_therapeutic_equivalence_claim:
            raise ValueError("Therapeutic equivalence claims are out of scope")
        if (
            self.abstention_reason is not None
            and self.review_state is not ReviewState.PENDING_REVIEW
        ):
            raise ValueError("Abstained candidates must remain pending review")
        return self


class AdjudicationEvent(FrozenModel):
    event_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    state: ReviewState
    occurred_at: AwareDatetime
    reviewer_id: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    supersedes_event_id: str | None = None

    @staticmethod
    def content_id(
        *,
        candidate_id: str,
        state: ReviewState,
        occurred_at: datetime,
        reviewer_id: str,
        rationale: str,
        supersedes_event_id: str | None,
    ) -> str:
        """Return the digest of every immutable event field."""
        payload = json.dumps(
            {
                "candidate_id": candidate_id,
                "occurred_at": occurred_at.isoformat(),
                "rationale": rationale,
                "reviewer_id": reviewer_id,
                "state": state.value,
                "supersedes_event_id": supersedes_event_id,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    @model_validator(mode="after")
    def require_decision(self) -> AdjudicationEvent:
        if self.state is ReviewState.PENDING_REVIEW:
            raise ValueError("Adjudication events must record a decision")
        expected = self.content_id(
            candidate_id=self.candidate_id,
            state=self.state,
            occurred_at=self.occurred_at,
            reviewer_id=self.reviewer_id,
            rationale=self.rationale,
            supersedes_event_id=self.supersedes_event_id,
        )
        if self.event_id != expected:
            raise ValueError("Adjudication event identifier is invalid")
        return self


class EvaluationCase(FrozenModel):
    case_id: str = Field(min_length=1)
    evaluation_class: EvaluationClass
    mapping_level: MappingLevel
    source: MappingEndpoint
    targets: tuple[MappingEndpoint, ...] = Field(min_length=1)
    relevant_target_ids: frozenset[str] = frozenset()
    languages: tuple[str, ...] = Field(min_length=1)
    tags: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ground_truth(self) -> EvaluationCase:
        target_ids = {target.concept_id for target in self.targets}
        if not self.relevant_target_ids <= target_ids:
            raise ValueError(
                "Relevant targets must occur in the candidate pool"
            )
        if (
            self.evaluation_class is EvaluationClass.POSITIVE
            and not self.relevant_target_ids
        ):
            raise ValueError("Positive cases require a relevant target")
        if (
            self.evaluation_class is EvaluationClass.NEGATIVE
            and self.relevant_target_ids
        ):
            raise ValueError("Negative cases cannot declare a relevant target")
        if self.source.level is not self.mapping_level or any(
            target.level is not self.mapping_level for target in self.targets
        ):
            raise ValueError("All endpoints must match the evaluation level")
        return self


class CandidatePrediction(FrozenModel):
    case_id: str = Field(min_length=1)
    ranked_target_ids: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    abstention_reason: AbstentionReason | None = None

    @property
    def abstained(self) -> bool:
        return self.abstention_reason is not None
