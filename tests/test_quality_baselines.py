"""Immutable mutation and performance baseline contracts."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.quality_baselines import (
    MutationObservations,
    Phase3Baselines,
    load_performance_receipt,
    load_phase3_baselines,
    load_survivor_review,
    mutation_regressed,
    performance_regressions,
)

BASELINE_PATH = Path("quality/baselines/phase3.json")
SURVIVOR_REVIEW_PATH = Path("quality/baselines/mutation-survivor-review.json")


def test_committed_phase3_baseline_is_valid_and_qualified() -> None:
    baseline = load_phase3_baselines(BASELINE_PATH)
    assert baseline.mutation.observations.survived == 365
    assert baseline.mutation.observations.untested == 2
    assert baseline.mutation.promotion_status == "qualified"
    assert baseline.performance.workload.row_count == 1_000_000


def test_survivor_review_reconciles_hosted_report_without_waivers() -> None:
    review = load_survivor_review(SURVIVOR_REVIEW_PATH)
    assert sum(group.count for group in review.groups) == 365
    assert review.untested == 2
    assert review.groups[0].module == "source_health"
    assert review.groups[0].count == 195
    assert review.groups[-1].module == "comparison_validity"
    assert {group.disposition for group in review.groups} == {"open_test_gap"}


def test_mutation_regression_is_independent_of_promotion_target() -> None:
    baseline = load_phase3_baselines(BASELINE_PATH).mutation
    unchanged = baseline.observations
    improved = MutationObservations(
        killed=1_650,
        survived=295,
        untested=0,
        skipped=0,
        suspicious=0,
        timeout=0,
        interrupted=0,
        segfault=0,
        total=1_945,
        score_percent=1_650 / 1_945 * 100,
    )
    worse = MutationObservations(
        killed=1_627,
        survived=318,
        untested=0,
        skipped=0,
        suspicious=0,
        timeout=0,
        interrupted=0,
        segfault=0,
        total=1_945,
        score_percent=1_627 / 1_945 * 100,
    )
    assert not mutation_regressed(baseline, unchanged)
    assert not mutation_regressed(baseline, improved)
    assert mutation_regressed(baseline, worse)


def test_mutation_regression_compares_rate_when_scope_expands() -> None:
    baseline = load_phase3_baselines(BASELINE_PATH).mutation
    expanded_but_not_regressed = MutationObservations(
        killed=1_838,
        survived=357,
        untested=0,
        skipped=0,
        suspicious=0,
        timeout=0,
        interrupted=0,
        segfault=0,
        total=2_195,
        score_percent=1_838 / 2_195 * 100,
    )
    expanded_and_regressed = expanded_but_not_regressed.model_copy(
        update={
            "killed": 1_836,
            "survived": 359,
            "score_percent": 1_836 / 2_195 * 100,
        }
    )

    assert not mutation_regressed(baseline, expanded_but_not_regressed)
    assert mutation_regressed(baseline, expanded_and_regressed)


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
    wrong_score = deepcopy(document)
    wrong_score["mutation"]["observations"]["score_percent"] = 99
    with pytest.raises(ValidationError, match="score does not match"):
        Phase3Baselines.model_validate(wrong_score)


def test_baseline_rejects_false_promotion_status() -> None:
    document = load_phase3_baselines(BASELINE_PATH).model_dump(mode="json")
    document["mutation"]["promotion_status"] = "blocked_survivor_debt"
    with pytest.raises(ValidationError, match="contradicts score"):
        Phase3Baselines.model_validate(document)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"survived": 316}, "reconcile"),
        ({"groups.0.priority": 2}, "contiguous"),
        ({"promotion_survivor_maximum": 316}, "contradicts debt"),
    ],
)
def test_survivor_review_rejects_inconsistent_classification(
    mutation: dict[str, int],
    message: str,
) -> None:
    document = load_survivor_review(SURVIVOR_REVIEW_PATH).model_dump(
        mode="json"
    )
    key, value = next(iter(mutation.items()))
    if key == "groups.0.priority":
        document["groups"][0]["priority"] = value
    else:
        document[key] = value
    with pytest.raises(ValidationError, match=message):
        type(load_survivor_review(SURVIVOR_REVIEW_PATH)).model_validate(
            document
        )


def test_performance_receipt_loader_requires_object(tmp_path: Path) -> None:
    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps({"passed": True}), encoding="utf-8")
    assert load_performance_receipt(valid) == {"passed": True}
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")
    with pytest.raises(TypeError, match="must be an object"):
        load_performance_receipt(invalid)
