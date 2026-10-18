"""Calibration is case-disjoint, sample-gated, and non-authoritative."""

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.frontier_candidate_benchmark import (
    load_synthetic_matching_cases,
    score_synthetic_candidate_cases,
)
from global_medicines_atlas.frontier_score_calibration import (
    ScoreOutcome,
    calibrate_scores,
)


def _observations(prefix: str, count: int) -> tuple[ScoreOutcome, ...]:
    result = []
    for index in range(count):
        score = (index % 20 + 0.5) / 20
        probability = 1 / (1 + math.exp(-(-2.0 + 4.0 * score)))
        # Deterministic, separate synthetic labels produce both outcomes in
        # every score band without introducing random state.
        correct = (index * 37 % 1000) < round(probability * 1000)
        result.append(
            ScoreOutcome(
                case_id=f"{prefix}-{index}", score=score, correct=correct
            )
        )
    return tuple(result)


def test_calibration_uses_independent_case_disjoint_holdout() -> None:
    result = calibrate_scores(
        _observations("cal", 400),
        _observations("hold", 400),
        calibration_version="synthetic-platt-v1",
    )

    assert result.state == "measured_synthetic_only"
    assert result.calibration_case_count == 400
    assert result.holdout_case_count == 400
    assert result.case_overlap_count == 0
    assert result.calibrated_holdout_count == 400
    assert result.minimum_per_class == 100
    assert result.calibration_dataset_sha256 != result.holdout_dataset_sha256
    assert result.holdout_brier_score is not None
    assert result.holdout_expected_calibration_error is not None
    assert result.confidence_authority == "review_priority_only"
    assert result.clinical_equivalence_claim is False


def test_calibration_refuses_small_sample_without_emitting_confidence() -> None:
    result = calibrate_scores(
        _observations("cal", 10),
        _observations("hold", 10),
        calibration_version="synthetic-platt-v1",
    )

    assert result.state == "insufficient_sample"
    assert result.calibrated_holdout_count == 0
    assert result.holdout_brier_score is None


def test_calibration_rejects_case_leakage() -> None:
    with pytest.raises(ValueError, match="case-disjoint"):
        calibrate_scores(
            _observations("same", 400),
            _observations("same", 400),
            calibration_version="synthetic-platt-v1",
        )


def test_calibration_rejects_duplicate_case_ids_and_bad_scores() -> None:
    with pytest.raises(ValueError, match="unique"):
        calibrate_scores(
            (ScoreOutcome(case_id="dup", score=0.2, correct=True),) * 2,
            _observations("hold", 400),
            calibration_version="synthetic-platt-v1",
        )
    with pytest.raises(ValidationError):
        ScoreOutcome(case_id="bad", score=1.1, correct=True)


def test_existing_frontier_candidate_cohort_cannot_emit_confidence() -> None:
    cases = load_synthetic_matching_cases(
        Path(__file__).parent / "fixtures" / "matching"
    )
    outcomes = score_synthetic_candidate_cases(cases)
    result = calibrate_scores(
        outcomes,
        (),
        calibration_version="frontier-six-case-diagnostic-v1",
    )

    assert len(outcomes) == 4
    assert result.state == "insufficient_sample"
    assert result.calibrated_holdout_count == 0
    assert result.holdout_brier_score is None
