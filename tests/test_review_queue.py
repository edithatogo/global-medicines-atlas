import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas import review_queue as review_queue_module
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
    MAX_ADJUDICATION_EVENTS,
    MAX_ADJUDICATION_FILE_BYTES,
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
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == json.dumps(
        first.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert path.read_bytes().endswith(b"\n")
    with pytest.raises(ValueError, match="Duplicate"):
        append_adjudication(path, second)


def test_regeneration_preserves_decisions_and_is_deterministic() -> None:
    accepted = _event("a")
    regenerated = regenerate_review_queue(
        [_entry("c"), _entry("a"), _entry("b"), _entry("b")],
        [accepted],
    )
    assert [item.candidate.candidate_id for item in regenerated] == ["b", "c"]
    assert regenerated[0] == _entry("b")


def test_regeneration_uses_last_duplicate_entry_and_sorts_identifiers() -> None:
    first_b = _entry("b")
    replacement_b = first_b.model_copy(
        update={"queued_at": NOW + timedelta(seconds=1)}
    )

    regenerated = regenerate_review_queue(
        [_entry("c"), first_b, _entry("a"), replacement_b],
        [],
    )

    assert [item.candidate.candidate_id for item in regenerated] == [
        "a",
        "b",
        "c",
    ]
    assert regenerated[1] == replacement_b


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


def test_loader_rejects_reordered_append_only_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    first = _event("a")
    second = _event(
        "a",
        state=ReviewState.REJECTED,
        at=NOW + timedelta(seconds=1),
        supersedes=first.event_id,
    )
    append_adjudication(path, first)
    append_adjudication(path, second)
    path.write_text("\n".join(reversed(path.read_text().splitlines())) + "\n")

    with pytest.raises(
        ValueError,
        match=r"^First decision cannot supersede an event$",
    ):
        load_adjudications(path)


def test_loader_bounds_adjudication_file_bytes(tmp_path: Path) -> None:
    path = tmp_path / "oversized.jsonl"
    path.write_bytes(b" " * (MAX_ADJUDICATION_FILE_BYTES + 1))

    with pytest.raises(
        ValueError, match=r"^Adjudication file exceeds byte bound$"
    ):
        load_adjudications(path)


def test_loader_accepts_files_at_byte_and_event_bounds(tmp_path: Path) -> None:
    byte_bounded = tmp_path / "byte-bounded.jsonl"
    event = _event("a")
    line = json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    byte_bounded.write_bytes(
        line + b" " * (MAX_ADJUDICATION_FILE_BYTES - len(line) - 1) + b"\n"
    )
    assert load_adjudications(byte_bounded) == (event,)

    event_bounded = tmp_path / "event-bounded.jsonl"
    event_bounded.write_text("\n" * MAX_ADJUDICATION_EVENTS)
    assert load_adjudications(event_bounded) == ()


def test_loader_rejects_event_count_over_bound(tmp_path: Path) -> None:
    path = tmp_path / "too-many-lines.jsonl"
    path.write_text("\n" * (MAX_ADJUDICATION_EVENTS + 1))

    with pytest.raises(
        ValueError,
        match=r"^Adjudication file exceeds event bound$",
    ):
        load_adjudications(path)


def test_loader_rejects_duplicate_event_ids(tmp_path: Path) -> None:
    path = tmp_path / "duplicate-events.jsonl"
    event = _event("a")
    line = json.dumps(event.model_dump(mode="json"), sort_keys=True)
    path.write_text(f"{line}\n{line}\n")

    with pytest.raises(
        ValueError,
        match=r"^Duplicate adjudication event$",
    ):
        load_adjudications(path)


def test_loader_rejects_non_chronological_event_chain(tmp_path: Path) -> None:
    path = tmp_path / "same-time-events.jsonl"
    first = _event("a")
    second = _event(
        "a",
        state=ReviewState.REJECTED,
        at=NOW,
        supersedes=first.event_id,
    )
    lines = [
        json.dumps(event.model_dump(mode="json"), sort_keys=True)
        for event in (first, second)
    ]
    path.write_text("\n".join(lines) + "\n")

    with pytest.raises(
        ValueError,
        match=r"^Adjudication events must be strictly chronological$",
    ):
        load_adjudications(path)


def test_loader_opens_nonblocking_and_reads_with_a_byte_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "events.jsonl"
    append_adjudication(path, _event("a"))
    real_open = os.open
    real_fdopen = os.fdopen

    def checked_open(file_path, flags, *args, **kwargs):
        assert flags & os.O_NONBLOCK
        return real_open(file_path, flags, *args, **kwargs)

    class BoundedReader:
        def __init__(self, descriptor, mode, *, closefd):
            self.stream = real_fdopen(descriptor, mode, closefd=closefd)

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            self.stream.close()

        def read(self, size):
            assert size == MAX_ADJUDICATION_FILE_BYTES + 1
            return self.stream.read(size)

    monkeypatch.setattr(review_queue_module.os, "open", checked_open)
    monkeypatch.setattr(review_queue_module.os, "fdopen", BoundedReader)

    assert load_adjudications(path) == (_event("a"),)


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


def test_event_identity_is_stable_and_covers_every_immutable_field() -> None:
    baseline = event_id(
        "a",
        NOW,
        ReviewState.ACCEPTED,
        "maintainer",
        "Rātionale",
    )
    same = event_id(
        "a",
        NOW,
        ReviewState.ACCEPTED,
        "maintainer",
        "Rātionale",
    )

    assert baseline == same
    assert len(baseline) == 64
    assert baseline.isascii()
    assert baseline != event_id(
        "b", NOW, ReviewState.ACCEPTED, "maintainer", "Rātionale"
    )
    assert baseline != event_id(
        "a",
        NOW + timedelta(microseconds=1),
        ReviewState.ACCEPTED,
        "maintainer",
        "Rātionale",
    )
    assert baseline != event_id(
        "a", NOW, ReviewState.REJECTED, "maintainer", "Rātionale"
    )
    assert baseline != event_id(
        "a", NOW, ReviewState.ACCEPTED, "reviewer-2", "Rātionale"
    )


def test_loading_missing_and_blank_lines_is_exact(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    assert load_adjudications(path) == ()

    event = _event("a")
    path.write_text(
        f"\n{event.model_dump_json()}\n\n",
        encoding="utf-8",
        newline="\n",
    )

    assert load_adjudications(path) == (event,)
