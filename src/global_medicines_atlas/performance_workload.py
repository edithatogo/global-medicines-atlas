"""Deterministic representative-scale analytical performance workload."""

from __future__ import annotations

import json
import math
import os
import platform
import sys
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

import duckdb
import orjson
import polars as pl
import pyarrow.parquet as pq

if sys.platform == "win32":

    def _process_peak_memory_mib() -> float | None:
        """Return no peak RSS when unavailable in the standard library."""
        return None

else:
    import resource

    def _process_peak_memory_mib() -> float | None:
        """Return process peak RSS from the POSIX resource interface."""
        peak = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        divisor = MEBIBYTE if sys.platform == "darwin" else 1024
        return peak / divisor

DEFAULT_ROW_COUNT = 1_000_000
DEFAULT_BATCH_SIZE = 100_000
DEFAULT_READERS = 4
DEFAULT_WARM_RUNS = 5
MEBIBYTE = 1024 * 1024

QUERY = """
SELECT
    jurisdiction,
    status_kind,
    count(*)::BIGINT AS assertion_count,
    count(DISTINCT concept_id)::BIGINT AS concept_count
FROM read_parquet(?)
WHERE effective_year BETWEEN 2015 AND 2026
GROUP BY jurisdiction, status_kind
ORDER BY jurisdiction, status_kind
"""


@dataclass(frozen=True)
class Measurement:
    """Observed metrics for one workload scenario."""

    scenario: Literal["cold", "warm", "concurrent"]
    samples: int
    readers: int
    rows_per_sample: int
    elapsed_seconds: tuple[float, ...]
    p95_ms: float
    records_per_second: float


@dataclass(frozen=True)
class BudgetResult:
    """Evaluation of one observed value against its declared budget."""

    metric: str
    observed: float
    threshold: float
    comparison: Literal["minimum", "maximum"]
    unit: str
    passed: bool


def generate_dataset(
    destination: Path,
    *,
    row_count: int = DEFAULT_ROW_COUNT,
    batch_size: int = DEFAULT_BATCH_SIZE,
    seed: int = 20260731,
) -> Path:
    """Stream deterministic synthetic medicine assertions to Parquet."""
    if row_count < 1:
        raise ValueError("row_count must be positive")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    temporary.unlink(missing_ok=True)
    writer: pq.ParquetWriter | None = None
    try:
        for start in range(0, row_count, batch_size):
            stop = min(start + batch_size, row_count)
            index = pl.int_range(start, stop, eager=True, dtype=pl.Int64)
            mixed = index * 1_103_515_245 + seed
            frame = pl.DataFrame({"row_id": index}).with_columns(
                pl.format(
                    "med-{}",
                    (mixed % 250_000).cast(pl.String).str.pad_start(12, "0"),
                ).alias("concept_id"),
                pl
                .col("row_id")
                .mod(8)
                .replace_strict({
                    0: "NZL",
                    1: "AUS",
                    2: "USA",
                    3: "CAN",
                    4: "GBR",
                    5: "EU",
                    6: "JPN",
                    7: "CHE",
                })
                .alias("jurisdiction"),
                pl
                .col("row_id")
                .mod(3)
                .replace_strict({0: "regulatory", 1: "funding", 2: "formulary"})
                .alias("status_kind"),
                pl
                .col("row_id")
                .mod(5)
                .replace_strict({
                    0: "active",
                    1: "approved",
                    2: "restricted",
                    3: "inactive",
                    4: "unknown",
                })
                .alias("status_code"),
                (2010 + mixed % 17).cast(pl.Int16).alias("effective_year"),
                (mixed % 10_000 / 10_000).alias("confidence"),
            )
            table = frame.to_arrow()
            if writer is None:
                writer = pq.ParquetWriter(
                    temporary,
                    table.schema,
                    compression="zstd",
                    use_dictionary=True,
                    write_statistics=True,
                )
            writer.write_table(table, row_group_size=batch_size)
        if writer is not None:
            writer.close()
            writer = None
        temporary.replace(destination)
    finally:
        if writer is not None:
            writer.close()
        temporary.unlink(missing_ok=True)
    return destination


def _query_once(dataset: Path) -> float:
    started = time.perf_counter()
    with duckdb.connect(":memory:") as connection:
        connection.execute("SET threads = 1")
        connection.execute(QUERY, [str(dataset)]).fetchall()
    return time.perf_counter() - started


def _p95(values: tuple[float, ...]) -> float:
    ordered = sorted(values)
    rank = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[rank]


def _measurement(
    scenario: Literal["cold", "warm", "concurrent"],
    elapsed: tuple[float, ...],
    *,
    readers: int,
    row_count: int,
) -> Measurement:
    total_rows = row_count * len(elapsed)
    total_seconds = sum(elapsed)
    return Measurement(
        scenario=scenario,
        samples=len(elapsed),
        readers=readers,
        rows_per_sample=row_count,
        elapsed_seconds=elapsed,
        p95_ms=_p95(elapsed) * 1_000,
        records_per_second=total_rows / total_seconds,
    )


def measure_workload(
    dataset: Path,
    *,
    row_count: int,
    readers: int = DEFAULT_READERS,
    warm_runs: int = DEFAULT_WARM_RUNS,
) -> tuple[Measurement, ...]:
    """Measure fresh, reused-connection, and concurrent-reader scenarios."""
    if readers < 1 or warm_runs < 1:
        raise ValueError("readers and warm_runs must be positive")
    cold = _measurement(
        "cold",
        (_query_once(dataset),),
        readers=1,
        row_count=row_count,
    )

    warm_elapsed: list[float] = []
    with duckdb.connect(":memory:") as connection:
        connection.execute("SET threads = 1")
        connection.execute(QUERY, [str(dataset)]).fetchall()
        for _ in range(warm_runs):
            started = time.perf_counter()
            connection.execute(QUERY, [str(dataset)]).fetchall()
            warm_elapsed.append(time.perf_counter() - started)
    warm = _measurement(
        "warm",
        tuple(warm_elapsed),
        readers=1,
        row_count=row_count,
    )

    wall_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=readers) as executor:
        futures = [
            executor.submit(_query_once, dataset) for _ in range(readers)
        ]
        reader_elapsed = tuple(future.result() for future in futures)
    wall_elapsed = time.perf_counter() - wall_started
    concurrent = Measurement(
        scenario="concurrent",
        samples=readers,
        readers=readers,
        rows_per_sample=row_count,
        elapsed_seconds=reader_elapsed,
        p95_ms=_p95(reader_elapsed) * 1_000,
        records_per_second=(row_count * readers) / wall_elapsed,
    )
    return cold, warm, concurrent


def load_budgets(path: Path) -> dict[str, Any]:
    """Load the declared quality budget contract."""
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("quality budgets must be a JSON object")
    return cast("dict[str, Any]", payload)


def evaluate_budgets(
    measurements: tuple[Measurement, ...],
    budgets: dict[str, Any],
    *,
    cpu_seconds: float,
    allocation_peak_mib: float,
    process_peak_memory_mib: float | None = None,
) -> tuple[BudgetResult, ...]:
    """Evaluate representative observations against declared budgets."""
    latency = float(budgets["latency"]["p95_ms"]["maximum"])
    concurrent_latency = float(
        budgets["latency"].get("concurrent_p95_ms", {"maximum": latency})[
            "maximum"
        ]
    )
    throughput = float(budgets["throughput"]["records_per_second"]["minimum"])
    cpu = float(budgets["cpu"]["seconds"]["maximum"])
    allocation = float(budgets["allocation"]["peak_mib"]["maximum"])
    results: list[BudgetResult] = []
    for measurement in measurements:
        latency_threshold = (
            concurrent_latency
            if measurement.scenario == "concurrent"
            else latency
        )
        results.extend((
            BudgetResult(
                metric=f"{measurement.scenario}.p95_ms",
                observed=measurement.p95_ms,
                threshold=latency_threshold,
                comparison="maximum",
                unit="milliseconds",
                passed=measurement.p95_ms <= latency_threshold,
            ),
            BudgetResult(
                metric=(f"{measurement.scenario}.records_per_second"),
                observed=measurement.records_per_second,
                threshold=throughput,
                comparison="minimum",
                unit="records_per_second",
                passed=measurement.records_per_second >= throughput,
            ),
        ))
    results.extend((
        BudgetResult(
            metric="process.cpu_seconds",
            observed=cpu_seconds,
            threshold=cpu,
            comparison="maximum",
            unit="cpu_seconds",
            passed=cpu_seconds <= cpu,
        ),
        BudgetResult(
            metric="python.allocation_peak_mib",
            observed=allocation_peak_mib,
            threshold=allocation,
            comparison="maximum",
            unit="mebibytes",
            passed=allocation_peak_mib <= allocation,
        ),
    ))
    if process_peak_memory_mib is not None:
        memory = float(budgets["memory"]["peak_mib"]["maximum"])
        results.append(
            BudgetResult(
                metric="process.peak_memory_mib",
                observed=process_peak_memory_mib,
                threshold=memory,
                comparison="maximum",
                unit="mebibytes",
                passed=process_peak_memory_mib <= memory,
            )
        )
    return tuple(results)


def run_workload(
    output_directory: Path,
    *,
    budgets_path: Path,
    row_count: int = DEFAULT_ROW_COUNT,
    batch_size: int = DEFAULT_BATCH_SIZE,
    seed: int = 20260731,
    readers: int = DEFAULT_READERS,
    warm_runs: int = DEFAULT_WARM_RUNS,
    require_process_memory: bool = False,
) -> dict[str, Any]:
    """Generate, measure, evaluate, and persist a machine-readable receipt."""
    output_directory.mkdir(parents=True, exist_ok=True)
    dataset = output_directory / "synthetic-medicines.parquet"
    receipt_path = output_directory / "performance-receipt.json"
    cpu_started = time.process_time()
    tracemalloc.start()
    generate_dataset(
        dataset,
        row_count=row_count,
        batch_size=batch_size,
        seed=seed,
    )
    measurements = measure_workload(
        dataset,
        row_count=row_count,
        readers=readers,
        warm_runs=warm_runs,
    )
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    cpu_seconds = time.process_time() - cpu_started
    process_peak_memory_mib = _process_peak_memory_mib()
    budgets = load_budgets(budgets_path)
    evaluations = evaluate_budgets(
        measurements,
        budgets,
        cpu_seconds=cpu_seconds,
        allocation_peak_mib=peak_bytes / MEBIBYTE,
        process_peak_memory_mib=process_peak_memory_mib,
    )
    dataset_digest = sha256(dataset.read_bytes()).hexdigest()
    receipt: dict[str, Any] = {
        "schema_version": "1.0.0",
        "evidence_class": "synthetic",
        "workload": {
            "row_count": row_count,
            "batch_size": batch_size,
            "seed": seed,
            "readers": readers,
            "warm_runs": warm_runs,
            "dataset_sha256": dataset_digest,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor_count": os.cpu_count(),
            "duckdb": duckdb.__version__,
            "polars": pl.__version__,
        },
        "measurements": [asdict(item) for item in measurements],
        "resources": {
            "cpu_seconds": cpu_seconds,
            "python_allocation_peak_mib": peak_bytes / MEBIBYTE,
            "process_peak_memory_mib": process_peak_memory_mib,
        },
        "budget_source": str(budgets_path),
        "budget_results": [asdict(item) for item in evaluations],
        "passed": all(item.passed for item in evaluations)
        and (process_peak_memory_mib is not None or not require_process_memory),
    }
    canonical = orjson.dumps(
        receipt,
        option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
    )
    receipt_path.write_bytes(canonical + b"\n")
    return cast("dict[str, Any]", orjson.loads(canonical))
