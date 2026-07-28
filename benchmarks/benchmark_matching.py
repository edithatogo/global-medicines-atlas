"""Stable Python-reference matching benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from global_medicines_atlas.matching import MatchingRecord, generate_candidates


@dataclass(frozen=True)
class BenchmarkResult:
    engine: str
    iterations: int
    candidates: int
    elapsed_seconds: float


def benchmark(
    source: MatchingRecord,
    targets: tuple[MatchingRecord, ...],
    *,
    iterations: int,
) -> BenchmarkResult:
    started = perf_counter()
    count = 0
    for _ in range(iterations):
        count += len(generate_candidates(source, targets).candidates)
    return BenchmarkResult(
        engine="python-reference",
        iterations=iterations,
        candidates=count,
        elapsed_seconds=perf_counter() - started,
    )
