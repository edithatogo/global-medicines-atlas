"""Prerequisite gates for object versioning and high-update formats."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from global_medicines_atlas.experiment_prerequisites import (
    ExperimentPrerequisiteReceipt,
)

ROOT = Path(__file__).resolve().parents[1]
OBJECT_VERSIONING = (
    ROOT / "quality/qualifications/object-versioning-prerequisite.json"
)
DELTA_HUDI = ROOT / "quality/qualifications/delta-hudi-prerequisite.json"
HUDI_SCRIPT = ROOT / "scripts/run_hudi_experiment.py"


def _load_hudi_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "run_hudi_experiment", HUDI_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
@pytest.mark.parametrize("path", [OBJECT_VERSIONING, DELTA_HUDI])
def test_committed_prerequisite_receipts_fail_closed(path: Path) -> None:
    receipt = ExperimentPrerequisiteReceipt.model_validate_json(
        path.read_bytes()
    )

    assert receipt.eligible is False
    assert receipt.outcome == "not_run_prerequisite_unmet"
    assert receipt.credentials_created is False
    assert receipt.production_deployment_claimed is False
    assert any(not check.satisfied for check in receipt.checks)


@pytest.mark.unit
def test_satisfied_check_requires_evidence() -> None:
    payload = json.loads(OBJECT_VERSIONING.read_text(encoding="utf-8"))
    payload["checks"][0]["satisfied"] = True

    with pytest.raises(ValidationError, match="requires evidence"):
        ExperimentPrerequisiteReceipt.model_validate(payload)


@pytest.mark.unit
def test_receipt_rejects_false_eligibility_or_outcome() -> None:
    payload = json.loads(DELTA_HUDI.read_text(encoding="utf-8"))
    payload["eligible"] = True
    with pytest.raises(ValidationError, match="complete check state"):
        ExperimentPrerequisiteReceipt.model_validate(payload)

    payload = json.loads(DELTA_HUDI.read_text(encoding="utf-8"))
    payload["outcome"] = "eligible"
    with pytest.raises(ValidationError, match="prerequisite eligibility"):
        ExperimentPrerequisiteReceipt.model_validate(payload)


@pytest.mark.unit
def test_hudi_failure_receipt_is_preserved_and_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _load_hudi_script()

    def fail(_directory: Path) -> tuple[list[dict[str, object]], str]:
        raise RuntimeError("Python runtime unsupported by the preview")

    output = tmp_path / "hudi.json"
    monkeypatch.setattr(script, "_run_hudi", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_hudi_experiment.py", "--output", str(output)],
    )

    assert script.main() == 1
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["outcome"] == "failed"
    assert receipt["correctness_verified"] is False
    assert receipt["error"]["message"] == (
        "Python runtime unsupported by the preview"
    )


@pytest.mark.unit
def test_hudi_synthetic_workload_survives_unusable_python_serializer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Frame:
        def __init__(self, spark: Any, rows: list[dict[str, Any]]) -> None:
            self.spark = spark
            self.rows = rows
            self.write = self

        def format(self, name: str) -> Any:
            if name != "hudi":
                raise ValueError("expected Hudi format")
            return self

        def options(self, **options: str) -> Any:
            if (
                options.get("hoodie.datasource.write.recordkey.field")
                != "native_id"
            ):
                raise ValueError("expected native record key")
            return self

        def mode(self, mode: str) -> Any:
            self.write_mode = mode
            return self

        def option(self, name: str, value: str) -> Any:
            if (name, value) != ("hoodie.datasource.write.operation", "upsert"):
                raise ValueError("expected upsert")
            return self

        def save(self, _target: str) -> None:
            if self.write_mode == "overwrite":
                self.spark.rows.clear()
            for row in self.rows:
                if row.get("_hoodie_is_deleted"):
                    self.spark.rows.pop(row["native_id"], None)
                else:
                    self.spark.rows[row["native_id"]] = row

        def load(self, _target: str) -> Any:
            self.rows = list(self.spark.rows.values())
            return self

        def select(self, *fields: str) -> Any:
            self.rows = [
                {field: row[field] for field in fields} for row in self.rows
            ]
            return self

        def collect(self) -> list[Any]:
            return [
                SimpleNamespace(asDict=lambda row=row: row) for row in self.rows
            ]

    class Spark:
        def __init__(self) -> None:
            self.rows: dict[str, dict[str, Any]] = {}
            self.read = Frame(self, [])

        def __getattr__(self, name: str) -> Any:
            if name == "createDataFrame":
                raise RuntimeError(
                    "Python function serialization is unavailable"
                )
            raise AttributeError(name)

        def sql(self, query: str) -> Frame:
            with sqlite3.connect(":memory:") as connection:
                cursor = connection.execute(query)
                fields = [field[0] for field in cursor.description]
                rows = [dict(zip(fields, row, strict=True)) for row in cursor]
            return Frame(self, rows)

        def stop(self) -> None:
            pass

    spark = Spark()
    pyspark = ModuleType("pyspark")
    pyspark.__version__ = "3.5.6-test"  # type: ignore[attr-defined]
    sql = ModuleType("pyspark.sql")
    sql.SparkSession = SimpleNamespace(  # type: ignore[attr-defined]
        builder=SimpleNamespace(
            appName=lambda _name: SimpleNamespace(getOrCreate=lambda: spark)
        )
    )
    monkeypatch.setitem(sys.modules, "pyspark", pyspark)
    monkeypatch.setitem(sys.modules, "pyspark.sql", sql)

    records, version = _load_hudi_script()._run_hudi(tmp_path)

    assert records == [
        {"native_id": "A-001", "value": 11},
        {"native_id": "C-003", "value": 3},
    ]
    assert version == "3.5.6-test"
