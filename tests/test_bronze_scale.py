"""Bronze scale fixtures, budgets, and bottleneck ranking."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from scripts.benchmark_bronze_scale import main as bronze_scale_cli

from global_medicines_atlas.bronze_scale import (
    FIXTURE_RELATIVE,
    RUST_MIN_SPEEDUP,
    RUST_MIN_WALL_SHARE,
    StageMeasurement,
    evaluate_bronze_scale_budgets,
    generate_synthetic_artefacts,
    load_bronze_scale_budgets,
    load_bronze_scale_fixture,
    run_bronze_scale,
    rust_rewrite_justified,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_fixture_is_deterministic_and_synthetic() -> None:
    fixture = load_bronze_scale_fixture(ROOT / FIXTURE_RELATIVE)
    first = generate_synthetic_artefacts(fixture, profile="ci")
    second = generate_synthetic_artefacts(fixture, profile="ci")

    assert fixture["evidence_class"] == "synthetic"
    assert fixture["profiles"]["ci"]["source_count"] == 8
    assert fixture["catalog_source_count_observed"] == 96
    assert first.json_payload == second.json_payload
    assert first.zip_payload == second.zip_payload
    assert first.json_payload != first.csv_payload
    assert first.zip_payload.startswith(b"PK")


@pytest.mark.unit
def test_budgets_validate_against_schema() -> None:
    schema = json.loads(
        (ROOT / "quality/bronze-scale-budgets.schema.json").read_text(
            encoding="utf-8"
        )
    )
    budgets = load_bronze_scale_budgets(
        ROOT / "quality/bronze-scale-budgets.json"
    )
    jsonschema.validate(budgets, schema)
    assert budgets["profile"] == "ci"
    assert budgets["rust_rewrite"]["min_wall_share"] == RUST_MIN_WALL_SHARE
    assert budgets["rust_rewrite"]["min_speedup"] == RUST_MIN_SPEEDUP


@pytest.mark.unit
def test_rust_rewrite_requires_hot_pure_python_path() -> None:
    hot_python = StageMeasurement(
        name="parsing",
        elapsed_seconds=4.0,
        wall_share=0.5,
        implementation="pure_python",
        accelerator=None,
        bytes_processed=1024,
    )
    openssl = StageMeasurement(
        name="hashing",
        elapsed_seconds=4.0,
        wall_share=0.5,
        implementation="openssl_c",
        accelerator="hashlib.sha256",
        bytes_processed=1024,
    )
    small = StageMeasurement(
        name="parsing",
        elapsed_seconds=0.01,
        wall_share=0.01,
        implementation="pure_python",
        accelerator=None,
        bytes_processed=1024,
    )
    assert rust_rewrite_justified(hot_python, speedup=3.0)
    assert not rust_rewrite_justified(openssl, speedup=10.0)
    assert not rust_rewrite_justified(small, speedup=10.0)
    assert not rust_rewrite_justified(hot_python, speedup=1.1)


@pytest.mark.unit
def test_budget_evaluation_fails_closed_on_slow_pipeline() -> None:
    budgets = load_bronze_scale_budgets(
        ROOT / "quality/bronze-scale-budgets.json"
    )
    results = evaluate_bronze_scale_budgets(
        {
            "pipeline_seconds": 99.0,
            "hashing_mib_per_second": 1.0,
            "archive_inspect_seconds": 0.01,
            "parquet_seconds": 0.01,
            "receipt_validation_seconds": 0.01,
            "lineage_seconds": 0.01,
            "catalogue_ops_per_second": 1.0,
        },
        budgets,
    )
    names = {item.metric: item.passed for item in results}
    assert names["pipeline_seconds"] is False
    assert names["hashing_mib_per_second"] is False
    assert names["catalogue_ops_per_second"] is False


@pytest.mark.integration
@pytest.mark.timeout(25)
def test_ci_profile_ranks_bottlenecks_and_meets_budgets(
    tmp_path: Path,
) -> None:
    receipt = run_bronze_scale(
        output_directory=tmp_path,
        fixture_path=ROOT / FIXTURE_RELATIVE,
        budgets_path=ROOT / "quality/bronze-scale-budgets.json",
        profile="ci",
    )
    persisted = json.loads(
        (tmp_path / "bronze-scale-receipt.json").read_text(encoding="utf-8")
    )
    assert persisted == receipt
    stages = {item["name"] for item in receipt["stages"]}
    assert stages >= {
        "ingestion",
        "hashing",
        "compression",
        "parquet_generation",
        "receipt_validation",
        "lineage_generation",
        "catalogue_operations",
        "archive_inspection",
        "parsing",
    }
    assert receipt["bottleneck"]["name"] in stages
    assert receipt["python_remains_orchestration"] is True
    assert receipt["rust_rewrite_justified"] is False
    assert receipt["passed"] is True
    assert receipt["workload"]["source_count"] == 8
    capabilities = {item["capability"] for item in receipt["rust_candidates"]}
    assert capabilities == {
        "streaming_hashing",
        "archive_inspection",
        "parsing",
        "compression_decompression",
        "high_volume_validation",
    }
    assert all(
        item["justified"] is False for item in receipt["rust_candidates"]
    )


@pytest.mark.unit
def test_fixture_and_budget_loaders_reject_arrays(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text("[]", encoding="utf-8")
    budgets = tmp_path / "budgets.json"
    budgets.write_text("[]", encoding="utf-8")
    with pytest.raises(TypeError, match="must be a JSON object"):
        load_bronze_scale_fixture(fixture)
    with pytest.raises(TypeError, match="must be a JSON object"):
        load_bronze_scale_budgets(budgets)


@pytest.mark.unit
def test_unknown_profile_and_undersized_payloads_fail() -> None:
    fixture = load_bronze_scale_fixture(ROOT / FIXTURE_RELATIVE)
    with pytest.raises(KeyError, match="unknown bronze scale profile"):
        generate_synthetic_artefacts(fixture, profile="missing")
    malformed: dict[str, Any] = {"seed": 1, "profiles": {"ci": []}}
    with pytest.raises(TypeError, match="profile must be a JSON object"):
        generate_synthetic_artefacts(malformed, profile="ci")
    tiny: dict[str, Any] = {
        "seed": 1,
        "profiles": {
            "ci": {
                "json_bytes": 4,
                "csv_bytes": 65536,
                "zip_members": 1,
                "zip_member_bytes": 16,
            }
        },
    }
    with pytest.raises(ValueError, match="json_bytes"):
        generate_synthetic_artefacts(tiny, profile="ci")
    tiny_csv: dict[str, Any] = {
        "seed": 1,
        "profiles": {
            "ci": {
                "json_bytes": 64,
                "csv_bytes": 8,
                "zip_members": 1,
                "zip_member_bytes": 16,
            }
        },
    }
    with pytest.raises(ValueError, match="csv_bytes"):
        generate_synthetic_artefacts(tiny_csv, profile="ci")


@pytest.mark.unit
def test_benchmark_cli_reports_ci_receipt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_bronze_scale.py",
            "--output",
            str(tmp_path),
            "--profile",
            "ci",
        ],
    )
    bronze_scale_cli()
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] == "ci"
    assert payload["passed"] is True
    assert payload["python_remains_orchestration"] is True
