"""Fail-closed policy for reviewable medicine-matching candidates."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from .matching_features import (
    FeatureDisposition,
    FeatureKind,
    MatchFeatures,
)
from .matching_models import MappingLevel, ReviewState
from .models import FrozenModel


class PolicyReason(StrEnum):
    REVIEW_REQUIRED = "review_required"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    IDENTIFIER_CONFLICT = "identifier_conflict"
    INGREDIENT_CONFLICT = "ingredient_conflict"
    STRENGTH_CONFLICT = "strength_conflict"
    UNIT_CONFLICT = "unit_conflict"
    FORM_CONFLICT = "form_conflict"
    ROUTE_CONFLICT = "route_conflict"
    TEMPORAL_CONFLICT = "temporal_conflict"
    AMBIGUOUS_SCORE = "ambiguous_score"
    MISSING_CORE_EVIDENCE = "missing_core_evidence"
    SEMANTIC_ONLY = "semantic_only"
    RXNORM_ONLY = "rxnorm_only"
    CLINICAL_EQUIVALENCE_OUT_OF_SCOPE = "clinical_equivalence_out_of_scope"


class MatchCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    source_concept_id: str = Field(min_length=1)
    target_concept_id: str = Field(min_length=1)
    source_jurisdiction: str = Field(min_length=2, max_length=3)
    target_jurisdiction: str = Field(min_length=2, max_length=3)
    mapping_level: MappingLevel
    features: MatchFeatures
    index_version: str = Field(min_length=1)
    model_version: str = Field(min_length=1)


class PolicyDecision(FrozenModel):
    candidate_id: str
    review_state: ReviewState = ReviewState.PENDING_REVIEW
    confidence: float = Field(ge=0, le=1)
    abstained: bool
    reason_codes: tuple[PolicyReason, ...] = Field(min_length=1)
    policy_version: str = Field(min_length=1)


_CONFLICT_REASONS = {
    FeatureKind.IDENTIFIER: PolicyReason.IDENTIFIER_CONFLICT,
    FeatureKind.INGREDIENT: PolicyReason.INGREDIENT_CONFLICT,
    FeatureKind.STRENGTH: PolicyReason.STRENGTH_CONFLICT,
    FeatureKind.UNIT: PolicyReason.UNIT_CONFLICT,
    FeatureKind.FORM: PolicyReason.FORM_CONFLICT,
    FeatureKind.ROUTE: PolicyReason.ROUTE_CONFLICT,
    FeatureKind.TEMPORAL: PolicyReason.TEMPORAL_CONFLICT,
}


class ReviewOnlyPolicy:
    """Score candidates while forbidding automatic mapping acceptance."""

    def __init__(
        self,
        *,
        policy_version: str = "review-only-v1",
        review_threshold: float = 0.65,
    ) -> None:
        if not 0 < review_threshold <= 1:
            raise ValueError("review_threshold must be in (0, 1]")
        self.policy_version = policy_version
        self.review_threshold = review_threshold

    def evaluate(self, candidate: MatchCandidate) -> PolicyDecision:
        evidence = candidate.features
        reasons = [PolicyReason.REVIEW_REQUIRED]
        reasons.extend(
            _CONFLICT_REASONS[kind]
            for kind in evidence.conflicts
            if kind in _CONFLICT_REASONS
        )

        core = (
            evidence.identifiers,
            evidence.ingredients,
            evidence.strength,
            evidence.unit,
            evidence.form,
            evidence.route,
        )
        missing_core = all(
            item.disposition
            in {
                FeatureDisposition.MISSING,
                FeatureDisposition.NOT_APPLICABLE,
            }
            for item in core
        )
        if missing_core:
            reasons.append(PolicyReason.MISSING_CORE_EVIDENCE)
            if evidence.semantic.contribution > 0:
                reasons.append(PolicyReason.SEMANTIC_ONLY)
            if evidence.rxnorm.contribution > 0:
                reasons.append(PolicyReason.RXNORM_ONLY)

        confidence = evidence.raw_score
        has_blocking_conflict = bool(
            set(evidence.conflicts)
            & {
                FeatureKind.IDENTIFIER,
                FeatureKind.INGREDIENT,
                FeatureKind.STRENGTH,
                FeatureKind.UNIT,
                FeatureKind.FORM,
                FeatureKind.ROUTE,
                FeatureKind.TEMPORAL,
            }
        )
        abstained = (
            missing_core
            or has_blocking_conflict
            or confidence < self.review_threshold
        )
        if confidence < self.review_threshold:
            reasons.append(PolicyReason.INSUFFICIENT_EVIDENCE)
        elif not has_blocking_conflict:
            reasons.append(PolicyReason.AMBIGUOUS_SCORE)

        return PolicyDecision(
            candidate_id=candidate.candidate_id,
            confidence=confidence,
            abstained=abstained,
            reason_codes=tuple(dict.fromkeys(reasons)),
            policy_version=self.policy_version,
        )
