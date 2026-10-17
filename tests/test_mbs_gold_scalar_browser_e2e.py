"""Chromium coverage for exact synthetic MBS scalar filters."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from test_mbs_gold_scalar_projection import (
    _exercise_exact_synthetic_scalar_trust_path,  # ruff: ignore[import-private-name] -- shared trust fixture
)


@pytest.mark.parametrize(
    ("field_name", "values", "operator", "filter_value", "expected"),
    [
        (
            "Benefit100",
            ["10.25", "2.75"],
            ">=",
            Decimal("10.00"),
            "10.250000000",
        ),
        (
            "BenefitStartDate",
            ["2025-07-01", "2025-08-01"],
            "=",
            {"type": "date", "value": "2025-07-01"},
            "2025-07-01",
        ),
    ],
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
