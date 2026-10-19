import json
from pathlib import Path

import pytest

from global_medicines_atlas.matching_models import EvaluationCase
from global_medicines_atlas.matching_qualification import (
    assess_matching_behavior,
)

FIXTURE = Path(__file__).parent / "fixtures" / "matching" / "cases.jsonl"
SCREENING = (
    Path(__file__).parents[1]
    / "quality"
    / "qualifications"
    / "australian-gold-relationship-screening-20261019.json"
)


def cases() -> tuple[EvaluationCase, ...]:
    return tuple(
        EvaluationCase.model_validate_json(line)
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
    )


@pytest.mark.integration
def test_candidate_generator_is_assessed_against_all_synthetic_labels() -> None:
    result = assess_matching_behavior(cases(), lexical_threshold=0.65)
    metrics = result.metrics.overall
    outcomes = {item.case_id: item for item in result.outcomes}

    assert metrics.case_count == 6
    assert metrics.evaluated_count == 4
    assert metrics.true_positive == 2
    assert metrics.false_positive == 2
    assert metrics.false_negative == 2
    assert metrics.precision == pytest.approx(0.5)
    assert metrics.recall == pytest.approx(0.5)
    assert metrics.f_score == pytest.approx(0.5)
    assert metrics.candidate_recall_at_k == pytest.approx(0.5)
    assert metrics.brier_score == pytest.approx(0.39381130013125)
    assert metrics.expected_calibration_error == pytest.approx(0.44110925)
    assert metrics.coverage == pytest.approx(2 / 3)
    assert metrics.selective_risk == pytest.approx(0.5)
    assert outcomes["strength-negative"].ranked_target_ids == ("us:cd:100",)
    assert outcomes["similar-name-negative"].ranked_target_ids == (
        "us:ing:chlorprop",
    )
    assert outcomes["brand-generic"].abstained
    assert outcomes["pack-ambiguous"].abstained
    assert result.production_promotion_eligible is False


@pytest.mark.integration
def test_stricter_cutoff_trades_fixture_false_positives_for_coverage() -> None:
    baseline = assess_matching_behavior(cases(), lexical_threshold=0.65)
    strict = assess_matching_behavior(cases(), lexical_threshold=0.99)

    assert strict.metrics.overall.false_positive == 0
    assert strict.metrics.overall.precision == pytest.approx(1.0)
    assert strict.metrics.overall.recall == pytest.approx(0.5)
    assert strict.metrics.overall.coverage == pytest.approx(1 / 3)
    assert strict.metrics.overall.selective_risk == pytest.approx(0.0)
    assert strict.metrics.overall.coverage < baseline.metrics.overall.coverage
    assert strict.production_promotion_eligible is False


@pytest.mark.integration
def test_gold_screen_keeps_source_structure_distinct_from_matches() -> None:
    screen = json.loads(SCREENING.read_text(encoding="utf-8"))
    relationships = {item["kind"]: item for item in screen["relationships"]}

    mbs = relationships["source_record_has_benefit"]
    assert (
        mbs["decision"] == "qualifies_as_source_explicit_within_record_evidence"
    )
    assert mbs["scope"]["edges"] == 5989
    assert mbs["screen"]["confidence"] is None
    assert mbs["screen"]["review_state"] == "not_reviewed"
    assert (
        relationships["cross_source_or_cross_record_semantic_match"]["decision"]
        == "does_not_qualify_for_gold_acceptance"
    )
    assert screen["production_promotion_eligible"] is False
