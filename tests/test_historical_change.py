from datetime import UTC, datetime

import pytest

from global_medicines_atlas.historical_change import (
    HistoricalChangeService,
    compare_historical_snapshots,
)
from global_medicines_atlas.historical_comparison import (
    NativeField,
    NativeRow,
    NativeSnapshot,
)


def snapshot(
    *, value: str, complete: bool = True, era: str = "era-1"
) -> NativeSnapshot:
    return NativeSnapshot(
        source_id="source",
        table="table",
        dimension="funding",
        schema_era=era,
        identity_profile="identity",
        source_revision="rev",
        source_path="path",
        b1_sha256="a" * 64,
        b2_sha256="b" * 64,
        observed_at=datetime.now(UTC),
        cohort="historical",
        declared_rows=1,
        complete=complete,
        rows=(
            NativeRow(
                native_id="item-1",
                occurrence_id="occ-1",
                fields=(
                    NativeField(name="status", state="value", value=value),
                ),
            ),
        ),
    )


def test_change_is_literal_and_not_cessation() -> None:
    result = compare_historical_snapshots(
        snapshot(value="old"), snapshot(value="new")
    )
    assert result.comparison_state == "compared"
    assert result.changes[0].kind == "field_changed"
    assert result.absence_interpretation == "unknown"


def test_missing_period_has_no_inferred_changes() -> None:
    result = compare_historical_snapshots(None, snapshot(value="new"))
    assert result.availability == "left_missing"
    assert result.comparison_state == "missing_period"
    assert result.changes == ()


def test_incomplete_snapshot_is_source_outage() -> None:
    result = compare_historical_snapshots(
        snapshot(value="old", complete=False), snapshot(value="new")
    )
    assert result.comparison_state == "source_outage"
    assert result.changes == ()


def test_schema_era_drift_is_not_a_change() -> None:
    result = compare_historical_snapshots(
        snapshot(value="old"), snapshot(value="new", era="era-2")
    )
    assert result.comparison_state == "schema_drift"
    assert result.changes == ()


def test_service_pages_injected_changes_deterministically() -> None:
    first = compare_historical_snapshots(None, snapshot(value="new"))
    second = compare_historical_snapshots(snapshot(value="old"), snapshot(value="new"))
    page = HistoricalChangeService((first, second)).page(offset=1, limit=1)
    assert page.items == (second,)
    assert page.total == 2
    assert page.next_offset is None


def test_service_rejects_unbounded_paging() -> None:
    service = HistoricalChangeService(())
    with pytest.raises(ValueError, match="bounds"):
        service.page(limit=1001)
