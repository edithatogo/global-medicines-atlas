"""Run the bounded Python-reference matching benchmark."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

from global_medicines_atlas.matching import MatchingRecord

MINIMUM_FIXTURE_RECORDS = 2


def main() -> None:
    repository = str(Path(__file__).resolve().parents[1])
    if repository not in sys.path:
        sys.path.insert(0, repository)
    benchmark = importlib.import_module(
        "benchmarks.benchmark_matching"
    ).benchmark
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("benchmarks/fixtures/matching_benchmark.jsonl"),
    )
    parser.add_argument("--iterations", type=int, default=100)
    arguments = parser.parse_args()
    if arguments.iterations < 1:
        parser.error("--iterations must be positive")
    records = [
        MatchingRecord.model_validate_json(line)
        for line in arguments.fixture.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(records) < MINIMUM_FIXTURE_RECORDS:
        parser.error("fixture must contain a source and at least one target")
    result = benchmark(
        records[0],
        tuple(records[1:]),
        iterations=arguments.iterations,
    )
    print(json.dumps(result.__dict__, sort_keys=True))


if __name__ == "__main__":
    main()
