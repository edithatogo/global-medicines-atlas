from pathlib import Path

from scripts.run_product_qualification import run

from global_medicines_atlas.product_release import (
    PerformanceResult,
    VerificationState,
)


def test_unverified_measurement_never_passes():
    result = PerformanceResult(
        scenario_id="PERF-QUERY",
        scenario="fixture comparison query p95",
        budget_ms=250,
        reason="no durable execution receipt was supplied",
    )
    assert result.verification is VerificationState.NOT_VERIFIED
    assert result.observed_ms is None
    assert not result.passed


def test_verified_measurement_must_meet_budget():
    passing = PerformanceResult(
        scenario_id="PERF-QUERY",
        scenario="fixture comparison query p95",
        budget_ms=250,
        observed_ms=249,
        sample_size=20,
        verification=VerificationState.PASSED,
        reason="executed workload passed",
        receipt_id="receipt-1",
    )
    failing = passing.model_copy(update={"observed_ms": 251})
    assert passing.passed
    assert not failing.passed


def test_runner_measures_real_fixture_workloads(tmp_path: Path):
    output = tmp_path / "evidence.json"
    receipts = tmp_path / "receipts"
    run(output, receipts)
    performance = sorted(receipts.glob("PERF-*.json"))
    assert len(performance) == 3
    assert all(
        '"sample_size":20' in item.read_text().replace(" ", "")
        for item in performance
    )
