"""Focused tests for the representative-scale performance workload."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from global_medicines_atlas.performance_workload import (
    BudgetResult,
    Measurement,
    evaluate_budgets,
    generate_dataset,
    load_budgets,
    measure_workload,
    run_workload,
)


@pytest.mark.unit
def test_generation_is_batched_and_deterministic(tmp_path: Path) -> None:
    first = generate_dataset(
        tmp_path / "first.parquet",
        row_count=257,
        batch_size=31,
        seed=7,
    )
    second = generate_dataset(
        tmp_path / "second.parquet",
        row_count=257,
        batch_size=64,
        seed=7,
    )

    first_frame = pl.read_parquet(first)
    second_frame = pl.read_parquet(second)
    assert first_frame.shape == (257, 7)
    assert first_frame.equals(second_frame)
    assert first_frame.get_column("jurisdiction").n_unique() == 8


@pytest.mark.unit
def test_budget_evaluation_covers_every_declared_measure() -> None:
    measurement = Measurement(
        scenario="warm",
        samples=2,
        readers=1,
        rows_per_sample=100,
        elapsed_seconds=(0.01, 0.02),
        p95_ms=20,
        records_per_second=10_001,
    )
    budgets = {
        "latency": {
            "p95_ms": {"maximum": 250},
            "concurrent_p95_ms": {"maximum": 500},
        },
        "throughput": {"records_per_second": {"minimum": 10_000}},
        "cpu": {"seconds": {"maximum": 60}},
        "allocation": {"peak_mib": {"maximum": 2048}},
    }

    results = evaluate_budgets(
        (measurement,),
        budgets,
        cpu_seconds=1,
        allocation_peak_mib=2,
    )

    assert len(results) == 4
    assert all(isinstance(item, BudgetResult) for item in results)
    assert all(item.passed for item in results)


@pytest.mark.integration
def test_runner_writes_complete_machine_readable_receipt(
    tmp_path: Path,
) -> None:
    output = tmp_path / "run"
    budgets = Path("quality/budgets.json")
    receipt = run_workload(
        output,
        budgets_path=budgets,
        row_count=1_000,
        batch_size=137,
        seed=42,
        readers=2,
        warm_runs=2,
    )

    persisted = json.loads(
        (output / "performance-receipt.json").read_text(encoding="utf-8")
    )
    assert persisted == receipt
    assert (output / "synthetic-medicines.parquet").is_file()
    assert receipt["workload"]["row_count"] == 1_000
    assert receipt["workload"]["seed"] == 42
    assert {item["scenario"] for item in receipt["measurements"]} == {
        "cold",
        "warm",
        "concurrent",
    }
    measurements = {item["scenario"]: item for item in receipt["measurements"]}
    assert measurements["warm"]["samples"] == 2
    assert measurements["concurrent"]["samples"] == 20
    assert len(receipt["workload"]["dataset_sha256"]) == 64
    assert "process_peak_memory_mib" in receipt["resources"]
    process_peak_memory = receipt["resources"]["process_peak_memory_mib"]
    assert process_peak_memory is None or process_peak_memory > 0
    expected_budget_results = 8 + int(process_peak_memory is not None)
    assert len(receipt["budget_results"]) == expected_budget_results


@pytest.mark.unit
@pytest.mark.parametrize(
    ("row_count", "batch_size"),
    [(0, 1), (1, 0)],
)
def test_generation_rejects_non_positive_sizes(
    tmp_path: Path,
    row_count: int,
    batch_size: int,
) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        generate_dataset(
            tmp_path / "invalid.parquet",
            row_count=row_count,
            batch_size=batch_size,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("readers", "warm_runs"),
    [(0, 1), (1, 0)],
)
def test_measurement_rejects_non_positive_run_counts(
    tmp_path: Path,
    readers: int,
    warm_runs: int,
) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        measure_workload(
            tmp_path / "unused.parquet",
            row_count=1,
            readers=readers,
            warm_runs=warm_runs,
        )


@pytest.mark.unit
def test_budget_loader_rejects_non_object(tmp_path: Path) -> None:
    budget_path = tmp_path / "budgets.json"
    budget_path.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="must be a JSON object"):
        load_budgets(budget_path)
