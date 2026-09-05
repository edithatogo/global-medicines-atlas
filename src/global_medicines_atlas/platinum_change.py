"""Bounded Platinum paging for historical change observations.

The page is a transport/evidence envelope over an already computed
``HistoricalChange``.  It never interprets absence as cessation and never
claims that a truncated page is a complete comparison.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from .historical_change import ChangeObservation, HistoricalChange
from .platinum_surface_contracts import PlatinumSurfaceModel, Sha256

_MAX_PAGE_LIMIT = 1000


class ChangePage(PlatinumSurfaceModel):
    """A deterministic, bounded page of literal historical observations."""

    schema_version: Literal["1.0"] = "1.0"
    comparison_state: str
    availability: str
    absence_interpretation: Literal["unknown"] = "unknown"
    changes: tuple[ChangeObservation, ...]
    offset: int = Field(ge=0)
    page_limit: int = Field(ge=1, le=_MAX_PAGE_LIMIT)
    total_changes: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    page_sha256: Sha256
    comparison_complete: bool = False

    @model_validator(mode="after")
    def coherent(self) -> ChangePage:
        if len(self.changes) > self.page_limit:
            raise ValueError("change page exceeds page limit")
        if self.offset + len(self.changes) > self.total_changes:
            raise ValueError("change page exceeds total changes")
        expected = (
            self.offset + len(self.changes)
            if self.offset + len(self.changes) < self.total_changes
            else None
        )
        if self.next_offset != expected:
            raise ValueError("next offset does not match change page")
        if self.comparison_complete and self.next_offset is not None:
            raise ValueError("incomplete page cannot claim complete comparison")
        return self


def _digest(
    comparison: HistoricalChange,
    changes: tuple[ChangeObservation, ...],
    *,
    offset: int,
    limit: int,
) -> str:
    payload = {
        "availability": comparison.availability,
        "changes": [item.model_dump(mode="json") for item in changes],
        "comparison_state": comparison.comparison_state,
        "limit": limit,
        "offset": offset,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_change_page(
    comparison: HistoricalChange,
    *,
    limit: int = 100,
    offset: int = 0,
) -> ChangePage:
    """Build one bounded page from a validated historical comparison."""
    if type(limit) is not int or not 1 <= limit <= _MAX_PAGE_LIMIT:
        raise ValueError("change page limit must be between 1 and 1000")
    if type(offset) is not int or offset < 0:
        raise ValueError("change page offset must be non-negative")
    total = len(comparison.changes)
    if offset > total:
        raise ValueError("change page offset exceeds total changes")
    changes = comparison.changes[offset : offset + limit]
    next_offset = (
        offset + len(changes) if offset + len(changes) < total else None
    )
    return ChangePage(
        comparison_state=comparison.comparison_state,
        availability=comparison.availability,
        changes=changes,
        offset=offset,
        page_limit=limit,
        total_changes=total,
        next_offset=next_offset,
        page_sha256=_digest(comparison, changes, offset=offset, limit=limit),
        comparison_complete=(next_offset is None),
    )


__all__ = ["ChangePage", "build_change_page"]
