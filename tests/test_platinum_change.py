from datetime import UTC, datetime

import pytest

from global_medicines_atlas.historical_change import (
    compare_historical_snapshots,
)
from global_medicines_atlas.historical_comparison import (
    NativeField,
    NativeRow,
    NativeSnapshot,
)
from global_medicines_atlas.platinum_change import build_change_page


def snap(value: str) -> NativeSnapshot:
    return NativeSnapshot(
        source_id="source", table="table", dimension="funding", schema_era="era",
        identity_profile="identity", source_revision="rev", source_path="path",
        b1_sha256="a" * 64, b2_sha256="b" * 64, observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        cohort="current", declared_rows=1, complete=True,
        rows=(NativeRow(native_id="item", occurrence_id="occ", fields=(NativeField(name="status", state="value", value=value),)),),
    )


def test_change_page_is_bounded_and_deterministic() -> None:
    comparison = compare_historical_snapshots(snap("old"), snap("new"))
    page = build_change_page(comparison, limit=1)
    assert page.comparison_complete is True
    assert page.next_offset is None
    assert page.page_sha256 == build_change_page(comparison, limit=1).page_sha256


def test_missing_period_is_not_complete_negative_evidence() -> None:
    page = build_change_page(compare_historical_snapshots(None, snap("new")))
    assert page.changes == ()
    assert page.absence_interpretation == "unknown"
    assert page.comparison_complete is True


def test_offset_and_limit_are_fail_closed() -> None:
    comparison = compare_historical_snapshots(snap("old"), snap("new"))
    with pytest.raises(ValueError, match="limit"):
        build_change_page(comparison, limit=0)
    with pytest.raises(ValueError, match="offset"):
        build_change_page(comparison, offset=2)
