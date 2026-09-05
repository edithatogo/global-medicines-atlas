"""Deterministic benchmark evidence for frontier query/export candidates.

This is deliberately an operation-count benchmark rather than a wall-clock
qualification.  It compares the portable Python fallback with optional
engines without making a dependency, latency, or production-promotion claim.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenModel

BENCHMARK_SCHEMA = "global-medicines-atlas.frontier-benchmark"
Candidate = Literal["python_fallback", "duckdb", "polars", "arrow", "xet_restore"]
_MAX_FIXTURE_ROWS = 10_000


class BenchmarkWorkload(FrozenModel):
    """A content-bound, bounded workload used by every candidate."""

    workload_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,127}$")
    row_count: int = Field(strict=True, gt=0, le=10_000)
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class BenchmarkObservation(FrozenModel):
    """Comparable, timing-independent candidate observations."""

    candidate: Candidate
    status: Literal["measured", "unavailable"]
    rows_scanned: int = Field(strict=True, ge=0)
    rows_returned: int = Field(strict=True, ge=0)
    operations: int = Field(strict=True, ge=0)
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    fallback: Literal["portable_python", "optional_engine", "not_applicable"]
    note: str = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def status_shape(self) -> BenchmarkObservation:
        if self.status == "measured" and self.output_sha256 is None:
            raise ValueError("measured candidate requires output digest")
        if self.status == "unavailable" and self.output_sha256 is not None:
            raise ValueError("unavailable candidate cannot have output digest")
        if self.rows_returned > self.rows_scanned:
            raise ValueError("returned rows exceed scanned rows")
        return self


class FrontierBenchmarkReceipt(FrozenModel):
    """Complete bounded benchmark evidence with a non-promotion disposition."""

    schema_id: Literal["global-medicines-atlas.frontier-benchmark"]
    schema_version: Literal[1]
    workload: BenchmarkWorkload
    observations: tuple[BenchmarkObservation, ...] = Field(min_length=1, max_length=5)
    production_dependency_adopted: Literal[False]
    technology_promotion_claimed: Literal[False]
    disposition: Literal["retain-preview", "defer", "reject"]

    @model_validator(mode="after")
    def validates_parity(self) -> FrontierBenchmarkReceipt:
        measured = [item for item in self.observations if item.status == "measured"]
        for item in measured:
            if item.output_sha256 != self.workload.output_sha256:
                raise ValueError("candidate output differs from portable result")
        if not any(item.candidate == "python_fallback" for item in measured):
            raise ValueError("portable fallback observation is required")
        if len({item.candidate for item in self.observations}) != len(self.observations):
            raise ValueError("benchmark candidates must be unique")
        return self


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def benchmark_fixture(rows: Sequence[Mapping[str, object]]) -> FrontierBenchmarkReceipt:
    """Run the portable benchmark over a bounded deterministic fixture."""
    if not rows or len(rows) > _MAX_FIXTURE_ROWS:
        raise ValueError("benchmark fixture must contain 1..10000 rows")
    normalized = sorted(
        (dict(row) for row in rows),
        key=lambda row: json.dumps(
            row, sort_keys=True, separators=(",", ":"), allow_nan=False
        ),
    )
    fixture_sha = _digest(normalized)
    selected = [row for row in normalized if row.get("active") is True]
    result = sorted(
        ({"id": row.get("id"), "value": row.get("value")} for row in selected),
        key=lambda row: (str(row["id"]), str(row["value"])),
    )
    query = {"predicate": "active = true", "projection": ["id", "value"], "order": ["id", "value"]}
    workload = BenchmarkWorkload(
        workload_id="frontier-small-active-v1",
        row_count=len(normalized),
        fixture_sha256=fixture_sha,
        query_sha256=_digest(query),
        output_sha256=_digest(result),
    )
    observations = [BenchmarkObservation(
            candidate="python_fallback", status="measured", rows_scanned=len(normalized),
            rows_returned=len(result), operations=len(normalized) + len(selected),
            output_sha256=workload.output_sha256, fallback="portable_python",
            note="Deterministic reference traversal; wall-clock timing intentionally omitted.",
        )]
    observations.extend(_optional_engine_observations(normalized, workload.output_sha256))
    return FrontierBenchmarkReceipt(
        schema_id=BENCHMARK_SCHEMA,
        schema_version=1,
        workload=workload,
        observations=tuple(observations),
        production_dependency_adopted=False,
        technology_promotion_claimed=False,
        disposition="retain-preview",
    )


def _unavailable(candidate: Candidate, reason: str) -> BenchmarkObservation:
    return BenchmarkObservation(
        candidate=candidate, status="unavailable", rows_scanned=0, rows_returned=0,
        operations=0, fallback="optional_engine", note=reason,
    )


def _optional_engine_observations(
    rows: Sequence[Mapping[str, object]], expected_output: str
) -> list[BenchmarkObservation]:
    """Measure installed optional engines without making them required.

    The fixture and projection are intentionally tiny and the result is reduced
    to the same canonical representation as the Python reference. Import or
    execution failures become explicit unavailable observations.
    """
    observations: list[BenchmarkObservation] = []
    try:
        polars = importlib.import_module("polars")
        frame = polars.DataFrame(list(rows))
        output = (
            frame.filter(polars.col("active") == True)  # ruff: ignore[true-false-comparison]
            .select(["id", "value"])
            .sort(["id", "value"])
            .to_dicts()
        )
        observations.append(_measured("polars", len(rows), output, expected_output,
                                     "Optional Polars expression evaluation; no wall-clock timing."))
    except (ImportError, ModuleNotFoundError) as exc:
        observations.append(_unavailable("polars", f"optional engine unavailable: {type(exc).__name__}"))
    except Exception as exc:  # pragma: no cover - platform-specific engine failures
        observations.append(_unavailable("polars", f"optional engine failed closed: {type(exc).__name__}"))

    try:  # ruff: ignore[too-many-statements-in-try-clause]
        arrow = importlib.import_module("pyarrow")
        compute = importlib.import_module("pyarrow.compute")
        table = arrow.Table.from_pylist(list(rows))
        filtered = table.filter(compute.equal(table["active"], arrow.scalar(value=True)))
        output = [{"id": item["id"], "value": item["value"]}
                  for item in filtered.select(["id", "value"]).to_pylist()]
        output.sort(key=lambda item: (str(item["id"]), str(item["value"])))
        observations.append(_measured("arrow", len(rows), output, expected_output,
                                     "Optional Arrow compute evaluation; no wall-clock timing."))
    except (ImportError, ModuleNotFoundError) as exc:
        observations.append(_unavailable("arrow", f"optional engine unavailable: {type(exc).__name__}"))
    except Exception as exc:  # pragma: no cover - platform-specific engine failures
        observations.append(_unavailable("arrow", f"optional engine failed closed: {type(exc).__name__}"))

    try:  # ruff: ignore[too-many-statements-in-try-clause]
        duckdb = importlib.import_module("duckdb")
        # Use a parameterised VALUES relation so no fixture text becomes SQL.
        values = ", ".join("(?, ?, ?)" for _ in rows)
        params = [value for row in rows for value in (row.get("id"), row.get("value"), row.get("active"))]
        connection = duckdb.connect()
        try:
            output_rows = connection.execute(
                f"SELECT column0 AS id, column1 AS value FROM (VALUES {values}) "  # ruff: ignore[hardcoded-sql-expression]
                "WHERE column2 IS TRUE ORDER BY id, value", params
            ).fetchall()
        finally:
            connection.close()
        output = [{"id": item[0], "value": item[1]} for item in output_rows]
        observations.append(_measured("duckdb", len(rows), output, expected_output,
                                     "Optional DuckDB VALUES query; no wall-clock timing."))
    except (ImportError, ModuleNotFoundError) as exc:
        observations.append(_unavailable("duckdb", f"optional engine unavailable: {type(exc).__name__}"))
    except Exception as exc:  # pragma: no cover - platform-specific engine failures
        observations.append(_unavailable("duckdb", f"optional engine failed closed: {type(exc).__name__}"))
    return observations


def _measured(candidate: Candidate, row_count: int, output: list[dict[str, object]],
              expected_output: str, note: str) -> BenchmarkObservation:
    digest = _digest(output)
    if digest != expected_output:
        return _unavailable(candidate, "optional engine parity mismatch; retained as unavailable")
    return BenchmarkObservation(
        candidate=candidate, status="measured", rows_scanned=row_count,
        rows_returned=len(output), operations=row_count + len(output),
        output_sha256=digest, fallback="optional_engine", note=note,
    )


def canonical_benchmark_bytes(receipt: FrontierBenchmarkReceipt) -> bytes:
    """Serialize benchmark evidence with stable bytes for a receipt."""
    return (json.dumps(receipt.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n").encode()
