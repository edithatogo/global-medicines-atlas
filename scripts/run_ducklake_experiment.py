"""Run the governed DuckLake comparison."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from global_medicines_atlas.ducklake_experiment import run_ducklake_comparison


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gma-ducklake-") as directory:
        receipt = run_ducklake_comparison(
            fixture_path=args.fixture,
            workspace=Path(directory),
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
