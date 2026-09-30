"""Generic Gold-edge review cases remain pending and evidence-bound."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from test_mbs_gold_graph import graph as mbs_graph
from test_pbs_gold_graph import graph as pbs_graph

from global_medicines_atlas.gold_edge_review import (
    GoldEdgeReviewCase,
    build_gold_edge_review_queue,
    regenerate_gold_edge_review_queue,
)
from global_medicines_atlas.matching_models import (
    AdjudicationEvent,
    ReviewState,
)

QUEUED_AT = datetime(2026, 9, 3, tzinfo=UTC)


def pbs_edge() -> dict[str, object]:
    return pbs_graph().edges[0].model_dump(mode="python")


def mbs_legacy_edge() -> dict[str, object]:
    payload = mbs_graph(1).edges[0].model_dump(mode="python")
    for name in ("semantic_dimension", "mapping_method"):
        payload.pop(name)
    return payload


def adjudication(
    candidate_id: str,
    state: ReviewState,
    rationale: str,
    supersedes_event_id: str | None = None,
) -> AdjudicationEvent:
    event_id = AdjudicationEvent.content_id(
        candidate_id=candidate_id,
        state=state,
        occurred_at=QUEUED_AT,
        reviewer_id="maintainer-supplied",
        rationale=rationale,
        supersedes_event_id=supersedes_event_id,
    )
    return AdjudicationEvent(
        event_id=event_id,
        candidate_id=candidate_id,
        state=state,
        occurred_at=QUEUED_AT,
        reviewer_id="maintainer-supplied",
        rationale=rationale,
        supersedes_event_id=supersedes_event_id,
    )


def test_queue_adapts_current_pbs_and_legacy_mbs_without_promotion():
    queue = build_gold_edge_review_queue(
        (mbs_legacy_edge(), pbs_edge()), queued_at=QUEUED_AT
    )
    assert tuple(case.review_case_id for case in queue) == tuple(
        sorted(case.review_case_id for case in queue)
    )
    by_kind = {case.edge_kind: case for case in queue}
    assert (
        by_kind["source_contains_entity"].semantic_dimension
        == "source_structure"
    )
    assert (
        by_kind["source_record_has_benefit"].semantic_dimension
        == "service_benefit"
    )
    assert all(case.mapping_method == "source-explicit" for case in queue)
    assert all(
        case.review_state is ReviewState.PENDING_REVIEW for case in queue
    )
    assert all(case.promotion_performed is False for case in queue)
    assert "reviewer_id" not in GoldEdgeReviewCase.model_fields
    assert "decision" not in GoldEdgeReviewCase.model_fields
    model_edge = pbs_graph().edges[0]
    model_case = build_gold_edge_review_queue(
        (model_edge,), queued_at=QUEUED_AT
    )[0]
    mapping_case = build_gold_edge_review_queue(
        (model_edge.model_dump(mode="python"),), queued_at=QUEUED_AT
    )[0]
    assert model_case == mapping_case


def test_case_digest_binds_complete_edge_and_case_fields():
    first = build_gold_edge_review_queue((pbs_edge(),), queued_at=QUEUED_AT)[0]
    second = build_gold_edge_review_queue(
        (pbs_graph().edges[1],), queued_at=QUEUED_AT
    )[0]
    assert first.edge_sha256 != second.edge_sha256
    assert first.review_case_id != second.review_case_id
    forged = first.model_dump()
    forged["edge_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="case identity"):
        GoldEdgeReviewCase.model_validate(forged)


@pytest.mark.parametrize(
    "state", [ReviewState.REJECTED, ReviewState.SUPERSEDED]
)
def test_other_terminal_adjudications_remove_only_the_decided_case(
    state: ReviewState,
):
    queue = build_gold_edge_review_queue(
        (pbs_edge(), mbs_legacy_edge()), queued_at=QUEUED_AT
    )
    decided = queue[0]
    rationale = f"Existing {state.value} event supplied by caller"
    event_id = AdjudicationEvent.content_id(
        candidate_id=decided.review_case_id,
        state=state,
        occurred_at=QUEUED_AT,
        reviewer_id="maintainer-supplied",
        rationale=rationale,
        supersedes_event_id=None,
    )
    event = AdjudicationEvent(
        event_id=event_id,
        candidate_id=decided.review_case_id,
        state=state,
        occurred_at=QUEUED_AT,
        reviewer_id="maintainer-supplied",
        rationale=rationale,
    )
    assert regenerate_gold_edge_review_queue(queue, (event,)) == (queue[1],)


def test_queue_rejects_duplicate_or_unsupported_edges():
    with pytest.raises(ValueError, match="Duplicate Gold edge"):
        build_gold_edge_review_queue(
            (pbs_edge(), pbs_edge()), queued_at=QUEUED_AT
        )
    unsupported = pbs_edge()
    unsupported["kind"] = "asserted_equivalence"
    with pytest.raises(ValueError, match="not supported"):
        build_gold_edge_review_queue((unsupported,), queued_at=QUEUED_AT)
    inferred = pbs_edge()
    inferred["inferred"] = True
    with pytest.raises(ValidationError):
        build_gold_edge_review_queue((inferred,), queued_at=QUEUED_AT)
    missing_id = pbs_edge()
    del missing_id["source_node_id"]
    with pytest.raises(ValidationError, match="source_node_id"):
        build_gold_edge_review_queue((missing_id,), queued_at=QUEUED_AT)


def test_needs_information_and_complete_supersession_chain_remain_pending():
    queue = build_gold_edge_review_queue(
        (pbs_edge(), mbs_legacy_edge()), queued_at=QUEUED_AT
    )
    needs_information = adjudication(
        queue[0].review_case_id,
        ReviewState.NEEDS_INFORMATION,
        "Existing event supplied by caller",
    )
    unresolved = regenerate_gold_edge_review_queue(queue, (needs_information,))
    assert unresolved == queue
    assert all(
        case.review_state is ReviewState.PENDING_REVIEW for case in unresolved
    )
    accepted = adjudication(
        queue[0].review_case_id,
        ReviewState.ACCEPTED,
        "Existing superseding decision supplied by caller",
        needs_information.event_id,
    )
    remaining = regenerate_gold_edge_review_queue(
        queue, (needs_information, accepted)
    )
    assert remaining == (queue[1],)
    assert remaining[0].review_state is ReviewState.PENDING_REVIEW


def test_conflicting_adjudication_roots_remain_pending():
    queue = build_gold_edge_review_queue((pbs_edge(),), queued_at=QUEUED_AT)
    first = adjudication(
        queue[0].review_case_id, ReviewState.NEEDS_INFORMATION, "First root"
    )
    second = adjudication(
        queue[0].review_case_id, ReviewState.REJECTED, "Second root"
    )
    assert regenerate_gold_edge_review_queue(queue, (first, second)) == queue


def test_dangling_adjudication_predecessor_remains_pending():
    queue = build_gold_edge_review_queue((pbs_edge(),), queued_at=QUEUED_AT)
    root = adjudication(
        queue[0].review_case_id, ReviewState.NEEDS_INFORMATION, "Root"
    )
    dangling = adjudication(
        queue[0].review_case_id,
        ReviewState.ACCEPTED,
        "Decision refers to an unavailable predecessor",
        "missing-event",
    )
    assert regenerate_gold_edge_review_queue(queue, (root, dangling)) == queue


def test_branched_adjudication_history_remains_pending():
    queue = build_gold_edge_review_queue((pbs_edge(),), queued_at=QUEUED_AT)
    root = adjudication(
        queue[0].review_case_id, ReviewState.NEEDS_INFORMATION, "Root"
    )
    first_child = adjudication(
        queue[0].review_case_id,
        ReviewState.ACCEPTED,
        "First child",
        root.event_id,
    )
    second_child = adjudication(
        queue[0].review_case_id,
        ReviewState.REJECTED,
        "Second child",
        root.event_id,
    )
    assert (
        regenerate_gold_edge_review_queue(
            queue, (root, first_child, second_child)
        )
        == queue
    )
