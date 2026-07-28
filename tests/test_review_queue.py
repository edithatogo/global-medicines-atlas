from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.matching_features import (
    FeatureDisposition as D,
)
from global_medicines_atlas.matching_features import (
    FeatureKind as K,
)
from global_medicines_atlas.matching_features import (
    MatchFeatures,
    feature,
)
from global_medicines_atlas.matching_models import (
    AdjudicationEvent,
    MappingLevel,
    ReviewState,
)
from global_medicines_atlas.matching_policy import (
    MatchCandidate,
    PolicyDecision,
    PolicyReason,
)
from global_medicines_atlas.review_queue import (
    ReviewQueueEntry,
    append_adjudication,
    event_id,
    load_adjudications,
    regenerate_review_queue,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def _entry(candidate_id: str) -> ReviewQueueEntry:
    missing = {kind: feature(kind, D.MISSING, 0, "Not supplied") for kind in K}
    features = MatchFeatures(
        mapping_level=MappingLevel.INGREDIENT,
        identifiers=missing[K.IDENTIFIER],
        ingredients=feature(K.INGREDIENT, D.AGREEMENT, 0.8, "Exact ingredient"),
        strength=missing[K.STRENGTH],
        unit=missing[K.UNIT],
        form=missing[K.FORM],
        route=missing[K.ROUTE],
        lexical=missing[K.LEXICAL],
        semantic=missing[K.SEMANTIC],
        rxnorm=missing[K.RXNORM],
        temporal=missing[K.TEMPORAL],
        feature_version="v1",
        evaluated_at=NOW,
    )
    candidate = MatchCandidate(
        candidate_id=candidate_id,
        source_concept_id=f"source-{candidate_id}",
        target_concept_id=f"target-{candidate_id}",
        source_jurisdiction="NZ",
        target_jurisdiction="AU",
        mapping_level=MappingLevel.INGREDIENT,
        features=features,
        index_version="v1",
        model_version="v1",
    )
    decision = PolicyDecision(
        candidate_id=candidate_id,
        confidence=0.8,
        abstained=False,
        reason_codes=(PolicyReason.REVIEW_REQUIRED,),
        policy_version="v1",
    )
    return ReviewQueueEntry(
        candidate=candidate, decision=decision, queued_at=NOW
    )


def _event(
    candidate_id: str,
    *,
    state: ReviewState = ReviewState.ACCEPTED,
    at: datetime = NOW,
    supersedes: str | None = None,
) -> AdjudicationEvent:
    rationale = "Reviewed against governed evidence"
    identifier = event_id(
        candidate_id,
        at,
        state,
        "maintainer",
        rationale,
        supersedes,
    )
    return AdjudicationEvent(
        event_id=identifier,
        candidate_id=candidate_id,
        state=state,
        occurred_at=at,
        reviewer_id="maintainer",
        rationale=rationale,
        supersedes_event_id=supersedes,
    )


def test_append_only_events_require_explicit_supersession(
    tmp_path: Path,
) -> None:
    path = tmp_path / "adjudications.jsonl"
    first = _event("a")
    append_adjudication(path, first)
    second = _event(
        "a",
        state=ReviewState.REJECTED,
        at=NOW + timedelta(seconds=1),
        supersedes=first.event_id,
    )
    append_adjudication(path, second)
    assert load_adjudications(path) == (first, second)
    with pytest.raises(ValueError, match="Duplicate"):
        append_adjudication(path, second)


def test_regeneration_preserves_decisions_and_is_deterministic() -> None:
    accepted = _event("a")
    regenerated = regenerate_review_queue(
        [_entry("c"), _entry("a"), _entry("b"), _entry("b")],
        [accepted],
    )
    assert [item.candidate.candidate_id for item in regenerated] == ["b", "c"]


def test_queue_and_event_chain_reject_inconsistent_state(
    tmp_path: Path,
) -> None:
    entry = _entry("a")
    with pytest.raises(ValidationError, match="identifiers must match"):
        ReviewQueueEntry(
            candidate=entry.candidate,
            decision=entry.decision.model_copy(update={"candidate_id": "b"}),
            queued_at=NOW,
        )
    with pytest.raises(ValidationError, match="pending review"):
        ReviewQueueEntry(
            candidate=entry.candidate,
            decision=entry.decision.model_copy(
                update={"review_state": ReviewState.ACCEPTED}
            ),
            queued_at=NOW,
        )

    path = tmp_path / "events.jsonl"
    with pytest.raises(ValueError, match="First decision"):
        append_adjudication(path, _event("a", supersedes="unknown"))
    first = _event("a")
    append_adjudication(path, first)
    with pytest.raises(ValueError, match="latest event"):
        append_adjudication(
            path,
            _event(
                "a",
                state=ReviewState.REJECTED,
                at=NOW + timedelta(seconds=1),
                supersedes="unknown",
            ),
        )


def test_event_chain_requires_strict_chronology(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    first = _event("a")
    append_adjudication(path, first)

    for occurred_at in (NOW, NOW - timedelta(seconds=1)):
        later = _event(
            "a",
            state=ReviewState.REJECTED,
            at=occurred_at,
            supersedes=first.event_id,
        )
        with pytest.raises(ValueError, match="strictly chronological"):
            append_adjudication(path, later)


def test_event_identity_covers_supersession_and_rationale() -> None:
    baseline = event_id(
        "a",
        NOW,
        ReviewState.ACCEPTED,
        "maintainer",
        "First rationale",
    )
    assert baseline != event_id(
        "a",
        NOW,
        ReviewState.ACCEPTED,
        "maintainer",
        "Changed rationale",
    )
    assert baseline != event_id(
        "a",
        NOW,
        ReviewState.ACCEPTED,
        "maintainer",
        "First rationale",
        "prior-event",
    )
