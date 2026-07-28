"""Append-only matching review queue and adjudication event log."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from pydantic import AwareDatetime, model_validator

from .matching_models import AdjudicationEvent, ReviewState
from .matching_policy import MatchCandidate, PolicyDecision
from .models import FrozenModel


class ReviewQueueEntry(FrozenModel):
    candidate: MatchCandidate
    decision: PolicyDecision
    queued_at: AwareDatetime

    @model_validator(mode="after")
    def identities_match(self) -> ReviewQueueEntry:
        if self.candidate.candidate_id != self.decision.candidate_id:
            raise ValueError("Candidate and decision identifiers must match")
        if self.decision.review_state is not ReviewState.PENDING_REVIEW:
            raise ValueError("Generated candidates must remain pending review")
        return self


def _json_line(model: FrozenModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def event_id(
    candidate_id: str,
    occurred_at: datetime,
    state: ReviewState,
    reviewer_id: str,
    rationale: str,
    supersedes_event_id: str | None = None,
) -> str:
    return AdjudicationEvent.content_id(
        candidate_id=candidate_id,
        state=state,
        occurred_at=occurred_at,
        reviewer_id=reviewer_id,
        rationale=rationale,
        supersedes_event_id=supersedes_event_id,
    )


def append_adjudication(path: Path, event: AdjudicationEvent) -> None:
    """Append a unique event without rewriting prior human decisions."""
    existing = load_adjudications(path)
    if any(item.event_id == event.event_id for item in existing):
        raise ValueError(f"Duplicate adjudication event: {event.event_id}")
    prior = [
        item for item in existing if item.candidate_id == event.candidate_id
    ]
    if prior and event.supersedes_event_id != prior[-1].event_id:
        raise ValueError("A later decision must supersede the latest event")
    if prior and event.occurred_at <= prior[-1].occurred_at:
        raise ValueError("Adjudication events must be strictly chronological")
    if not prior and event.supersedes_event_id is not None:
        raise ValueError("First decision cannot supersede an event")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(_json_line(event) + "\n")


def load_adjudications(path: Path) -> tuple[AdjudicationEvent, ...]:
    if not path.exists():
        return ()
    return tuple(
        AdjudicationEvent.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def regenerate_review_queue(
    entries: Iterable[ReviewQueueEntry],
    adjudications: Iterable[AdjudicationEvent],
) -> tuple[ReviewQueueEntry, ...]:
    """Regenerate pending work while preserving all adjudicated candidates."""
    decided = {event.candidate_id for event in adjudications}
    by_id: dict[str, ReviewQueueEntry] = {}
    for entry in entries:
        if entry.candidate.candidate_id not in decided:
            by_id[entry.candidate.candidate_id] = entry
    return tuple(by_id[key] for key in sorted(by_id))
