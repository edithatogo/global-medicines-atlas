"""Run the candidate generator against its explicit labelled test fixture."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import Field

from .matching import MatchingRecord, generate_candidates
from .matching_evaluation import (
    GroupedMatchingMetrics,
    evaluate_grouped_predictions,
)
from .matching_models import (
    AbstentionReason,
    CandidatePrediction,
    EvaluationCase,
    EvaluationClass,
    MappingEndpoint,
)
from .models import FrozenModel


class MatchingCaseOutcome(FrozenModel):
    """The candidate generator's observable behavior for one labelled case."""

    case_id: str
    evaluation_class: EvaluationClass
    ranked_target_ids: tuple[str, ...]
    methods_by_target: dict[str, tuple[str, ...]]
    confidence: float = Field(ge=0, le=1)
    abstained: bool
    abstention_reason: AbstentionReason | None


class MatchingBehaviorAssessment(FrozenModel):
    """Deterministic, non-promoting assessment of a labelled fixture."""

    schema_version: Literal[1] = 1
    qualification_state: Literal["synthetic_fixture_assessment_only"] = (
        "synthetic_fixture_assessment_only"
    )
    production_promotion_eligible: Literal[False] = False
    lexical_threshold: float = Field(ge=0, le=1)
    candidate_limit: int = Field(ge=1)
    metrics: GroupedMatchingMetrics
    outcomes: tuple[MatchingCaseOutcome, ...]
    limitations: tuple[str, ...] = Field(min_length=1)


def _matching_record(endpoint: MappingEndpoint) -> MatchingRecord:
    """Project only name and identifiers represented by the fixture contract."""
    return MatchingRecord(
        record_id=endpoint.concept_id,
        jurisdiction=endpoint.jurisdiction,
        name=endpoint.preferred_name,
        identifiers=endpoint.identifiers,
    )


def assess_matching_behavior(
    cases: Iterable[EvaluationCase],
    *,
    lexical_threshold: float = 0.65,
    candidate_limit: int = 20,
    k: int = 5,
) -> MatchingBehaviorAssessment:
    """Score real generator output against held fixture labels.

    The fixture is synthetic. These metrics diagnose implementation behavior;
    they do not calibrate a threshold or qualify production relationships.
    """
    case_list = tuple(cases)
    predictions: list[CandidatePrediction] = []
    outcomes: list[MatchingCaseOutcome] = []
    for case in case_list:
        generated = generate_candidates(
            _matching_record(case.source),
            tuple(_matching_record(target) for target in case.targets),
            lexical_threshold=lexical_threshold,
            limit=candidate_limit,
        )
        ranked = tuple(
            candidate.target_record_id for candidate in generated.candidates
        )
        confidence = (
            generated.candidates[0].score if generated.candidates else 0.0
        )
        predictions.append(
            CandidatePrediction(
                case_id=case.case_id,
                ranked_target_ids=ranked,
                confidence=confidence,
                abstention_reason=(
                    AbstentionReason.INSUFFICIENT_EVIDENCE
                    if generated.abstained
                    else None
                ),
            )
        )
        outcomes.append(
            MatchingCaseOutcome(
                case_id=case.case_id,
                evaluation_class=case.evaluation_class,
                ranked_target_ids=ranked,
                methods_by_target={
                    candidate.target_record_id: tuple(
                        method.value for method in candidate.methods
                    )
                    for candidate in generated.candidates
                },
                confidence=confidence,
                abstained=generated.abstained,
                abstention_reason=(
                    AbstentionReason.INSUFFICIENT_EVIDENCE
                    if generated.abstained
                    else None
                ),
            )
        )

    return MatchingBehaviorAssessment(
        lexical_threshold=lexical_threshold,
        candidate_limit=candidate_limit,
        metrics=evaluate_grouped_predictions(
            case_list,
            predictions,
            k=k,
        ),
        outcomes=tuple(outcomes),
        limitations=(
            "The six labelled cases are self-authored synthetic fixtures.",
            "Fixture endpoints expose names and identifiers only; the assessment does not establish source-era attribute coverage.",
            "The observed confidence scores are not calibrated or eligible for production promotion.",
            "No candidate is a reviewed medicine identity or therapeutic-equivalence assertion.",
        ),
    )
