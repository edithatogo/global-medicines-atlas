"""Write deterministic candidate-retrieval evidence for synthetic cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from global_medicines_atlas.frontier_candidate_benchmark import (
    benchmark_synthetic_candidates,
    canonical_candidate_benchmark_bytes,
    load_synthetic_matching_cases,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures/matching"),
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.limit < 1:
        parser.error("--limit must be positive")

    cases = load_synthetic_matching_cases(arguments.fixture_dir)
    receipt = benchmark_synthetic_candidates(cases, limit=arguments.limit)
    output = canonical_candidate_benchmark_bytes(receipt)
    if arguments.output is None:
        sys.stdout.buffer.write(output)
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_bytes(output)


if __name__ == "__main__":
    main()
