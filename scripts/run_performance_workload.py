"""Run the deterministic representative-scale performance workload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.performance_workload import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_READERS,
    DEFAULT_ROW_COUNT,
    DEFAULT_WARM_RUNS,
    run_workload,
)


def main() -> None:
    """Parse command-line arguments and emit the receipt summary."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("build/performance/representative"),
    )
    parser.add_argument(
        "--budgets",
        type=Path,
        default=Path("quality/budgets.json"),
    )
    parser.add_argument("--row-count", type=int, default=DEFAULT_ROW_COUNT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--readers", type=int, default=DEFAULT_READERS)
    parser.add_argument("--warm-runs", type=int, default=DEFAULT_WARM_RUNS)
    parser.add_argument("--require-process-memory", action="store_true")
    arguments = parser.parse_args()
    receipt = run_workload(
        arguments.output_directory,
        budgets_path=arguments.budgets,
        row_count=arguments.row_count,
        batch_size=arguments.batch_size,
        seed=arguments.seed,
        readers=arguments.readers,
        warm_runs=arguments.warm_runs,
        require_process_memory=arguments.require_process_memory,
    )
    print(json.dumps({"passed": receipt["passed"]}, sort_keys=True))
    if not receipt["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
