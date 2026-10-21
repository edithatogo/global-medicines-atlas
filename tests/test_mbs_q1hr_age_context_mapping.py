"""Synthetic checks for value-free age-band comparison helpers."""

from __future__ import annotations

from collections import Counter

import pytest
from scripts import qualify_mbs_q1hr_age_context_mapping as mapping


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("0-4", (0, 4)),
        ("5 to 14 years", (5, 14)),
        ("under 1", (0, 0)),
        ("75+", (75, None)),
        ("not stated", None),
        ("14-5", None),
    ],
)
def test_explicit_whole_year_bands_parse_fail_closed(
    label: str, expected: tuple[int, int | None] | None
) -> None:
    assert mapping._age_band(label) == expected


def test_age_pair_semantics_reports_only_aggregate_counts() -> None:
    result = mapping._age_pair_semantics(
        Counter({("0-4", "0 to 4"): 25, ("5-14", "5-19"): 1})
    )

    assert result == {
        "candidate_category_pairs_with_explicit_year_bounds": 2,
        "candidate_category_pairs_with_equal_year_bounds": 1,
        "candidate_category_pairs_with_different_year_bounds": 1,
        "candidate_category_pairs_with_unparsed_labels": 0,
    }


def test_candidate_report_keeps_row_labels_out_of_results() -> None:
    workbook = [("2016", "3", "1", "NSW", "0-4", "F", "10", "5")]
    csv_values = [("2016", "3", "1", "NSW", "0 to 4", "F", "10", "5")]

    result = mapping._candidate_relationships(workbook, csv_values)

    assert result["candidate_category_pairs_with_equal_year_bounds"] == 1
    assert result["workbook_context_occurrences_without_csv_match"] == 0
    assert result["csv_context_occurrences_without_workbook_match"] == 0
    assert result["source_values_or_category_labels_emitted"] is False
