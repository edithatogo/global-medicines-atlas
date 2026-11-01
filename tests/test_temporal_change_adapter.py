from __future__ import annotations

import pytest
from test_temporal_coverage_route import _observation  # ruff: ignore[import-private-name] -- shared synthetic fixture

from global_medicines_atlas.historical_change import (
    HistoricalChangeService,
    compare_historical_snapshots,
)
from global_medicines_atlas.temporal_change_adapter import (
    TemporalChangeRouteAdapter,
)
from global_medicines_atlas.temporal_coverage_route import (
    TemporalCoverageRouteAdapter,
)


def test_composed_page_keeps_sources_separate_and_json_safe() -> None:
    adapter = TemporalChangeRouteAdapter(
        TemporalCoverageRouteAdapter([_observation("a"), _observation("b")]),
        HistoricalChangeService([
            compare_historical_snapshots(None, None),
            compare_historical_snapshots(None, None),
        ]),
    )

    payload = adapter.page_payload(offset=1, limit=1)

    assert payload["offset"] == 1
    assert payload["limit"] == 1
    assert payload["temporal"]["items"][0]["observation_id"] == "b"
    assert (
        payload["historical"]["items"][0]["absence_interpretation"] == "unknown"
    )


@pytest.mark.parametrize(
    "kwargs", [{"offset": -1}, {"limit": 0}, {"limit": 1001}]
)
def test_composed_page_rejects_unbounded_requests(
    kwargs: dict[str, int],
) -> None:
    adapter = TemporalChangeRouteAdapter(
        TemporalCoverageRouteAdapter([]), HistoricalChangeService([])
    )
    with pytest.raises(ValueError, match="paging bounds"):
        adapter.page_payload(**kwargs)
