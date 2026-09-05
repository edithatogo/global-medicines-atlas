from __future__ import annotations

import pytest

from global_medicines_atlas.historical_change import (
    HistoricalChangeService,
    compare_historical_snapshots,
)
from global_medicines_atlas.historical_change_adapter import (
    historical_change_page_payload,
)


def test_adapter_returns_bounded_json_safe_page() -> None:
    service = HistoricalChangeService([
        compare_historical_snapshots(None, None),
        compare_historical_snapshots(None, None),
    ])

    payload = historical_change_page_payload(service, offset=1, limit=1)

    assert payload["offset"] == 1
    assert payload["limit"] == 1
    assert payload["total"] == 2
    assert payload["next_offset"] is None
    assert payload["items"][0]["absence_interpretation"] == "unknown"


@pytest.mark.parametrize(
    "kwargs", [{"offset": -1}, {"limit": 0}, {"limit": 1001}]
)
def test_adapter_preserves_service_bounds(kwargs: dict[str, int]) -> None:
    service = HistoricalChangeService([])
    with pytest.raises(ValueError, match="paging bounds"):
        historical_change_page_payload(service, **kwargs)
