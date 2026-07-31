"""Immutable mutation and performance baseline contracts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.quality_baselines import (
    MutationObservations,
    Phase3Baselines,
    load_phase3_baselines,
    load_survivor_review,
    mutation_regressed,
    performance_regressions,
)

BASELINE_PATH = Path("quality/baselines/phase3.json")
SURVIVOR_REVIEW_PATH = Path("quality/baselines/mutation-survivor-review.json")


def test_committed_phase3_baseline_is_valid_and_records_debt() -> None:
    baseline = load_phase3_baselines(BASELINE_PATH)
    assert baseline.mutation.observations.survived == 523
    assert baseline.mutation.promotion_status == "blocked_survivor_debt"
    assert baseline.performance.workload.row_count == 1_000_000


def test_survivor_review_reconciles_hosted_report_without_waivers() -> None:
    review = load_survivor_review(SURVIVOR_REVIEW_PATH)
    assert sum(group.count for group in review.groups) == 523
    assert review.groups[0].module == "source_health"
    assert review.groups[0].count == 240
    assert {group.disposition for group in review.groups} == {"open_test_gap"}


def test_mutation_regression_is_independent_of_promotion_target() -> None:
    baseline = load_phase3_baselines(BASELINE_PATH).mutation
    unchanged = baseline.observations
    improved = MutationObservations(
        killed=1_524,
        survived=382,
        untested=0,
        skipped=0,
        suspicious=0,
        timeout=0,
        interrupted=0,
        segfault=0,
        total=1_906,
        score_percent=1_524 / 1_906 * 100,
    )
    worse = MutationObservations(
        killed=1_382,
        survived=524,
        untested=0,
        skipped=0,
        suspicious=0,
        timeout=0,
        interrupted=0,
        segfault=0,
        total=1_906,
        score_percent=1_382 / 1_906 * 100,
    )
    assert not mutation_regressed(baseline, unchanged)
    assert not mutation_regressed(baseline, improved)
    assert mutation_regressed(baseline, worse)


def test_performance_regression_envelope_is_direction_aware() -> None:
    baseline = load_phase3_baselines(BASELINE_PATH).performance
    current = baseline.observations.model_dump()
    assert performance_regressions(baseline, current) == ()
    without_process_memory = {
        key: value
        for key, value in current.items()
        if key != "process_peak_memory_mib"
    }
    assert performance_regressions(baseline, without_process_memory) == ()
    current["cold_p95_ms"] *= 2
    current["concurrent_records_per_second"] /= 2
    assert performance_regressions(baseline, current) == (
        "cold_p95_ms",
        "concurrent_records_per_second",
    )


def test_baseline_rejects_inconsistent_mutation_evidence() -> None:
    document = load_phase3_baselines(BASELINE_PATH).model_dump(mode="json")
    inconsistent = deepcopy(document)
    inconsistent["mutation"]["observations"]["survived"] = 1
    with pytest.raises(ValidationError, match="status counts"):
        Phase3Baselines.model_validate(inconsistent)


def test_baseline_rejects_false_promotion_status() -> None:
    document = load_phase3_baselines(BASELINE_PATH).model_dump(mode="json")
    document["mutation"]["promotion_status"] = "qualified"
    with pytest.raises(ValidationError, match="contradicts score"):
        Phase3Baselines.model_validate(document)
