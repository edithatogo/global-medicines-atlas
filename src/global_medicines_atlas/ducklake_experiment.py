"""DuckLake comparison using the governed datahouse fixture."""

from __future__ import annotations

import hashlib
import importlib.metadata
import time
from pathlib import Path
from typing import Literal, cast

import duckdb
from pydantic import Field

from .models import FrozenModel

DUCKLAKE_SPEC_VERSION = "1.0"


class DuckLakeComparisonReceipt(FrozenModel):
    schema_id: Literal["global-medicines-atlas.ducklake-comparison"]
    schema_version: Literal[1]
    ducklake_spec_version: Literal["1.0"]
    duckdb_version: str = Field(min_length=1)
    extension_version: str = Field(min_length=1)
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_rows: int = Field(ge=0)
    baseline_sum: int
    ducklake_rows: int = Field(ge=0)
    ducklake_sum: int
    updated_sum: int
    historical_sum: int
    snapshot_count: int = Field(ge=1)
    reattach_verified: bool
    direct_parquet_or_source_fallback_verified: bool
    elapsed_ms: float = Field(ge=0)
    correctness_verified: bool
    optional_for_core: Literal[True] = True
    catalogue_authoritative: Literal[False] = False
    production_deployment_claimed: Literal[False] = False


def safe_sql_path(path: Path) -> str:
    resolved = path.resolve().as_posix()
    if "'" in resolved:
        raise ValueError("experiment path cannot contain a quote")
    return resolved


def _row(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: tuple[object, ...] = (),
) -> tuple[object, ...]:
    row = connection.execute(query, parameters).fetchone()
    if row is None:
        raise RuntimeError("DuckLake experiment query returned no row")
    return cast("tuple[object, ...]", row)


def _pair(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: tuple[object, ...] = (),
) -> tuple[int, int]:
    row = _row(connection, query, parameters)
    return int(cast("int", row[0])), int(cast("int", row[1]))


def run_ducklake_comparison(  # ruff: ignore[too-many-locals]
    *, fixture_path: Path, workspace: Path
) -> DuckLakeComparisonReceipt:
    """Compare DuckLake snapshots with direct DuckDB source reads."""

    started = time.perf_counter()
    workspace.mkdir(parents=True, exist_ok=True)
    fixture_sha256 = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    fixture = safe_sql_path(fixture_path)
    catalogue = safe_sql_path(workspace / "experiment.ducklake")
    connection = duckdb.connect()
    try:
        connection.execute("INSTALL ducklake")
        connection.execute("LOAD ducklake")
        extension_version = str(
            _row(
                connection,
                "SELECT extension_version FROM duckdb_extensions() "
                "WHERE extension_name = 'ducklake' AND loaded",
            )[0]
        )
        baseline_rows, baseline_sum = _pair(
            connection,
            "SELECT count(*), sum(value) FROM read_json_auto(?)",
            (fixture,),
        )
        connection.execute(f"ATTACH 'ducklake:{catalogue}' AS lake")
        connection.execute(
            "CREATE TABLE lake.records AS SELECT * FROM read_json_auto(?)",
            (fixture,),
        )
        ducklake_rows, ducklake_sum = _pair(
            connection, "SELECT count(*), sum(value) FROM lake.records"
        )
        historical_version = int(
            cast(
                "int",
                _row(
                    connection,
                    "SELECT max(snapshot_id) FROM lake.snapshots()",
                )[0],
            )
        )
        connection.execute(
            "UPDATE lake.records SET value = value + 10 "
            "WHERE native_id = 'A-001'"
        )
        updated_sum = int(
            cast(
                "int",
                _row(connection, "SELECT sum(value) FROM lake.records")[0],
            )
        )
        historical_sum = int(
            cast(
                "int",
                _row(
                    connection,
                    "SELECT sum(value) FROM lake.records AT (VERSION => ?)",
                    (historical_version,),
                )[0],
            )
        )
        snapshot_count = int(
            cast(
                "int",
                _row(connection, "SELECT count(*) FROM lake.snapshots()")[0],
            )
        )
        connection.execute("DETACH lake")
        connection.execute(f"ATTACH 'ducklake:{catalogue}' AS lake")
        reattached_sum = int(
            cast(
                "int",
                _row(connection, "SELECT sum(value) FROM lake.records")[0],
            )
        )
        connection.execute("DETACH lake")
        fallback_rows, fallback_sum = _pair(
            connection,
            "SELECT count(*), sum(value) FROM read_json_auto(?)",
            (fixture,),
        )
    finally:
        connection.close()
    correctness = (
        baseline_rows == ducklake_rows == fallback_rows
        and baseline_sum == ducklake_sum == historical_sum
        and updated_sum == reattached_sum
        and baseline_sum == fallback_sum
    )
    return DuckLakeComparisonReceipt(
        schema_id="global-medicines-atlas.ducklake-comparison",
        schema_version=1,
        ducklake_spec_version=DUCKLAKE_SPEC_VERSION,
        duckdb_version=importlib.metadata.version("duckdb"),
        extension_version=extension_version,
        fixture_sha256=fixture_sha256,
        baseline_rows=baseline_rows,
        baseline_sum=baseline_sum,
        ducklake_rows=ducklake_rows,
        ducklake_sum=ducklake_sum,
        updated_sum=updated_sum,
        historical_sum=historical_sum,
        snapshot_count=snapshot_count,
        reattach_verified=updated_sum == reattached_sum,
        direct_parquet_or_source_fallback_verified=(
            baseline_rows == fallback_rows and baseline_sum == fallback_sum
        ),
        elapsed_ms=(time.perf_counter() - started) * 1000,
        correctness_verified=correctness,
    )
