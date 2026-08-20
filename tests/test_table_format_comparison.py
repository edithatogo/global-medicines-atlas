from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

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
