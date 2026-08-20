"""Run a standalone Apache Hudi workload and preserve failures as evidence."""

from __future__ import annotations

import argparse
import importlib
import json
import platform
import tempfile
import time
from pathlib import Path


def _require_expected(records: list[dict[str, object]]) -> None:
    expected = [
        {"native_id": "A-001", "value": 11},
        {"native_id": "C-003", "value": 3},
    ]
    if records != expected:
        raise ValueError(
            "final records do not match the common workload oracle"
        )


def _run_hudi(directory: Path) -> tuple[list[dict[str, object]], str]:
    pyspark = importlib.import_module("pyspark")
    spark_session = importlib.import_module("pyspark.sql").SparkSession
    spark = spark_session.builder.appName("gma-synthetic-hudi").getOrCreate()
    target = directory / "hudi"
    options = {
        "hoodie.table.name": "gma_synthetic",
        "hoodie.datasource.write.recordkey.field": "native_id",
        "hoodie.datasource.write.precombine.field": "value",
        "hoodie.datasource.write.table.type": "COPY_ON_WRITE",
    }
    try:
        spark.createDataFrame([
            {"native_id": "A-001", "value": 1},
            {"native_id": "B-002", "value": 2},
        ]).write.format("hudi").options(**options).mode("overwrite").save(
            str(target)
        )
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
        records = sorted(
            (
                row.asDict()
                for row in spark.read
                .format("hudi")
                .load(str(target))
                .select("native_id", "value")
                .collect()
            ),
            key=lambda row: str(row["native_id"]),
        )
        _require_expected(records)
        return records, str(pyspark.__version__)
    finally:
        spark.stop()


def execute(directory: Path) -> dict[str, object]:
    started = time.monotonic_ns()
    records: list[dict[str, object]] = []
    error: dict[str, str] | None = None
    outcome = "passed"
    pyspark_version = "not_installed"
    try:
        records, pyspark_version = _run_hudi(directory)
    except Exception as exception:
        outcome = "failed"
        error = {
            "type": type(exception).__name__,
            "message": str(exception)[:1000],
        }
    return {
        "schema_version": "1.0",
        "engine": "hudi",
        "outcome": outcome,
        "correctness_verified": outcome == "passed",
        "historical_recovery_verified": False,
        "conflict_behavior": "not_exercised_single_writer_workload",
        "compaction": "not_exercised_bounded_workload",
        "portability": (
            "engine_neutral_records_and_oracle; engine_specific_physical_readback"
        ),
        "final_records": records,
        "elapsed_seconds": round(
            (time.monotonic_ns() - started) / 1_000_000_000, 6
        ),
        "runtime": {
            "python": platform.python_version(),
            "dependency": pyspark_version,
            "hudi_bundle": "org.apache.hudi:hudi-spark3.5-bundle_2.12:1.2.0",
        },
        "workload": {
            "initial_rows": 2,
            "updates": 1,
            "deletes": 1,
            "appends": 1,
            "expected_final_rows": 2,
        },
        "error": error,
        "synthetic_only": True,
        "governed_input_reconstruction": "not_applicable_synthetic_workload",
        "core_dependency_added": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gma-hudi-") as temporary:
        receipt = execute(Path(temporary))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
