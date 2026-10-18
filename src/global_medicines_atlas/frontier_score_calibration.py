"""Case-disjoint calibration diagnostics for synthetic candidate scores."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from math import exp
from typing import Literal

from pydantic import Field

from .models import FrozenModel

# Mechanical minimum for the exploratory calibration path: 100 examples per
# class permits at least ten observations per reliability bin in aggregate.
# It is not a statistical adequacy claim for candidate or clinical use.
_MIN_PER_CLASS = 100
_RIDGE = 1e-8
_MIN_HESSIAN_DETERMINANT = 1e-14
_CONVERGENCE_TOLERANCE = 1e-9


class ScoreOutcome(FrozenModel):
    """A top-candidate score and fixture-known correctness outcome."""

    case_id: str = Field(min_length=1, max_length=256)
    score: float = Field(ge=0.0, le=1.0)
    correct: bool


class CalibratedScore(FrozenModel):
    case_id: str
    confidence: float = Field(ge=0.0, le=1.0)


class ScoreCalibrationReceipt(FrozenModel):
    """Holdout diagnostics; calibrated values may prioritize human review only."""

    schema_id: Literal["global-medicines-atlas.frontier-score-calibration"]
    schema_version: Literal[1]
    state: Literal["insufficient_sample", "measured_synthetic_only"]
    calibration_version: str = Field(min_length=1, max_length=128)
    calibration_case_count: int = Field(ge=0)
    calibration_positive_count: int = Field(ge=0)
    calibration_negative_count: int = Field(ge=0)
    minimum_per_class: Literal[100]
    holdout_case_count: int = Field(ge=0)
    holdout_positive_count: int = Field(ge=0)
    holdout_negative_count: int = Field(ge=0)
    case_overlap_count: Literal[0]
    calibration_case_ids_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_case_ids_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    calibration_dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    calibrated_holdout_count: int = Field(ge=0)
    holdout_brier_score: float | None = Field(default=None, ge=0.0, le=1.0)
    holdout_expected_calibration_error: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    confidence_authority: Literal["review_priority_only"]
    clinical_equivalence_claim: Literal[False]
    source_claim: Literal[False]


def _sigmoid(value: float) -> float:
    bounded = min(40.0, max(-40.0, value))
    return 1.0 / (1.0 + exp(-bounded))


def _digest_ids(rows: tuple[ScoreOutcome, ...]) -> str:
    payload = json.dumps(
        sorted(row.case_id for row in rows),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest_dataset(rows: tuple[ScoreOutcome, ...]) -> str:
    payload = json.dumps(
        [
            row.model_dump(mode="json")
            for row in sorted(rows, key=lambda item: item.case_id)
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _fit_platt(rows: tuple[ScoreOutcome, ...]) -> tuple[float, float] | None:
    """Fit a regularized two-parameter logistic map by Newton iteration."""
    intercept = 0.0
    slope = 1.0
    for _ in range(100):
        g0 = _RIDGE * intercept
        g1 = _RIDGE * slope
        h00 = _RIDGE
        h01 = 0.0
        h11 = _RIDGE
        for row in rows:
            probability = _sigmoid(intercept + slope * row.score)
            residual = probability - float(row.correct)
            curvature = probability * (1.0 - probability)
            g0 += residual
            g1 += residual * row.score
            h00 += curvature
            h01 += curvature * row.score
            h11 += curvature * row.score * row.score
        determinant = h00 * h11 - h01 * h01
        if determinant <= _MIN_HESSIAN_DETERMINANT:
            return None
        step0 = (h11 * g0 - h01 * g1) / determinant
        step1 = (h00 * g1 - h01 * g0) / determinant
        intercept -= step0
        slope -= step1
        if max(abs(step0), abs(step1)) < _CONVERGENCE_TOLERANCE:
            break
    if slope <= 0:
        return None
    return intercept, slope


def _ece(rows: tuple[tuple[float, bool], ...], bins: int = 10) -> float:
    if not rows:
        return 0.0
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        members = tuple(
            row
            for row in rows
            if lower <= row[0] < upper
            or (index == bins - 1 and row[0] >= upper)
        )
        if members:
            confidence = sum(row[0] for row in members) / len(members)
            accuracy = sum(row[1] for row in members) / len(members)
            error += len(members) / len(rows) * abs(confidence - accuracy)
    return error


def calibrate_scores(
    calibration: Iterable[ScoreOutcome],
    holdout: Iterable[ScoreOutcome],
    *,
    calibration_version: str,
) -> ScoreCalibrationReceipt:
    """Fit on one case set and evaluate once on a disjoint synthetic holdout.

    Small cohorts receive no emitted confidence or calibration metric. Even a
    successful synthetic fit is explicitly restricted to review prioritization
    and makes no source, clinical, or production claim.
    """
    train = tuple(sorted(calibration, key=lambda row: row.case_id))
    test = tuple(sorted(holdout, key=lambda row: row.case_id))
    for label, rows in (("calibration", train), ("holdout", test)):
        if len({row.case_id for row in rows}) != len(rows):
            raise ValueError(f"{label} case identifiers must be unique")
    overlap = {row.case_id for row in train} & {row.case_id for row in test}
    if overlap:
        raise ValueError("calibration and holdout must be case-disjoint")
    train_pos = sum(row.correct for row in train)
    train_neg = len(train) - train_pos
    test_pos = sum(row.correct for row in test)
    test_neg = len(test) - test_pos
    params = (
        _fit_platt(train)
        if (train_pos >= _MIN_PER_CLASS and train_neg >= _MIN_PER_CLASS)
        else None
    )
    sufficient_test = test_pos >= _MIN_PER_CLASS and test_neg >= _MIN_PER_CLASS
    measured = params is not None and sufficient_test
    calibrated = (
        tuple(
            (_sigmoid(params[0] + params[1] * row.score), row.correct)
            for row in test
        )
        if measured and params is not None
        else ()
    )
    return ScoreCalibrationReceipt(
        schema_id="global-medicines-atlas.frontier-score-calibration",
        schema_version=1,
        state="measured_synthetic_only" if measured else "insufficient_sample",
        calibration_version=calibration_version,
        calibration_case_count=len(train),
        calibration_positive_count=train_pos,
        calibration_negative_count=train_neg,
        minimum_per_class=_MIN_PER_CLASS,
        holdout_case_count=len(test),
        holdout_positive_count=test_pos,
        holdout_negative_count=test_neg,
        case_overlap_count=0,
        calibration_case_ids_sha256=_digest_ids(train),
        holdout_case_ids_sha256=_digest_ids(test),
        calibration_dataset_sha256=_digest_dataset(train),
        holdout_dataset_sha256=_digest_dataset(test),
        calibrated_holdout_count=len(calibrated),
        holdout_brier_score=(
            sum((score - float(correct)) ** 2 for score, correct in calibrated)
            / len(calibrated)
            if calibrated
            else None
        ),
        holdout_expected_calibration_error=(
            _ece(calibrated) if calibrated else None
        ),
        confidence_authority="review_priority_only",
        clinical_equivalence_claim=False,
        source_claim=False,
    )
