"""Aggregate diagnostics retain ambiguity and nominal unknown categories."""

import json
import sys

import pytest
from scripts import qualify_mbs_q1_source_meanings as module
from scripts.qualify_mbs_q1_source_meanings import diagnose, qualify


def row(item, value, age="Unknown"):
    return ("2016", "3", item, "SYNTHETIC", age, "F", "10", value)


def test_rounding_is_not_exact_equivalence():
    result = diagnose([row("a", "10")], [row("a", "10.4")])
    assert result["full_key_counts"]["lower"] == 1
    assert result["workbook_equals_rounded_csv"]["ROUND_DOWN_0"] == 1
    assert result["workbook_equals_rounded_csv"]["ROUND_DOWN_1"] == 0
    assert result["workbook_age_row_counts"]["native_unknown"] == 1
    assert result["native_unknown_category"]["numeric_bounds"] is None
    assert "SYNTHETIC" not in json.dumps(result)


def test_duplicate_keys_and_nonfinite_measures_are_excluded():
    result = diagnose(
        [row("a", "1"), row("a", "2"), row("b", "NaN")],
        [row("a", "1"), row("b", "Infinity")],
    )
    assert result["full_key_counts"]["ambiguous_keys_excluded"] == 1
    assert result["full_key_counts"]["nonnumeric_pairs_excluded"] == 1
    assert "numeric_pairs" not in result["full_key_counts"]


def test_metadata_rows_cannot_define_data_age_categories():
    result = diagnose([("header",) * 8], [])
    assert result["workbook_age_row_counts"] == {}


def test_local_qualification_fails_before_network(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="exact main Actions"):
        qualify("a" * 40)


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("GITHUB_REPOSITORY", "other/repo"),
        ("GITHUB_REF", "refs/heads/other"),
        ("GITHUB_SHA", "b" * 40),
    ],
)
def test_wrong_hosted_identity_fails_before_network(
    monkeypatch, variable, value
):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match="exact main Actions"):
        qualify("a" * 40)


def test_unknown_marker_is_not_blank_zero_or_casefolded():
    result = diagnose(
        [
            row("a", "1", "Unknown"),
            row("b", "1", "unknown"),
            row("c", "1", None),
            row("d", "1", "0"),
        ],
        [],
    )
    assert result["workbook_age_row_counts"] == {
        "native_unknown": 1,
        "other": 3,
    }


def test_cli_check_is_deterministic_and_read_only(tmp_path, monkeypatch):
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(module, "qualify", lambda _: {"synthetic": True})
    arguments = [
        "diagnostic",
        "--exact-commit",
        "a" * 40,
        "--output",
        str(output),
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    module.main()
    before = output.read_bytes()
    monkeypatch.setattr(sys, "argv", [*arguments, "--check"])
    module.main()
    assert output.read_bytes() == before
    output.write_text('{"tampered": true}')
    with pytest.raises(SystemExit, match="stale"):
        module.main()
    assert output.read_text() == '{"tampered": true}'
