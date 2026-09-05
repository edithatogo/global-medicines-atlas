"""Pure transport adapter for bounded historical-change pages.

The adapter deliberately accepts an injected service and returns JSON-safe
metadata only.  It performs no acquisition, persistence, or external I/O.
"""

from __future__ import annotations

from typing import Any

from .historical_change import HistoricalChangePage, HistoricalChangeService


def historical_change_page_payload(
    service: HistoricalChangeService,
    *,
    offset: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    """Render one bounded page for a read-only route.

    Pydantic validation remains the source of truth for the envelope, while
    ``mode="json"`` ensures datetime and nested model values are transport
    safe.  Paging bounds are enforced by the injected service.
    """

    page: HistoricalChangePage = service.page(offset=offset, limit=limit)
    return page.model_dump(mode="json")


__all__ = ["historical_change_page_payload"]
