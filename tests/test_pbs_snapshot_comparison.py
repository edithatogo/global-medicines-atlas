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


@pytest.mark.parametrize(
    "rows", [[{"benefit": "missing"}], [{"native_xml_id": ""}]]
)
def test_rejects_rows_without_non_empty_identity(rows) -> None:
    with pytest.raises(ValueError, match="non-empty string key"):
        compare_pbs_snapshots(rows, [])


def test_rejects_duplicate_identity() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        compare_pbs_snapshots(
            [{"native_xml_id": "A"}, {"native_xml_id": "A"}], []
        )


def test_marks_one_sided_rows_neutral_when_snapshot_incomplete() -> None:
    result = compare_pbs_snapshots(
        [{"native_xml_id": "A"}],
        [{"native_xml_id": "B"}],
        legacy_complete=False,
        current_complete=False,
    )
    assert [item["kind"] for item in result] == [
        "present_only_legacy",
        "present_only_current",
    ]


def test_bounds_materialization_and_deep_copies_nested_values() -> None:
    nested = {"restrictions": ["x"]}
    result = compare_pbs_snapshots(
        [{"native_xml_id": "A", "meta": nested}], [], max_rows=1
    )
    nested["restrictions"].append("mutated")
    assert result[0]["before"] == {
        "native_xml_id": "A",
        "meta": {"restrictions": ["x"]},
    }
    with pytest.raises(ValueError, match="max_rows"):
        compare_pbs_snapshots(
            [{"native_xml_id": "A"}, {"native_xml_id": "B"}], [], max_rows=1
        )
