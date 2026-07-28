from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from global_medicines_atlas.matching_models import (
    AbstentionReason,
    AdjudicationEvent,
    CandidateMethod,
    FeatureContribution,
    MappingCandidate,
    MappingEndpoint,
    MappingLevel,
    ReviewState,
)


def endpoint(concept_id: str, jurisdiction: str) -> MappingEndpoint:
    return MappingEndpoint(
        concept_id=concept_id,
        jurisdiction=jurisdiction,
        level=MappingLevel.INGREDIENT,
        preferred_name="Synthetic ingredient",
        language="en",
        provenance_ids=(f"fixture:{concept_id}",),
    )


def candidate(**updates: object) -> MappingCandidate:
    values: dict[str, object] = {
        "candidate_id": "candidate-1",
        "source": endpoint("nz:1", "NZL"),
        "target": endpoint("au:1", "AUS"),
        "method": CandidateMethod.IDENTIFIER,
        "features": (
            FeatureContribution(
                feature="shared_identifier",
                value=1.0,
                contribution=0.8,
                explanation="Synthetic identifier agreement",
            ),
        ),
        "confidence": 0.8,
        "calibration_version": "fixture-v1",
        "index_version": "fixture-v1",
        "model_version": "python-reference-v1",
        "generated_at": datetime(2026, 7, 29, tzinfo=UTC),
    }
    values.update(updates)
    return MappingCandidate.model_validate(values)


@pytest.mark.unit
def test_candidates_are_review_first_and_explainable() -> None:
    result = candidate()

    assert result.review_state is ReviewState.PENDING_REVIEW
    assert result.features[0].feature == "shared_identifier"
    assert not result.is_therapeutic_equivalence_claim


@pytest.mark.edge
@pytest.mark.parametrize(
    "updates",
    [
        {"is_therapeutic_equivalence_claim": True},
        {"target": endpoint("nz:2", "NZL")},
        {
            "features": (
                FeatureContribution(
                    feature="duplicate",
                    value=1.0,
                    contribution=0.5,
                    explanation="First",
                ),
                FeatureContribution(
                    feature="duplicate",
                    value=0.5,
                    contribution=0.2,
                    explanation="Second",
                ),
            )
        },
        {
            "abstention_reason": AbstentionReason.AMBIGUOUS_CANDIDATES,
            "review_state": ReviewState.ACCEPTED,
        },
    ],
)
def test_candidates_reject_unsafe_states(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        candidate(**updates)


@pytest.mark.unit
def test_adjudication_is_append_only_decision_evidence() -> None:
    occurred_at = datetime(2026, 7, 29, tzinfo=UTC)
    identifier = AdjudicationEvent.content_id(
        candidate_id="candidate-1",
        state=ReviewState.SUPERSEDED,
        occurred_at=occurred_at,
        reviewer_id="maintainer",
        rationale="Superseded after source correction.",
        supersedes_event_id="event-1",
    )
    event = AdjudicationEvent(
        event_id=identifier,
        candidate_id="candidate-1",
        state=ReviewState.SUPERSEDED,
        occurred_at=occurred_at,
        reviewer_id="maintainer",
        rationale="Superseded after source correction.",
        supersedes_event_id="event-1",
    )

    assert event.supersedes_event_id == "event-1"


@pytest.mark.edge
def test_adjudication_cannot_record_pending_as_a_decision() -> None:
    with pytest.raises(ValidationError):
        AdjudicationEvent(
            event_id="event-1",
            candidate_id="candidate-1",
            state=ReviewState.PENDING_REVIEW,
            occurred_at=datetime(2026, 7, 29, tzinfo=UTC),
            reviewer_id="maintainer",
            rationale="Not yet reviewed.",
        )


@pytest.mark.edge
def test_adjudication_rejects_an_identifier_for_different_content() -> None:
    occurred_at = datetime(2026, 7, 29, tzinfo=UTC)
    identifier = AdjudicationEvent.content_id(
        candidate_id="candidate-1",
        state=ReviewState.ACCEPTED,
        occurred_at=occurred_at,
        reviewer_id="maintainer",
        rationale="Original rationale",
        supersedes_event_id=None,
    )
    with pytest.raises(ValidationError, match="identifier is invalid"):
        AdjudicationEvent(
            event_id=identifier,
            candidate_id="candidate-1",
            state=ReviewState.ACCEPTED,
            occurred_at=occurred_at,
            reviewer_id="maintainer",
            rationale="Tampered rationale",
        )
