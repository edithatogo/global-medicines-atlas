from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jsonschema
import pyarrow as pa
import pytest

import global_medicines_atlas.table_format_comparison as comparison
from global_medicines_atlas.table_format_comparison import (
    run_table_format,
    workload_demand_receipt,
)


def test_demand_receipt_does_not_convert_missing_measurement_to_zero() -> None:
    receipt = workload_demand_receipt()
    assert receipt["high_update_format_demand"] == "not_evidenced"
    assert all(
        value is None for value in receipt["observed_requirements"].values()
    )
    assert "synthetic benchmark" in receipt["interpretation"]


def test_iceberg_ready_baseline_runs_common_workload(tmp_path: Path) -> None:
    receipt = run_table_format("iceberg_ready_parquet", tmp_path)
    assert receipt["outcome"] == "passed"
    assert receipt["correctness_verified"] is True
    assert receipt["historical_recovery_verified"] is True
    assert receipt["workload"] == {
        "initial_rows": 2,
        "updates": 1,
        "deletes": 1,
        "appends": 1,
        "expected_final_rows": 2,
    }
    assert receipt["core_dependency_added"] is False
    assert (
        receipt["conflict_behavior"] == "not_exercised_single_writer_workload"
    )
    assert receipt["compaction"] == "not_exercised_bounded_workload"
    assert "engine_neutral" in receipt["portability"]


def test_missing_optional_engine_becomes_failure_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_: Path) -> tuple[list[dict[str, object]], bool]:
        raise ModuleNotFoundError("optional engine unavailable")

    monkeypatch.setitem(
        __import__(
            "global_medicines_atlas.table_format_comparison",
            fromlist=["_RUNNERS"],
        )._RUNNERS,
        "delta",
        unavailable,
    )
    receipt = run_table_format("delta", tmp_path)
    assert receipt["outcome"] == "failed"
    assert receipt["error"]["type"] == "ModuleNotFoundError"
    assert receipt["correctness_verified"] is False


def test_wrong_engine_result_becomes_failure_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        comparison._RUNNERS,  # pyright: ignore[reportPrivateUsage]
        "delta",
        lambda _: ([{"native_id": "wrong", "value": 0}], False),
    )
    receipt = run_table_format("delta", tmp_path)
    assert receipt["outcome"] == "failed"
    assert receipt["error"]["type"] == "ValueError"


def test_delta_runner_executes_update_delete_append_and_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current: list[dict[str, object]] = []
    version_zero: list[dict[str, object]] = []

    class FakeDeltaTable:
        def __init__(self, _: Path, version: int | None = None) -> None:
            self.version = version

        def update(self, **_: object) -> None:
            current[0]["value"] = 11

        def delete(self, **_: object) -> None:
            current[:] = [row for row in current if row["native_id"] != "B-002"]

        def to_pyarrow_table(self) -> pa.Table:
            records = version_zero if self.version == 0 else current
            return pa.Table.from_pylist(records)

    def fake_write(_: Path, table: pa.Table, mode: str | None = None) -> None:
        records = table.to_pylist()
        if mode == "append":
            current.extend(records)
        else:
            current[:] = records
            version_zero[:] = [dict(record) for record in records]

    fake_module = SimpleNamespace(
        DeltaTable=FakeDeltaTable, write_deltalake=fake_write
    )
    original_import = comparison.importlib.import_module

    def fake_import(name: str) -> Any:
        return fake_module if name == "deltalake" else original_import(name)

    monkeypatch.setattr(
        comparison.importlib,
        "import_module",
        fake_import,
    )
    receipt = run_table_format("delta", tmp_path)
    assert receipt["outcome"] == "passed"
    assert receipt["historical_recovery_verified"] is True
    assert receipt["final_records"] == [
        {"native_id": "A-001", "value": 11},
        {"native_id": "C-003", "value": 3},
    ]


def test_unknown_engine_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown table-format"):
        run_table_format("unknown", tmp_path)


def test_decision_packet_schema_and_evidence_digests() -> None:
    root = Path(__file__).resolve().parents[1]
    packet = json.loads(
        (
            root
            / "quality/qualifications/free-tier-datahouse-decision-packet.json"
        ).read_text()
    )
    schema = json.loads(
        (root / "quality/datahouse-decision-packet.schema.json").read_text()
    )
    jsonschema.validate(packet, schema)
    for evidence in packet["evidence"]:
        assert (
            hashlib.sha256((root / evidence["path"]).read_bytes()).hexdigest()
            == evidence["sha256"]
        )
    assert packet["maintainer_gate"]["promotion_claimed"] is False
    assert packet["maintainer_gate"]["production_durability_claimed"] is False
