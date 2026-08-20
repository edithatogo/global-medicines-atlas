"""Run one isolated table-format experiment and always write its receipt."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from global_medicines_atlas.table_format_comparison import run_table_format


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--engine", required=True, choices=("iceberg_ready_parquet", "delta")
    )
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(
        prefix=f"gma-{arguments.engine}-"
    ) as temporary:
        receipt = run_table_format(arguments.engine, Path(temporary))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
