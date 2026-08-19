"""Stable bronze scale benchmark runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from global_medicines_atlas.bronze_scale import run_bronze_scale


def benchmark(
    *,
    output_directory: Path,
    fixture_path: Path,
    budgets_path: Path,
    profile: str = "ci",
) -> dict[str, Any]:
    """Run the committed CI or projection profile and return the receipt."""

    return run_bronze_scale(
        output_directory=output_directory,
        fixture_path=fixture_path,
        budgets_path=budgets_path,
        profile=profile,
    )
