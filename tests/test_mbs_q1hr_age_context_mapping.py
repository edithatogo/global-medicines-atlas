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
        ('"0-4"', (0, 4)),
        ('"5 to 14 years', None),
        ("age 0 to under 1 year", (0, 0)),
        ("aged 5 years to less than 15 years", (5, 14)),
        ("age group: 5-14 years", (5, 14)),
        ("age 5", (5, 5)),
        (">=85", (85, None)),
        ('">=85"', (85, None)),
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
        "candidate_category_pairs_with_equal_normalized_label_text": 0,
        "candidate_category_pairs_with_different_normalized_label_text": 2,
    }


def test_exact_label_pair_counts_are_separate_from_age_band_semantics() -> None:
    result = mapping._age_pair_semantics(
        Counter({
            ("0-4", '"0-4"'): 1,
            ("unknown", '"unknown"'): 1,
            ("1-3", '"1-4"'): 1,
        })
    )

    assert result["candidate_category_pairs_with_equal_year_bounds"] == 1
    assert result["candidate_category_pairs_with_unparsed_labels"] == 1
    assert (
        result["candidate_category_pairs_with_equal_normalized_label_text"] == 2
    )
    assert (
        result["candidate_category_pairs_with_different_normalized_label_text"]
        == 1
    )


def test_age_label_syntax_counts_do_not_return_source_labels() -> None:
    assert mapping._age_label_syntax_counts({
        "0-4",
        "75+",
        "under 1",
        "not stated",
        "aged 5",
    }) == {
        "closed_range": 1,
        "non_numeric": 1,
        "open_ended_lower": 1,
        "single_age_or_single_year": 2,
    }


def test_candidate_report_keeps_row_labels_out_of_results() -> None:
    workbook: list[tuple[str | None, ...]] = [
        ("2016", "3", "1", "NSW", "0-4", "F", "10", "5")
    ]
    csv_values: list[tuple[str | None, ...]] = [
        ("2016", "3", "1", "NSW", "0 to 4", "F", "10", "5")
    ]

    result = mapping._candidate_relationships(workbook, csv_values)

    assert result["candidate_category_pairs_with_equal_year_bounds"] == 1
    assert result["workbook_context_occurrences_without_csv_match"] == 0
    assert result["csv_context_occurrences_without_workbook_match"] == 0
    assert result["workbook_age_label_syntax_counts"] == {"closed_range": 1}
    assert result["csv_age_label_syntax_counts"] == {"closed_range": 1}
    assert result["source_values_or_category_labels_emitted"] is False


def test_two_malformed_quoted_labels_do_not_count_as_equal() -> None:
    result = mapping._age_pair_semantics(Counter({('"0-4', '"5-9'): 1}))
    assert (
        result["candidate_category_pairs_with_equal_normalized_label_text"] == 0
    )
    assert result["candidate_category_pairs_with_unparsed_labels"] == 1
