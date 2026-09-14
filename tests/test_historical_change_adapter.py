from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from global_medicines_atlas import api as api_mod
from global_medicines_atlas.api import create_app
from global_medicines_atlas.historical_change import (
    HistoricalChange,
    HistoricalChangePage,
    HistoricalChangeService,
    compare_historical_snapshots,
)
from global_medicines_atlas.historical_change_adapter import (
    historical_change_page_payload,
)
from global_medicines_atlas.historical_comparison import NativeSnapshot


def _snapshot(**changes: object) -> NativeSnapshot:
    """Build one bounded source-native observation for outcome controls."""
    return NativeSnapshot.model_validate({
        "source_id": "synthetic-mbs",
        "table": "fees",
        "dimension": "service_benefit",
        "schema_era": "fixture-v1",
        "identity_profile": "literal-item-v1",
        "source_revision": "fixture-1",
        "source_path": "fixture.xml",
        "b1_sha256": "a" * 64,
        "b2_sha256": "b" * 64,
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
        "cohort": "historical",
        "declared_rows": 0,
        "complete": True,
        "rows": (),
        **changes,
    })


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
    ("left", "right", "availability", "state"),
    [
        (None, _snapshot(), "left_missing", "missing_period"),
        (_snapshot(), None, "right_missing", "missing_period"),
        (None, None, "both_missing", "source_outage"),
        (
            _snapshot(complete=False),
            _snapshot(),
            "both_present",
            "source_outage",
        ),
        (
            _snapshot(),
            _snapshot(schema_era="fixture-v2"),
            "both_present",
            "schema_drift",
        ),
    ],
)
def test_history_outcomes_preserve_missingness_and_schema_drift(
    left: NativeSnapshot | None,
    right: NativeSnapshot | None,
    availability: str,
    state: str,
) -> None:
    """Missing snapshots and incompatible eras never become a cessation."""
    result = compare_historical_snapshots(left, right)

    assert result.availability == availability
    assert result.comparison_state == state
    assert result.absence_interpretation == "unknown"
    if state != "compared":
        assert result.changes == ()


@pytest.mark.parametrize(
    "kwargs", [{"offset": -1}, {"limit": 0}, {"limit": 1001}]
)
def test_adapter_preserves_service_bounds(kwargs: dict[str, int]) -> None:
    service = HistoricalChangeService([])
    with pytest.raises(ValueError, match="paging bounds"):
        historical_change_page_payload(service, **kwargs)


def test_history_api_is_bounded_and_preserves_unknown_missingness() -> None:
    history = HistoricalChangeService([
        compare_historical_snapshots(None, None),
        compare_historical_snapshots(None, None),
    ])
    client = TestClient(
        create_app(
            object(),  # type: ignore[arg-type]
            historical_changes=history,
        )
    )

    response = client.get("/api/v1/history", params={"offset": 1, "limit": 1})

    assert response.status_code == 503
    assert response.json()["retryable"] is False
    assert (
        client.get("/api/v1/history", params={"offset": -1}).status_code == 422
    )
    assert client.post("/api/v1/history").status_code == 405
    unavailable = TestClient(create_app(object()))  # type: ignore[arg-type]
    assert unavailable.get("/api/v1/history").status_code == 503

    class InvalidHistory:
        def page(self, *, offset: int, limit: int):
            del offset, limit
            raise ValueError("invalid page")

    invalid = TestClient(
        create_app(
            object(),  # type: ignore[arg-type]
            historical_changes=InvalidHistory(),  # type: ignore[arg-type]
        )
    )
    assert invalid.get("/api/v1/history").status_code == 422

    item = HistoricalChange.model_construct(
        left={},
        right={},
        availability="both_present",
        comparison_state="compared",
        changes=(),
    )
    page = HistoricalChangePage.model_construct(
        items=(item,), offset=0, limit=1, total=1, next_offset=None
    )

    class StaticHistory:
        def page(self, *, offset: int, limit: int) -> HistoricalChangePage:
            del offset, limit
            return page

    available = TestClient(
        create_app(object(), historical_changes=StaticHistory())
    )  # type: ignore[arg-type]
    assert available.get("/api/v1/history").status_code == 200
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(api_mod, "_MAX_HISTORY_PAGE_BYTES", 1)
    assert available.get("/api/v1/history").status_code == 503
    monkeypatch.undo()
