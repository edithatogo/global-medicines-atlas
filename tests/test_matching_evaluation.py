import json
from pathlib import Path

import pytest

from global_medicines_atlas.matching_evaluation import (
    evaluate_grouped_predictions,
    evaluate_predictions,
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
