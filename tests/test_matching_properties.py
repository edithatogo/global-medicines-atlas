import pytest
from hypothesis import given
from hypothesis import strategies as st

from global_medicines_atlas.matching_evaluation import evaluate_predictions
from global_medicines_atlas.matching_models import (
    CandidatePrediction,
    EvaluationCase,
    EvaluationClass,
    MappingEndpoint,
    MappingLevel,
)


def evaluation_case(*, relevant: bool) -> EvaluationCase:
    target = MappingEndpoint(
        concept_id="au:target",
        jurisdiction="AUS",
        level=MappingLevel.INGREDIENT,
        preferred_name="Target",
        language="en",
        provenance_ids=("fixture:target",),
    )
    return EvaluationCase(
        case_id="case",
        evaluation_class=(
            EvaluationClass.POSITIVE if relevant else EvaluationClass.NEGATIVE
        ),
        mapping_level=MappingLevel.INGREDIENT,
        source=MappingEndpoint(
            concept_id="nz:source",
            jurisdiction="NZL",
            level=MappingLevel.INGREDIENT,
            preferred_name="Source",
            language="en",
            provenance_ids=("fixture:source",),
        ),
        targets=(target,),
        relevant_target_ids=(
            frozenset({target.concept_id}) if relevant else frozenset()
        ),
        languages=("en",),
        rationale="Synthetic property fixture.",
    )


@pytest.mark.property
@given(
    confidence=st.floats(
        min_value=0.0,
        max_value=1.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    relevant=st.booleans(),
)
def test_metrics_remain_bounded(
    confidence: float,
    relevant: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
) -> None:
    case = evaluation_case(relevant=relevant)
    prediction = CandidatePrediction(
        case_id=case.case_id,
        ranked_target_ids=("au:target",),
        confidence=confidence,
    )

    metrics = evaluate_predictions([case], [prediction])

    for value in (
        metrics.precision,
        metrics.recall,
        metrics.f_score,
        metrics.candidate_recall_at_k,
        metrics.brier_score,
        metrics.expected_calibration_error,
        metrics.coverage,
        metrics.abstention_rate,
        metrics.selective_risk,
    ):
        assert 0.0 <= value <= 1.0


@pytest.mark.property
@given(confidences=st.lists(st.floats(0.0, 1.0), min_size=1, max_size=20))
def test_case_order_does_not_change_aggregate_metrics(
    confidences: list[float],
) -> None:
    cases = []
    predictions = []
    for index, confidence in enumerate(confidences):
        case = evaluation_case(relevant=True).model_copy(
            update={"case_id": f"case-{index}"}
        )
        cases.append(case)
        predictions.append(
            CandidatePrediction(
                case_id=case.case_id,
                ranked_target_ids=("au:target",),
                confidence=confidence,
            )
        )

    assert evaluate_predictions(cases, predictions) == evaluate_predictions(
        reversed(cases),
        reversed(predictions),
    )
