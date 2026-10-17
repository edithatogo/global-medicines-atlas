"""Chromium coverage for exact synthetic MBS scalar filters."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_mbs_gold_scalar_projection import (
    _EXACT_SCALAR_CASES,  # ruff: ignore[import-private-name] -- shared cases
    _exercise_exact_synthetic_scalar_trust_path,  # ruff: ignore[import-private-name] -- shared trust fixture
)


@pytest.mark.parametrize(
    ("field_name", "values", "operator", "filter_value", "expected"),
    _EXACT_SCALAR_CASES,
)
@pytest.mark.e2e
def test_exact_synthetic_scalar_trust_path_in_chromium(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    values: list[str],
    operator: str,
    filter_value: str | dict[str, str],
    expected: str,
) -> None:
    """Carry exact Decimal and date results through the browser form."""
    _exercise_exact_synthetic_scalar_trust_path(
        tmp_path,
        monkeypatch,
        field_name,
        values,
        operator,
        filter_value,
        expected,
        exercise_browser=True,
    )
