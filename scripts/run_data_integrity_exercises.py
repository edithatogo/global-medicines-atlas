"""Run medicine-data integrity exercises and emit a durable receipt."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.data_integrity import run_data_integrity_exercises


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/data-integrity-receipt.json"),
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    receipt = run_data_integrity_exercises()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        receipt.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(arguments.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
