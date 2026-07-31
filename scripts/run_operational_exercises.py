"""Run bounded release-candidate operational exercises."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.operational_exercises import (
    run_operational_exercises,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/operational-exercises/receipt.json"),
    )
    parser.add_argument(
        "--budgets",
        type=Path,
        default=Path("quality/budgets.json"),
    )
    arguments = parser.parse_args()
    receipt = run_operational_exercises(
        arguments.output,
        budgets_path=arguments.budgets,
    )
    print(arguments.output.as_posix())
    return 0 if receipt.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
