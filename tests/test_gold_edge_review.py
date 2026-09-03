"""Generic Gold-edge review cases remain pending and evidence-bound."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from global_medicines_atlas.gold_edge_review import (
    GoldEdgeReviewCase,
    build_gold_edge_review_queue,
    regenerate_gold_edge_review_queue,
)
from global_medicines_atlas.matching_models import (
    AdjudicationEvent,
    ReviewState,
)
from global_medicines_atlas.models import FrozenModel

QUEUED_AT = datetime(2026, 9, 3, tzinfo=UTC)


class ExampleGoldEdge(FrozenModel):
    edge_id: str
    kind: str
    source_node_id: str
    target_node_id: str
    semantic_dimension: str
    mapping_method: str
    inferred: bool


def pbs_edge(edge_id: str = "pbs-gold-edge:" + "1" * 64) -> dict[str, object]:
    return {
        "edge_id": edge_id,
        "kind": "source_contains_entity",
        "source_node_id": "pbs-gold-node:" + "2" * 64,
        "target_node_id": "pbs-gold-node:" + "3" * 64,
        "semantic_dimension": "source_structure",
        "mapping_method": "source-explicit",
        "review_state": "not_reviewed",
        "inferred": False,
        "evidence": {"receipt_sha256": "4" * 64},
    }


def mbs_legacy_edge() -> dict[str, object]:
    return {
        "edge_id": "mbs-gold-edge:" + "5" * 64,
        "kind": "source_record_has_benefit",
        "source_node_id": "mbs-gold-node:" + "6" * 64,
        "target_node_id": "mbs-gold-node:" + "7" * 64,
        "assertion_basis": "same_source_record",
        "inferred": False,
        "evidence": {"receipt_sha256": "8" * 64},
    }


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
    model_edge = ExampleGoldEdge(
        edge_id="pbs-gold-edge:" + "a" * 64,
        kind="source_contains_entity",
        source_node_id="pbs-gold-node:" + "b" * 64,
        target_node_id="pbs-gold-node:" + "c" * 64,
        semantic_dimension="source_structure",
        mapping_method="source-explicit",
        inferred=False,
    )
    assert (
        build_gold_edge_review_queue((model_edge,), queued_at=QUEUED_AT)[
            0
        ].edge_id
        == model_edge.edge_id
    )


def test_case_digest_binds_complete_edge_and_case_fields():
    first = build_gold_edge_review_queue((pbs_edge(),), queued_at=QUEUED_AT)[0]
    changed_edge = pbs_edge()
    changed_edge["evidence"] = {"receipt_sha256": "9" * 64}
    second = build_gold_edge_review_queue((changed_edge,), queued_at=QUEUED_AT)[
        0
    ]
    assert first.edge_sha256 != second.edge_sha256
    assert first.review_case_id != second.review_case_id
    forged = first.model_dump()
    forged["edge_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="case identity"):
        GoldEdgeReviewCase.model_validate(forged)


def test_queue_rejects_duplicate_or_unsupported_edges():
    with pytest.raises(ValueError, match="Duplicate Gold edge"):
        build_gold_edge_review_queue(
            (pbs_edge(), pbs_edge()), queued_at=QUEUED_AT
        )
    unsupported = pbs_edge()
    unsupported["kind"] = "asserted_equivalence"
    del unsupported["semantic_dimension"]
    del unsupported["mapping_method"]
    with pytest.raises(ValueError, match="explicit review controls"):
        build_gold_edge_review_queue((unsupported,), queued_at=QUEUED_AT)
    inferred = pbs_edge()
    inferred["inferred"] = True
    with pytest.raises(ValueError, match="non-inferred"):
        build_gold_edge_review_queue((inferred,), queued_at=QUEUED_AT)
    missing_id = pbs_edge()
    del missing_id["source_node_id"]
    with pytest.raises(ValueError, match="source_node_id"):
        build_gold_edge_review_queue((missing_id,), queued_at=QUEUED_AT)


def test_existing_adjudication_only_filters_and_never_creates_decisions():
    queue = build_gold_edge_review_queue(
        (pbs_edge(), mbs_legacy_edge()), queued_at=QUEUED_AT
    )
    decided = queue[0]
    event_id = AdjudicationEvent.content_id(
        candidate_id=decided.review_case_id,
        state=ReviewState.NEEDS_INFORMATION,
        occurred_at=QUEUED_AT,
        reviewer_id="maintainer-supplied",
        rationale="Existing event supplied by caller",
        supersedes_event_id=None,
    )
    event = AdjudicationEvent(
        event_id=event_id,
        candidate_id=decided.review_case_id,
        state=ReviewState.NEEDS_INFORMATION,
        occurred_at=QUEUED_AT,
        reviewer_id="maintainer-supplied",
        rationale="Existing event supplied by caller",
    )
    remaining = regenerate_gold_edge_review_queue(queue, (event,))
    assert remaining == (queue[1],)
    assert remaining[0].review_state is ReviewState.PENDING_REVIEW
