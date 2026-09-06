from __future__ import annotations

import pytest

from global_medicines_atlas.pbs_snapshot_comparison import compare_pbs_snapshots


def test_reports_stable_addition_cessation_and_change() -> None:
    legacy = [
        {"native_xml_id": "B", "benefit": "2"},
        {"native_xml_id": "C", "benefit": "3"},
    ]
    current = [
        {"native_xml_id": "A", "benefit": "1"},
        {"native_xml_id": "B", "benefit": "updated"},
    ]
    assert compare_pbs_snapshots(legacy, current) == [
        {
            "key": "A",
            "kind": "addition",
            "before": None,
            "after": {"native_xml_id": "A", "benefit": "1"},
            "interpretation": "literal_snapshot_difference",
        },
        {
            "key": "B",
            "kind": "change",
            "before": {"native_xml_id": "B", "benefit": "2"},
            "after": {"native_xml_id": "B", "benefit": "updated"},
            "interpretation": "literal_snapshot_difference",
        },
        {
            "key": "C",
            "kind": "cessation",
            "before": {"native_xml_id": "C", "benefit": "3"},
            "after": None,
            "interpretation": "literal_snapshot_difference",
        },
    ]


@pytest.mark.parametrize("rows", [[{"benefit": "missing"}], [{"native_xml_id": ""}]])
def test_rejects_rows_without_non_empty_identity(rows) -> None:
    with pytest.raises(ValueError, match="non-empty string key"):
        compare_pbs_snapshots(rows, [])


def test_rejects_duplicate_identity() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        compare_pbs_snapshots(
            [{"native_xml_id": "A"}, {"native_xml_id": "A"}], []
        )
