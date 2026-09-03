"""Pending-only review adapter for evidence-bearing Gold graph edges."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Literal, cast

from pydantic import AwareDatetime, Field, model_validator

from .matching_models import AdjudicationEvent, ReviewState
from .mbs_gold_graph import MbsGoldEdge
from .models import FrozenModel
from .pbs_gold_graph import PbsGoldEdge


class GoldEdgeReviewCase(FrozenModel):
    """An immutable queue case; it is neither a decision nor a promotion."""

    review_case_id: str = Field(pattern=r"^gold-edge-review:[0-9a-f]{64}$")
    edge_id: str = Field(min_length=1)
    edge_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    edge_kind: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    semantic_dimension: str = Field(min_length=1)
    mapping_method: str = Field(min_length=1)
    review_state: Literal[ReviewState.PENDING_REVIEW] = (
        ReviewState.PENDING_REVIEW
    )
    queued_at: AwareDatetime
    promotion_performed: Literal[False] = False

    @model_validator(mode="after")
    def identity_is_bound(self) -> GoldEdgeReviewCase:
        if self.review_case_id != _case_id(
            self.edge_id,
            self.edge_sha256,
            self.edge_kind,
            self.source_node_id,
            self.target_node_id,
            self.semantic_dimension,
            self.mapping_method,
            self.queued_at,
        ):
            raise ValueError("Gold edge review case identity differs")
        return self


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: (
            item.isoformat() if isinstance(item, datetime) else str(item)
        ),
    ).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _case_id(
    edge_id: str,
    edge_sha256: str,
    edge_kind: str,
    source_node_id: str,
    target_node_id: str,
    semantic_dimension: str,
    mapping_method: str,
    queued_at: datetime,
) -> str:
    return "gold-edge-review:" + _digest({
        "edge_id": edge_id,
        "edge_sha256": edge_sha256,
        "edge_kind": edge_kind,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "semantic_dimension": semantic_dimension,
        "mapping_method": mapping_method,
        "queued_at": queued_at,
        "review_state": ReviewState.PENDING_REVIEW,
        "promotion_performed": False,
    })


def _edge_payload(
    edge: Mapping[str, object] | FrozenModel,
) -> dict[str, object]:
    raw = (
        edge.model_dump(mode="python")
        if isinstance(edge, FrozenModel)
        else dict(edge)
    )
    kind = raw.get("kind")
    if kind == "source_contains_entity":
        validated: FrozenModel = PbsGoldEdge.model_validate(raw)
    elif kind == "source_record_has_benefit":
        validated = MbsGoldEdge.model_validate(raw)
    else:
        raise ValueError(
            "Gold edge kind is not supported by the review adapter"
        )
    return cast("dict[str, object]", validated.model_dump(mode="json"))


def build_gold_edge_review_queue(
    edges: Iterable[Mapping[str, object] | FrozenModel],
    *,
    queued_at: datetime,
) -> tuple[GoldEdgeReviewCase, ...]:
    """Create deterministic pending cases without making a review decision."""
    cases: dict[str, GoldEdgeReviewCase] = {}
    edge_ids: set[str] = set()
    for edge in edges:
        payload = _edge_payload(edge)
        edge_id = cast("str", payload["edge_id"])
        if edge_id in edge_ids:
            raise ValueError(f"Duplicate Gold edge: {edge_id}")
        edge_ids.add(edge_id)
        edge_kind = cast("str", payload["kind"])
        source = cast("str", payload["source_node_id"])
        target = cast("str", payload["target_node_id"])
        dimension = cast("str", payload["semantic_dimension"])
        method = cast("str", payload["mapping_method"])
        edge_sha256 = _digest(payload)
        case = GoldEdgeReviewCase(
            review_case_id=_case_id(
                edge_id,
                edge_sha256,
                edge_kind,
                source,
                target,
                dimension,
                method,
                queued_at,
            ),
            edge_id=edge_id,
            edge_sha256=edge_sha256,
            edge_kind=edge_kind,
            source_node_id=source,
            target_node_id=target,
            semantic_dimension=dimension,
            mapping_method=method,
            queued_at=queued_at,
        )
        cases[case.review_case_id] = case
    return tuple(cases[key] for key in sorted(cases))


def regenerate_gold_edge_review_queue(
    cases: Iterable[GoldEdgeReviewCase],
    adjudications: Iterable[AdjudicationEvent],
) -> tuple[GoldEdgeReviewCase, ...]:
    """Filter caller-supplied decided cases without manufacturing decisions."""
    decided = {event.candidate_id for event in adjudications}
    pending = {
        case.review_case_id: case
        for case in cases
        if case.review_case_id not in decided
    }
    return tuple(pending[key] for key in sorted(pending))
