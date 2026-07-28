"""Honest comparison of independently projected source representations."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from .ingestors import ProjectionOutcome, canonical_record_payload
from .models import FrozenModel


class ParityStatus(StrEnum):
    EQUIVALENT = "equivalent"
    DIFFERENT = "different"
    NOT_COMPARABLE = "not_comparable"


class ParityResult(FrozenModel):
    """Deterministic result that preserves comparability limitations."""

    status: ParityStatus
    left_projection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    right_projection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    left_count: int = Field(ge=0)
    right_count: int = Field(ge=0)
    only_left: tuple[str, ...] = ()
    only_right: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    @property
    def is_equivalent(self) -> bool:
        return self.status is ParityStatus.EQUIVALENT


def compare_projections(
    left: ProjectionOutcome,
    right: ProjectionOutcome,
) -> ParityResult:
    """Compare like-for-like projections, or explain why that is unsafe."""

    reasons: list[str] = []
    if left.jurisdiction != right.jurisdiction:
        reasons.append("jurisdictions differ")
    if left.population_id != right.population_id:
        reasons.append("declared populations differ")
    if left.projection_id != right.projection_id:
        reasons.append("projection versions differ")
    if left.schema_fingerprint != right.schema_fingerprint:
        reasons.append("logical schemas differ")

    if reasons:
        return ParityResult(
            status=ParityStatus.NOT_COMPARABLE,
            reasons=tuple(reasons),
            left_projection_digest=left.projection_digest,
            right_projection_digest=right.projection_digest,
            left_count=len(left.records),
            right_count=len(right.records),
        )

    left_records = {
        record.concept.concept_id: canonical_record_payload(record)
        for record in left.records
    }
    right_records = {
        record.concept.concept_id: canonical_record_payload(record)
        for record in right.records
    }
    only_left = tuple(sorted(left_records.keys() - right_records.keys()))
    only_right = tuple(sorted(right_records.keys() - left_records.keys()))
    changed = tuple(
        concept_id
        for concept_id in sorted(left_records.keys() & right_records.keys())
        if left_records[concept_id] != right_records[concept_id]
    )
    status = (
        ParityStatus.EQUIVALENT
        if not only_left and not only_right and not changed
        else ParityStatus.DIFFERENT
    )
    return ParityResult(
        status=status,
        only_left=only_left,
        only_right=only_right,
        changed=changed,
        left_projection_digest=left.projection_digest,
        right_projection_digest=right.projection_digest,
        left_count=len(left.records),
        right_count=len(right.records),
    )
