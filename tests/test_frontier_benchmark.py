"""Deterministic frontier benchmark contracts."""

import pytest
from pydantic import ValidationError

from global_medicines_atlas.frontier_benchmark import (
    benchmark_fixture,
    canonical_benchmark_bytes,
)

FIXTURE = [
    {"id": "b", "value": 2, "active": True},
    {"id": "a", "value": 1, "active": False},
    {"id": "a", "value": 3, "active": True},
]


def test_benchmark_is_deterministic_and_reports_portable_parity() -> None:
    first = benchmark_fixture(FIXTURE)
    second = benchmark_fixture(list(reversed(FIXTURE)))
    assert first.workload.output_sha256 == second.workload.output_sha256
    assert canonical_benchmark_bytes(first) == canonical_benchmark_bytes(second)
    assert first.observations[0].rows_scanned == 3
    assert first.observations[0].rows_returned == 2
    assert first.technology_promotion_claimed is False
    xet = next(
        item for item in first.observations if item.candidate == "xet_restore"
    )
    assert xet.status == "unavailable"
    assert "two exact" in xet.note


def test_benchmark_rejects_divergent_candidate_output() -> None:
    document = benchmark_fixture(FIXTURE).model_dump(mode="json")
    document["observations"].append({
        "candidate": "polars",
        "status": "measured",
        "rows_scanned": 3,
        "rows_returned": 2,
        "operations": 3,
        "output_sha256": "0" * 64,
        "fallback": "optional_engine",
        "note": "negative control",
    })
    with pytest.raises(ValidationError, match="candidate output differs"):
        type(benchmark_fixture(FIXTURE))(**document)


def test_benchmark_bounds_fixture() -> None:
    with pytest.raises(ValueError, match=r"1\.\.10000"):
        benchmark_fixture([])
    with pytest.raises(ValueError, match=r"1\.\.10000"):
        benchmark_fixture([{"id": index} for index in range(10_001)])


def test_benchmark_rejects_non_finite_fixture_values() -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        benchmark_fixture([{"id": "a", "value": float("nan"), "active": True}])
