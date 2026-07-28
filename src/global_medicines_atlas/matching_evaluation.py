"""Deterministic evaluation metrics for review-first matching candidates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from math import sqrt

from pydantic import Field

from .matching_models import (
    AbstentionReason,
    CandidatePrediction,
    EvaluationCase,
    EvaluationClass,
)
from .models import FrozenModel


class MatchingMetrics(FrozenModel):
    case_count: int = Field(ge=0)
    evaluated_count: int = Field(ge=0)
    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)
    true_negative: int = Field(ge=0)
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f_score: float = Field(ge=0.0, le=1.0)
    candidate_recall_at_k: float = Field(ge=0.0, le=1.0)
    brier_score: float = Field(ge=0.0, le=1.0)
    expected_calibration_error: float = Field(ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    abstention_rate: float = Field(ge=0.0, le=1.0)
    selective_risk: float = Field(ge=0.0, le=1.0)


class GroupedMatchingMetrics(FrozenModel):
    overall: MatchingMetrics
    by_mapping_level: dict[str, MatchingMetrics]
    by_jurisdiction_pair: dict[str, MatchingMetrics]
    by_language: dict[str, MatchingMetrics]
    by_fixture_class: dict[str, MatchingMetrics]


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _top_is_relevant(
    case: EvaluationCase,
    prediction: CandidatePrediction,
) -> bool:
    return bool(
        prediction.ranked_target_ids
        and prediction.ranked_target_ids[0] in case.relevant_target_ids
    )


def _expected_calibration_error(
    outcomes: list[tuple[float, bool]],
    bin_count: int,
) -> float:
    if bin_count < 1:
        raise ValueError("bin_count must be positive")
    if not outcomes:
        return 0.0
    total = len(outcomes)
    error = 0.0
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        members = [
            (confidence, correct)
            for confidence, correct in outcomes
            if lower <= confidence < upper
            or (index == bin_count - 1 and confidence >= upper)
        ]
        if not members:
            continue
        average_confidence = sum(item[0] for item in members) / len(members)
        accuracy = sum(item[1] for item in members) / len(members)
        error += len(members) / total * abs(accuracy - average_confidence)
    return error


def evaluate_predictions(  # ruff: ignore[too-many-branches, too-many-locals]
    cases: Iterable[EvaluationCase],
    predictions: Iterable[CandidatePrediction],
    *,
    k: int = 5,
    calibration_bins: int = 10,
) -> MatchingMetrics:
    """Evaluate candidates without treating a score as reviewed equivalence."""

    if k < 1:
        raise ValueError("k must be positive")
    case_list = list(cases)
    prediction_list = list(predictions)
    predictions_by_case = {item.case_id: item for item in prediction_list}
    if len(predictions_by_case) != len(prediction_list):
        raise ValueError("Predictions must have unique case identifiers")
    unknown = predictions_by_case.keys() - {case.case_id for case in case_list}
    if unknown:
        raise ValueError("Predictions contain unknown case identifiers")

    tp = fp = fn = tn = candidate_hits = positive_count = 0
    outcomes: list[tuple[float, bool]] = []
    answered = 0
    errors = 0
    for case in case_list:
        if case.relevant_target_ids:
            positive_count += 1
        prediction = predictions_by_case.get(
            case.case_id,
            CandidatePrediction(
                case_id=case.case_id,
                confidence=0.0,
                abstention_reason=AbstentionReason.INSUFFICIENT_EVIDENCE,
            ),
        )
        if prediction.abstained:
            if case.evaluation_class is not EvaluationClass.NEGATIVE:
                fn += 1
            continue
        answered += 1
        has_prediction = bool(prediction.ranked_target_ids)
        correct = _top_is_relevant(case, prediction)
        if case.relevant_target_ids:
            if any(
                item in case.relevant_target_ids
                for item in prediction.ranked_target_ids[:k]
            ):
                candidate_hits += 1
            if correct:
                tp += 1
            else:
                fn += 1
                if has_prediction:
                    fp += 1
        elif has_prediction:
            fp += 1
        else:
            tn += 1
            correct = True
        errors += not correct
        outcomes.append((prediction.confidence, correct))

    count = len(case_list)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    brier = (
        sum(
            (confidence - float(correct)) ** 2
            for confidence, correct in outcomes
        )
        / len(outcomes)
        if outcomes
        else 0.0
    )
    return MatchingMetrics(
        case_count=count,
        evaluated_count=answered,
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        true_negative=tn,
        precision=precision,
        recall=recall,
        f_score=(
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        ),
        candidate_recall_at_k=_ratio(candidate_hits, positive_count),
        brier_score=brier,
        expected_calibration_error=_expected_calibration_error(
            outcomes,
            calibration_bins,
        ),
        coverage=_ratio(answered, count),
        abstention_rate=1.0 - _ratio(answered, count) if count else 0.0,
        selective_risk=_ratio(errors, answered),
    )


def root_mean_brier(metrics: MatchingMetrics) -> float:
    """Expose an interpretable calibration diagnostic."""

    return sqrt(metrics.brier_score)


def evaluate_grouped_predictions(
    cases: Iterable[EvaluationCase],
    predictions: Iterable[CandidatePrediction],
    *,
    k: int = 5,
    calibration_bins: int = 10,
) -> GroupedMatchingMetrics:
    """Evaluate relevant quality and bias slices with identical metric rules."""

    case_list = tuple(cases)
    prediction_list = tuple(predictions)
    predictions_by_case = {
        prediction.case_id: prediction for prediction in prediction_list
    }

    def jurisdiction_pair(case: EvaluationCase) -> str:
        targets = sorted({target.jurisdiction for target in case.targets})
        return f"{case.source.jurisdiction}-{'/'.join(targets)}"

    def fixture_class(case: EvaluationCase) -> str:
        return case.tags[0] if case.tags else case.evaluation_class.value

    def grouped(
        key: Callable[[EvaluationCase], Iterable[str]],
    ) -> dict[str, MatchingMetrics]:
        members: dict[str, list[EvaluationCase]] = defaultdict(list)
        for case in case_list:
            for value in key(case):
                members[value].append(case)
        return {
            value: evaluate_predictions(
                group,
                (
                    predictions_by_case[case.case_id]
                    for case in group
                    if case.case_id in predictions_by_case
                ),
                k=k,
                calibration_bins=calibration_bins,
            )
            for value, group in sorted(members.items())
        }

    return GroupedMatchingMetrics(
        overall=evaluate_predictions(
            case_list,
            prediction_list,
            k=k,
            calibration_bins=calibration_bins,
        ),
        by_mapping_level=grouped(lambda case: (case.mapping_level.value,)),
        by_jurisdiction_pair=grouped(lambda case: (jurisdiction_pair(case),)),
        by_language=grouped(lambda case: case.languages),
        by_fixture_class=grouped(lambda case: (fixture_class(case),)),
    )
