"""Synthetic tests for internal PBS ATC-shaped value comparison."""

from __future__ import annotations

from scripts import qualify_pbs_utilisation_atc_internal_consistency as screen


def test_internal_set_comparison_reports_counts_and_opaque_digest() -> None:
    result = screen.compare_code_sets(
        {"_atc_values": {"A10AB02", "B01AA07"}},
        {"_atc_values": {"A10AB02", "C09AA05"}},
    )

    assert result["item_map_distinct_atc_shaped_values"] == 2
    assert result["summary_distinct_atc_shaped_values"] == 2
    assert result["distinct_values_in_both"] == 1
    assert result["item_map_values_absent_from_summary"] == 1
    assert result["summary_values_absent_from_item_map"] == 1
    assert result["sets_equal"] is False
    assert len(result["shared_set_sha256"]) == 64
    assert not any(
        code in repr(result) for code in ("A10AB02", "B01AA07", "C09AA05")
    )


def test_code_normalization_is_case_and_edge_whitespace_only() -> None:
    assert screen._normalize_code(" a10ab02 ") == "A10AB02"
    assert screen.ATC_PATTERN.fullmatch(screen._normalize_code(" a10ab02 "))
    assert not screen.ATC_PATTERN.fullmatch("A10-AB02")
