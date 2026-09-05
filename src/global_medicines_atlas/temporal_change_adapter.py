"""Bounded, transport-neutral composition of temporal and change evidence.

This module composes two already-admitted read-only adapters.  It does not
join, infer, or reconcile their observations; the two result sets remain
explicitly separate in the response so that temporal coverage is not mistaken
for a historical change finding.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .historical_change import HistoricalChangeService
from .temporal_coverage_route import TemporalCoverageRouteAdapter

_MAX_PAGE_SIZE = 1000


class TemporalChangePage(BaseModel):
    """A bounded page containing independent temporal and change collections."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    temporal: dict[str, Any]
    historical: dict[str, Any]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=_MAX_PAGE_SIZE)


class TemporalChangeRouteAdapter:
    """Compose injected temporal and historical pages without external I/O."""

    def __init__(
        self,
        temporal: TemporalCoverageRouteAdapter,
        historical: HistoricalChangeService,
    ) -> None:
        self._temporal = temporal
        self._historical = historical

    def page(self, *, offset: int = 0, limit: int = 100) -> TemporalChangePage:
        """Return equally bounded pages while retaining each source envelope."""
        if offset < 0 or limit < 1 or limit > _MAX_PAGE_SIZE:
            raise ValueError("temporal change paging bounds are invalid")
        return TemporalChangePage(
            temporal=self._temporal.page_payload(offset=offset, limit=limit),
            historical=self._historical.page(offset=offset, limit=limit).model_dump(
                mode="json"
            ),
            offset=offset,
            limit=limit,
        )

    def page_payload(self, *, offset: int = 0, limit: int = 100) -> dict[str, Any]:
        """Return a JSON-safe response suitable for a read-only transport."""
        return self.page(offset=offset, limit=limit).model_dump(mode="json")


__all__ = ["TemporalChangePage", "TemporalChangeRouteAdapter"]
