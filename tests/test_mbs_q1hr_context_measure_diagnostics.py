"""Context-key joins must not confuse row order, repeats or missing values."""

import json

import pytest
from scripts.qualify_mbs_q1hr_context_measure_diagnostics import diagnose


def _row(item: str, benefit: str | None, age: str = "5-9"):
    return ("2016", "3", item, "SYNTHETIC_STATE", age, "F", "10", benefit)


def test_join_compares_measures_after_row_reordering_and_outer_quotes() -> None:
    report = diagnose(
        [_row("synthetic-a", "10"), _row("synthetic-b", "20")],
        [_row("synthetic-b", "20.0", '"5-9"'), _row("synthetic-a", "10")],
    )
    assert report["unambiguous_full_key_pairs"] == 2
    assert report["exact_numeric_matches_by_fixed_scale"]["1"] == 2
    assert report["workbook_only_rows"] == 0
    assert "synthetic-a" not in json.dumps(report)
    assert "SYNTHETIC_STATE" not in json.dumps(report)


def test_ambiguous_keys_are_excluded_and_missing_values_not_equal() -> None:
    report = diagnose(
        [_row("repeat", "1"), _row("repeat", "2"), _row("missing", None)],
        [_row("repeat", "1"), _row("missing", "NaN")],
    )
    assert report["ambiguous_shared_full_keys_excluded"] == 1
    assert report["shared_keys_with_multiplicity_mismatch"] == 1
    assert report["unambiguous_numeric_benefit_pairs"] == 0
    assert report["exact_numeric_matches_by_fixed_scale"]["1"] == 0


def test_residual_rows_are_classified_without_values_or_deletion() -> None:
    report = diagnose([(None,) * 8, _row("residual", "Infinity")], [])
    assert report["workbook_only_rows"] == 2
    assert report["workbook_only_rows_with_all_context_fields_missing"] == 1
    assert report["workbook_only_row_field_shapes"]["Benefits"] == {
        "missing": 1,
        "text": 1,
    }
    assert "residual" not in json.dumps(report)


def test_partial_source_row_is_rejected() -> None:
    with pytest.raises(ValueError, match="eight source columns"):
        diagnose([("incomplete",)], [])


def test_precision_diagnostics_do_not_hide_large_measure_disagreements() -> (
    None
):
    report = diagnose(
        [_row("float", "10.0000000001"), _row("different", "100")],
        [_row("float", "10.00"), _row("different", "1")],
    )
    assert report["exact_numeric_matches_by_fixed_scale"]["1"] == 0
    precision = report["numeric_precision_diagnostics"]
    assert precision["rounded_2_decimal_places"] == 1
    assert precision["absolute_difference_le_0.000000001"] == 1
    assert precision["absolute_difference_gt_0.01"] == 1
