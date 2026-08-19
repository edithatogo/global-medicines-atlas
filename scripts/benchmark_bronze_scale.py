"""Run the bronze scale benchmark and print the machine-readable receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.bronze_scale import (
    BUDGETS_RELATIVE,
    FIXTURE_RELATIVE,
    run_bronze_scale,
)


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        type=Path,
        default=repository / FIXTURE_RELATIVE,
    )
    parser.add_argument(
        "--budgets",
        type=Path,
        default=repository / BUDGETS_RELATIVE,
    )
    parser.add_argument("--profile", default="ci")
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "build" / "bronze-scale",
    )
    arguments = parser.parse_args()
    receipt = run_bronze_scale(
        output_directory=arguments.output,
        fixture_path=arguments.fixture,
        budgets_path=arguments.budgets,
        profile=arguments.profile,
    )
    print(json.dumps(receipt, sort_keys=True))
    if not receipt["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
