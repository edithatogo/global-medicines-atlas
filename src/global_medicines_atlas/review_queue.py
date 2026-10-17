"""Append-only matching review queue and adjudication event log."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from pydantic import AwareDatetime, model_validator

from .matching_models import AdjudicationEvent, ReviewState
from .matching_policy import MatchCandidate, PolicyDecision
from .models import FrozenModel

MAX_ADJUDICATION_FILE_BYTES = 16 * 1024 * 1024
MAX_ADJUDICATION_EVENTS = 10_000
LF_BYTE = ord("\n")
CR_BYTE = ord("\r")


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
    payload = _read_adjudication_payload(path)
    existing = _parse_adjudications(payload)
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

    line_count = len(_physical_jsonl_lines(payload))
    if line_count + 1 > MAX_ADJUDICATION_EVENTS:
        raise ValueError("Adjudication file exceeds event bound")
    line = _json_line(event).encode("utf-8")
    separator = (
        b"" if not payload or payload.endswith((b"\n", b"\r")) else b"\n"
    )
    appended = separator + line + b"\n"
    if len(payload) + len(appended) > MAX_ADJUDICATION_FILE_BYTES:
        raise ValueError("Adjudication file exceeds byte bound")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(appended)


def load_adjudications(path: Path) -> tuple[AdjudicationEvent, ...]:
    return _parse_adjudications(_read_adjudication_payload(path))


def _read_adjudication_payload(path: Path) -> bytes:
    if not path.exists():
        return b""
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        file_status = os.fstat(descriptor)
        if not stat.S_ISREG(file_status.st_mode):
            raise ValueError("Adjudication file must be regular")
        if file_status.st_size > MAX_ADJUDICATION_FILE_BYTES:
            raise ValueError("Adjudication file exceeds byte bound")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            payload = stream.read(MAX_ADJUDICATION_FILE_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(payload) > MAX_ADJUDICATION_FILE_BYTES:
        raise ValueError("Adjudication file exceeds byte bound")

    return payload


def _parse_adjudications(payload: bytes) -> tuple[AdjudicationEvent, ...]:
    lines = _physical_jsonl_lines(payload)
    if len(lines) > MAX_ADJUDICATION_EVENTS:
        raise ValueError("Adjudication file exceeds event bound")
    events = tuple(
        AdjudicationEvent.model_validate_json(line) for line in lines if line
    )
    _validate_adjudication_sequence(events)
    return events


def _physical_jsonl_lines(payload: bytes) -> tuple[bytes, ...]:
    """Split physical CR, LF, or CRLF delimiters without Unicode splitting."""
    if not payload:
        return ()
    lines: list[bytes] = []
    start = 0
    index = 0
    while index < len(payload):
        if payload[index] == LF_BYTE:
            end = (
                index - 1
                if index > start and payload[index - 1] == CR_BYTE
                else index
            )
            lines.append(payload[start:end])
            index += 1
            start = index
        elif payload[index] == CR_BYTE:
            lines.append(payload[start:index])
            index += 1
            if index < len(payload) and payload[index] == LF_BYTE:
                index += 1
            start = index
        else:
            index += 1
    if start < len(payload):
        lines.append(payload[start:])
    return tuple(lines)


def _validate_adjudication_sequence(
    events: tuple[AdjudicationEvent, ...],
) -> None:
    latest_by_candidate: dict[str, AdjudicationEvent] = {}
    seen_event_ids: set[str] = set()
    for event in events:
        if event.event_id in seen_event_ids:
            raise ValueError("Duplicate adjudication event")
        seen_event_ids.add(event.event_id)
        prior = latest_by_candidate.get(event.candidate_id)
        if prior is None:
            if event.supersedes_event_id is not None:
                raise ValueError("First decision cannot supersede an event")
        else:
            if event.supersedes_event_id != prior.event_id:
                raise ValueError(
                    "A later decision must supersede the latest event"
                )
            if event.occurred_at <= prior.occurred_at:
                raise ValueError(
                    "Adjudication events must be strictly chronological"
                )
        latest_by_candidate[event.candidate_id] = event


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
