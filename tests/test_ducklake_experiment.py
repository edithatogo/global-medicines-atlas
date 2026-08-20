"""DuckLake comparison contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from global_medicines_atlas.ducklake_experiment import (
    DUCKLAKE_SPEC_VERSION,
    run_ducklake_comparison,
    safe_sql_path,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/datahouse/bronze_records.json"


@pytest.mark.unit
def test_ducklake_specification_is_pinned() -> None:
    assert DUCKLAKE_SPEC_VERSION == "1.0"


@pytest.mark.unit
def test_sql_path_rejects_quote(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="quote"):
        safe_sql_path(tmp_path / "hostile'path")


@pytest.mark.integration
def test_actual_ducklake_comparison(tmp_path: Path) -> None:
    receipt = run_ducklake_comparison(
        fixture_path=FIXTURE,
        workspace=tmp_path,
    )

    assert receipt.correctness_verified is True
    assert receipt.baseline_rows == receipt.ducklake_rows == 2
    assert receipt.baseline_sum == receipt.ducklake_sum == 3
    assert receipt.historical_sum == 3
    assert receipt.updated_sum == 13
    assert receipt.snapshot_count >= 3
    assert receipt.reattach_verified is True
    assert receipt.direct_parquet_or_source_fallback_verified is True
    assert receipt.catalogue_authoritative is False
    assert receipt.production_deployment_claimed is False
