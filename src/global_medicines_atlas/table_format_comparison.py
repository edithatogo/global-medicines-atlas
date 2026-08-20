# pyright: reportUnknownMemberType=false
"""Bounded, synthetic comparison of optional high-update table formats."""

from __future__ import annotations

import importlib
import importlib.metadata
import platform
import resource
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

INITIAL_RECORDS = (
    {"native_id": "A-001", "value": 1},
    {"native_id": "B-002", "value": 2},
)
EXPECTED_FINAL = (
    {"native_id": "A-001", "value": 11},
    {"native_id": "C-003", "value": 3},
)


def workload_demand_receipt() -> dict[str, Any]:
    """Record only demand established by governed, repository-owned evidence."""
    return {
        "schema_version": "1.0",
        "evidence_scope": "governed_repository_receipts_as_of_2026-08-21",
        "inputs": [
            "quality/qualifications/delta-hudi-prerequisite.json",
            "quality/qualifications/datahouse-experiment-matrix.json",
            "conductor/archive/datahouse_interoperability_experiments_20260820/evidence.jsonl",
        ],
        "observed_requirements": {
            "source_record_updates": None,
            "source_record_deletes": None,
            "multi_writer_concurrency": None,
            "transaction_gap_in_baseline": None,
        },
        "high_update_format_demand": "not_evidenced",
        "interpretation": (
            "Absence of governed measurements is not evidence of zero source events; "
            "synthetic benchmark events must not be counted as Atlas demand."
        ),
    }


def _normalized(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda record: str(record["native_id"]))


def _baseline(directory: Path) -> tuple[list[dict[str, Any]], bool]:
    target = directory / "table.parquet"
    pq.write_table(pa.Table.from_pylist(list(INITIAL_RECORDS)), target)
    historical = pq.read_table(target).to_pylist() == list(INITIAL_RECORDS)
    pq.write_table(pa.Table.from_pylist(list(EXPECTED_FINAL)), target)
    return pq.read_table(target).to_pylist(), historical


def _delta(directory: Path) -> tuple[list[dict[str, Any]], bool]:
    deltalake = importlib.import_module("deltalake")
    delta_table = deltalake.DeltaTable
    write_deltalake = deltalake.write_deltalake

    target = directory / "delta"
    write_deltalake(target, pa.Table.from_pylist(list(INITIAL_RECORDS)))
    table = delta_table(target)
    table.update(
        predicate="native_id = 'A-001'",
        updates={"value": "value + 10"},
    )
    table.delete(predicate="native_id = 'B-002'")
    write_deltalake(
        target,
        pa.Table.from_pylist([{"native_id": "C-003", "value": 3}]),
        mode="append",
    )
    current = delta_table(target).to_pyarrow_table().to_pylist()
    historical_table = (
        delta_table(target, version=0).to_pyarrow_table().to_pylist()
    )
    return current, _normalized(historical_table) == _normalized(
        list(INITIAL_RECORDS)
    )


def _hudi(directory: Path) -> tuple[list[dict[str, Any]], bool]:
    spark_session = importlib.import_module("pyspark.sql").SparkSession

    target = directory / "hudi"
    spark = spark_session.builder.appName("gma-synthetic-hudi").getOrCreate()
    options = {
        "hoodie.table.name": "gma_synthetic",
        "hoodie.datasource.write.recordkey.field": "native_id",
        "hoodie.datasource.write.precombine.field": "value",
        "hoodie.datasource.write.table.type": "COPY_ON_WRITE",
    }
    try:
        spark.createDataFrame(list(INITIAL_RECORDS)).write.format(
            "hudi"
        ).options(**options).mode("overwrite").save(str(target))
        changes = [
            {"native_id": "A-001", "value": 11, "_hoodie_is_deleted": False},
            {"native_id": "B-002", "value": 2, "_hoodie_is_deleted": True},
            {"native_id": "C-003", "value": 3, "_hoodie_is_deleted": False},
        ]
        spark.createDataFrame(changes).write.format("hudi").options(
            **options
        ).option("hoodie.datasource.write.operation", "upsert").mode(
            "append"
        ).save(str(target))
        current = [
            row.asDict()
            for row in spark.read
            .format("hudi")
            .load(str(target))
            .select("native_id", "value")
            .collect()
        ]
        return current, False
    finally:
        spark.stop()


_RUNNERS: dict[str, Callable[[Path], tuple[list[dict[str, Any]], bool]]] = {
    "iceberg_ready_parquet": _baseline,
    "delta": _delta,
    "hudi": _hudi,
}


def _require_expected_records(records: list[dict[str, Any]]) -> None:
    if _normalized(records) != _normalized(list(EXPECTED_FINAL)):
        raise ValueError(
            "final records do not match the common workload oracle"
        )


def run_table_format(engine: str, directory: Path) -> dict[str, Any]:
    """Run one engine and return a comparable success or failure receipt."""
    if engine not in _RUNNERS:
        raise ValueError(f"unknown table-format engine: {engine}")
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic_ns()
    before_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    outcome = "passed"
    error: dict[str, str] | None = None
    final_records: list[dict[str, Any]] = []
    historical_recovery = False
    try:
        final_records, historical_recovery = _RUNNERS[engine](directory)
        _require_expected_records(final_records)
    except Exception as exception:  # experiment failures are evidence
        outcome = "failed"
        error = {
            "type": type(exception).__name__,
            "message": str(exception)[:1000],
        }
    completed = time.monotonic_ns()
    after_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    distributions = {"delta": "deltalake", "hudi": "pyspark"}
    dependency = distributions.get(engine)
    dependency_version = None
    if dependency:
        try:
            dependency_version = importlib.metadata.version(dependency)
        except importlib.metadata.PackageNotFoundError:
            dependency_version = "not_installed"
    return {
        "schema_version": "1.0",
        "engine": engine,
        "outcome": outcome,
        "workload": {
            "initial_rows": len(INITIAL_RECORDS),
            "updates": 1,
            "deletes": 1,
            "appends": 1,
            "expected_final_rows": len(EXPECTED_FINAL),
        },
        "correctness_verified": outcome == "passed",
        "historical_recovery_verified": historical_recovery,
        "conflict_behavior": "not_exercised_single_writer_workload",
        "compaction": "not_exercised_bounded_workload",
        "portability": (
            "engine_neutral_records_and_oracle; engine_specific_physical_readback"
        ),
        "final_records": _normalized(final_records),
        "elapsed_seconds": round((completed - started) / 1_000_000_000, 6),
        "peak_rss_delta_native_units": max(0, after_memory - before_memory),
        "runtime": {
            "python": platform.python_version(),
            "dependency": dependency_version,
        },
        "error": error,
        "synthetic_only": True,
        "governed_input_reconstruction": "not_applicable_synthetic_workload",
        "core_dependency_added": False,
    }
