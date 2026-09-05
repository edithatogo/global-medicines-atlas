"""Pure, bounded route adapter for temporal coverage observations.

The adapter is intentionally transport-agnostic.  It pages an injected set of
already admitted observations and emits JSON-safe source evidence; it never
acquires, stores, or interprets observations.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .coverage import CoverageObservation

_MAX_PAGE_SIZE = 1000


class TemporalCoveragePage(BaseModel):
    """A deterministic bounded page with explicit temporal evidence rows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[CoverageObservation, ...]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=_MAX_PAGE_SIZE)
    total: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)


class TemporalCoverageRouteAdapter:
    """Render injected observations for a read-only temporal route."""

    def __init__(self, observations: Sequence[CoverageObservation]) -> None:
        self._observations = tuple(observations)

    def page(self, *, offset: int = 0, limit: int = 100) -> TemporalCoveragePage:
        """Return a bounded page without inferring coverage or validity."""
        if offset < 0 or limit < 1 or limit > _MAX_PAGE_SIZE:
            raise ValueError("temporal coverage paging bounds are invalid")
        total = len(self._observations)
        items = self._observations[offset : offset + limit]
        end = offset + len(items)
        return TemporalCoveragePage(
            items=items,
            offset=offset,
            limit=limit,
            total=total,
            next_offset=end if end < total else None,
        )

    def page_payload(self, *, offset: int = 0, limit: int = 100) -> dict[str, Any]:
        """Return only JSON-safe source-faithful observations for transport."""
        return self.page(offset=offset, limit=limit).model_dump(mode="json")


__all__ = ["TemporalCoveragePage", "TemporalCoverageRouteAdapter"]
