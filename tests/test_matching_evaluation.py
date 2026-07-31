import json
from pathlib import Path

import pytest

from global_medicines_atlas.matching_evaluation import (
    evaluate_grouped_predictions,
    evaluate_predictions,
    root_mean_brier,
)
from global_medicines_atlas.matching_models import (
    AbstentionReason,
    CandidatePrediction,
    EvaluationCase,
)

FIXTURES = Path(__file__).parent / "fixtures" / "matching"


def load_cases() -> list[EvaluationCase]:
    return [
        EvaluationCase.model_validate_json(line)
        for line in (FIXTURES / "cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]


@pytest.mark.integration
def test_fixture_manifest_describes_complete_synthetic_corpus() -> None:
    manifest = json.loads(
        (FIXTURES / "manifest.json").read_text(encoding="utf-8")
    )
    cases = load_cases()

    assert manifest["fixture_count"] == len(cases)
    assert manifest["synthetic"] is True
    assert manifest["clinical_equivalence_claims"] is False
    assert {case.evaluation_class for case in cases} == set(manifest["classes"])
    assert set().union(*(set(case.languages) for case in cases)) == set(
        manifest["languages"]
    )


@pytest.mark.unit
def test_perfect_predictions_report_perfect_discrimination() -> None:
    cases = load_cases()
    predictions = [
        CandidatePrediction(
            case_id=case.case_id,
            ranked_target_ids=tuple(sorted(case.relevant_target_ids)),
            confidence=1.0,
        )
        for case in cases
    ]

    metrics = evaluate_predictions(cases, predictions, k=2)

    assert metrics.precision == pytest.approx(1.0)
    assert metrics.recall == pytest.approx(1.0)
    assert metrics.f_score == pytest.approx(1.0)
    assert metrics.candidate_recall_at_k == pytest.approx(1.0)
    assert metrics.brier_score == pytest.approx(0.0)
    assert metrics.coverage == pytest.approx(1.0)
    assert metrics.selective_risk == pytest.approx(0.0)


@pytest.mark.unit
def test_abstention_is_visible_in_coverage_and_recall() -> None:
    cases = load_cases()[:2]
    predictions = [
        CandidatePrediction(
            case_id=cases[0].case_id,
            ranked_target_ids=tuple(cases[0].relevant_target_ids),
            confidence=0.8,
        ),
        CandidatePrediction(
            case_id=cases[1].case_id,
            confidence=0.0,
            abstention_reason=AbstentionReason.AMBIGUOUS_CANDIDATES,
        ),
    ]

    metrics = evaluate_predictions(cases, predictions)

    assert metrics.coverage == pytest.approx(0.5)
    assert metrics.abstention_rate == pytest.approx(0.5)
    assert metrics.recall == pytest.approx(0.5)
    assert metrics.selective_risk == pytest.approx(0.0)


@pytest.mark.unit
def test_mixed_predictions_report_exact_confusion_and_calibration_metrics() -> (
    None
):
    cases = load_cases()[:4]
    predictions = [
        CandidatePrediction(
            case_id=cases[0].case_id,
            ranked_target_ids=("au:ing:para",),
            confidence=0.8,
        ),
        CandidatePrediction(
            case_id=cases[1].case_id,
            ranked_target_ids=("gb:mp:propranolol",),
            confidence=0.6,
        ),
        CandidatePrediction(
            case_id=cases[2].case_id,
            ranked_target_ids=("us:cd:100",),
            confidence=0.7,
        ),
        CandidatePrediction(
            case_id=cases[3].case_id,
            confidence=0.9,
        ),
    ]

    metrics = evaluate_predictions(
        cases,
        predictions,
        k=1,
        calibration_bins=2,
    )

    assert metrics.model_dump() == {
        "case_count": 4,
        "evaluated_count": 4,
        "true_positive": 1,
        "false_positive": 2,
        "false_negative": 1,
        "true_negative": 1,
        "precision": pytest.approx(1 / 3),
        "recall": pytest.approx(1 / 2),
        "f_score": pytest.approx(0.4),
        "candidate_recall_at_k": pytest.approx(1 / 2),
        "brier_score": pytest.approx(0.225),
        "expected_calibration_error": pytest.approx(0.25),
        "coverage": pytest.approx(1.0),
        "abstention_rate": pytest.approx(0.0),
        "selective_risk": pytest.approx(0.5),
    }
    assert root_mean_brier(metrics) == pytest.approx(0.225**0.5)


@pytest.mark.unit
def test_candidate_recall_obeys_the_exact_k_boundary() -> None:
    case = load_cases()[1]
    prediction = CandidatePrediction(
        case_id=case.case_id,
        ranked_target_ids=("gb:mp:propranolol", "gb:mp:paracetamol"),
        confidence=0.5,
    )

    at_one = evaluate_predictions([case], [prediction], k=1)
    at_two = evaluate_predictions([case], [prediction], k=2)

    assert at_one.candidate_recall_at_k == pytest.approx(0.0)
    assert at_two.candidate_recall_at_k == pytest.approx(1.0)
    assert at_one.true_positive == at_two.true_positive == 0
    assert at_one.false_positive == at_two.false_positive == 1
    assert at_one.false_negative == at_two.false_negative == 1


@pytest.mark.unit
def test_calibration_bins_include_zero_midpoint_and_one_once() -> None:
    cases = load_cases()[:3]
    predictions = [
        CandidatePrediction(
            case_id=cases[0].case_id,
            ranked_target_ids=("au:ing:para",),
            confidence=1.0,
        ),
        CandidatePrediction(
            case_id=cases[1].case_id,
            ranked_target_ids=("gb:mp:propranolol",),
            confidence=0.5,
        ),
        CandidatePrediction(
            case_id=cases[2].case_id,
            confidence=0.0,
        ),
    ]

    metrics = evaluate_predictions(cases, predictions, calibration_bins=2)

    assert metrics.brier_score == pytest.approx(5 / 12)
    assert metrics.expected_calibration_error == pytest.approx(1 / 2)


@pytest.mark.unit
def test_empty_evaluation_has_exact_zero_metrics() -> None:
    metrics = evaluate_predictions([], [])

    assert set(metrics.model_dump().values()) == {0}


@pytest.mark.integration
def test_grouped_metrics_expose_quality_and_bias_slices() -> None:
    cases = load_cases()
    predictions = [
        CandidatePrediction(
            case_id=case.case_id,
            ranked_target_ids=tuple(sorted(case.relevant_target_ids)),
            confidence=1.0,
        )
        for case in cases
    ]

    grouped = evaluate_grouped_predictions(cases, predictions, k=2)

    assert set(grouped.by_mapping_level) == {
        "clinical_drug",
        "ingredient",
        "medicinal_product",
        "pack",
    }
    assert {"en", "pt", "ja", "mi", "de"} <= set(grouped.by_language)
    assert "NZL-DEU" in grouped.by_jurisdiction_pair
    assert grouped.by_fixture_class["exact-identifier"].case_count == 1
    assert list(grouped.by_mapping_level) == sorted(grouped.by_mapping_level)
    assert list(grouped.by_jurisdiction_pair) == sorted(
        grouped.by_jurisdiction_pair
    )
    assert list(grouped.by_language) == sorted(grouped.by_language)
    assert list(grouped.by_fixture_class) == sorted(grouped.by_fixture_class)
    assert grouped.overall.case_count == len(cases)


@pytest.mark.unit
def test_grouped_fixture_class_falls_back_when_tags_are_absent() -> None:
    case = load_cases()[0].model_copy(update={"tags": ()})
    prediction = CandidatePrediction(
        case_id=case.case_id,
        ranked_target_ids=tuple(case.relevant_target_ids),
        confidence=1.0,
    )

    grouped = evaluate_grouped_predictions([case], [prediction])

    assert list(grouped.by_fixture_class) == [case.evaluation_class.value]
    assert grouped.by_fixture_class["positive"].case_count == 1


@pytest.mark.edge
def test_evaluation_rejects_unknown_or_duplicate_case_predictions() -> None:
    cases = load_cases()[:1]
    unknown = CandidatePrediction(case_id="unknown", confidence=0.0)
    with pytest.raises(ValueError, match="unknown"):
        evaluate_predictions(cases, [unknown])

    duplicate = CandidatePrediction(case_id=cases[0].case_id, confidence=0.0)
    with pytest.raises(ValueError, match="unique"):
        evaluate_predictions(cases, [duplicate, duplicate])


@pytest.mark.edge
@pytest.mark.parametrize(
    ("k", "bins", "message"),
    [(0, 10, "k must be positive"), (1, 0, "bin_count must be positive")],
)
def test_evaluation_rejects_invalid_metric_configuration(
    k: int,
    bins: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        evaluate_predictions(load_cases()[:1], [], k=k, calibration_bins=bins)
