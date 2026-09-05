from datetime import UTC, datetime

import pytest

from global_medicines_atlas.coverage import CoverageObservation
from global_medicines_atlas.models import AssertionKind, TimeInterval
from global_medicines_atlas.temporal_coverage_route import (
    TemporalCoverageRouteAdapter,
)


def _observation(identifier: str) -> CoverageObservation:
    moment = datetime(2025, 1, 1, tzinfo=UTC)
    return CoverageObservation(
        jurisdiction="AU",
        source_id="source",
        receipt_id="receipt",
        observation_id=identifier,
        population_partition_id="all",
        dimension=AssertionKind.FUNDING,
        medicine_concept_id="concept",
        assertion_type="listed",
        assertion_status="observed",
        concept_population="aggregate:all",
        valid_time=TimeInterval(start=moment),
        observed_time=TimeInterval(start=moment),
        assertion_count=1,
        concept_numerator=1,
    )


def test_route_pages_source_faithful_json() -> None:
    adapter = TemporalCoverageRouteAdapter((
        _observation("one"),
        _observation("two"),
    ))
    payload = adapter.page_payload(offset=1, limit=1)
    assert payload["total"] == 2
    assert payload["next_offset"] is None
    assert payload["items"][0]["observation_id"] == "two"
    assert payload["items"][0]["valid_time"]["start"].startswith("2025-01-01")


@pytest.mark.parametrize(
    "kwargs", [{"offset": -1}, {"limit": 0}, {"limit": 1001}]
)
def test_route_rejects_unbounded_requests(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="paging bounds"):
        TemporalCoverageRouteAdapter(()).page(**kwargs)
