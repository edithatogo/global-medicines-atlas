from datetime import UTC, datetime

import pytest

from global_medicines_atlas.matching_features import (
    FeatureDisposition as D,
)
from global_medicines_atlas.matching_features import (
    FeatureKind as K,
)
from global_medicines_atlas.matching_features import (
    MatchFeatures,
    feature,
)
from global_medicines_atlas.matching_models import MappingLevel, ReviewState
from global_medicines_atlas.matching_policy import (
    MatchCandidate,
    PolicyReason,
    ReviewOnlyPolicy,
)


def _candidate(
    *,
    ingredient_disposition: D = D.AGREEMENT,
    ingredient_score: float = 0.3,
) -> MatchCandidate:
    neutral = {
        K.STRENGTH: 0.1,
        K.UNIT: 0.05,
        K.FORM: 0.05,
        K.ROUTE: 0.05,
        K.LEXICAL: 0.1,
        K.SEMANTIC: 0.0,
        K.RXNORM: 0.05,
        K.TEMPORAL: 0.05,
    }
    features = MatchFeatures(
        mapping_level=MappingLevel.MEDICINAL_PRODUCT,
        identifiers=feature(K.IDENTIFIER, D.AGREEMENT, 0.25, "ID agrees"),
        ingredients=feature(
            K.INGREDIENT,
            ingredient_disposition,
            ingredient_score,
            "Ingredient evidence",
        ),
        strength=feature(K.STRENGTH, D.AGREEMENT, neutral[K.STRENGTH], "ok"),
        unit=feature(K.UNIT, D.AGREEMENT, neutral[K.UNIT], "ok"),
        form=feature(K.FORM, D.AGREEMENT, neutral[K.FORM], "ok"),
        route=feature(K.ROUTE, D.AGREEMENT, neutral[K.ROUTE], "ok"),
        lexical=feature(K.LEXICAL, D.AGREEMENT, neutral[K.LEXICAL], "ok"),
        semantic=feature(
            K.SEMANTIC, D.NOT_APPLICABLE, neutral[K.SEMANTIC], "unused"
        ),
        rxnorm=feature(K.RXNORM, D.AGREEMENT, neutral[K.RXNORM], "feature"),
        temporal=feature(K.TEMPORAL, D.AGREEMENT, neutral[K.TEMPORAL], "ok"),
        feature_version="v1",
        evaluated_at=datetime(2026, 7, 29, tzinfo=UTC),
    )
    return MatchCandidate(
        candidate_id="candidate-1",
        source_concept_id="nz-1",
        target_concept_id="au-1",
        source_jurisdiction="NZ",
        target_jurisdiction="AU",
        mapping_level=MappingLevel.MEDICINAL_PRODUCT,
        features=features,
        index_version="index-v1",
        model_version="reference-v1",
    )


def test_strong_candidate_is_still_pending_human_review() -> None:
    result = ReviewOnlyPolicy().evaluate(_candidate())
    assert result.review_state is ReviewState.PENDING_REVIEW
    assert result.confidence == pytest.approx(1.0)
    assert result.abstained is False
    assert result.reason_codes == (
        PolicyReason.REVIEW_REQUIRED,
        PolicyReason.AMBIGUOUS_SCORE,
    )
    assert result.policy_version == "review-only-v1"


def test_core_conflict_forces_abstention_and_explains_reason() -> None:
    result = ReviewOnlyPolicy().evaluate(
        _candidate(
            ingredient_disposition=D.CONFLICT,
            ingredient_score=-0.4,
        )
    )
    assert result.review_state is ReviewState.PENDING_REVIEW
    assert result.abstained
    assert result.confidence == pytest.approx(0.3)
    assert result.reason_codes == (
        PolicyReason.REVIEW_REQUIRED,
        PolicyReason.INGREDIENT_CONFLICT,
        PolicyReason.INSUFFICIENT_EVIDENCE,
    )


def test_invalid_threshold_and_semantic_only_candidates_fail_closed() -> None:
    with pytest.raises(ValueError, match="review_threshold"):
        ReviewOnlyPolicy(review_threshold=0)

    candidate = _candidate()
    semantic_only = candidate.features.model_copy(
        update={
            "identifiers": feature(K.IDENTIFIER, D.MISSING, 0, "Missing"),
            "ingredients": feature(K.INGREDIENT, D.MISSING, 0, "Missing"),
            "strength": feature(K.STRENGTH, D.MISSING, 0, "Missing"),
            "unit": feature(K.UNIT, D.MISSING, 0, "Missing"),
            "form": feature(K.FORM, D.MISSING, 0, "Missing"),
            "route": feature(K.ROUTE, D.MISSING, 0, "Missing"),
            "semantic": feature(K.SEMANTIC, D.AGREEMENT, 0.4, "Vector"),
            "rxnorm": feature(K.RXNORM, D.AGREEMENT, 0.4, "RxNorm"),
        }
    )
    result = ReviewOnlyPolicy().evaluate(
        candidate.model_copy(update={"features": semantic_only})
    )
    assert result.abstained
    assert PolicyReason.MISSING_CORE_EVIDENCE in result.reason_codes
    assert PolicyReason.SEMANTIC_ONLY in result.reason_codes
    assert PolicyReason.RXNORM_ONLY in result.reason_codes


@pytest.mark.parametrize("threshold", [0, -0.01, 1.01])
def test_review_threshold_rejects_values_outside_half_open_interval(
    threshold: float,
) -> None:
    with pytest.raises(ValueError, match=r"\(0, 1\]"):
        ReviewOnlyPolicy(review_threshold=threshold)


def test_review_threshold_accepts_one_and_preserves_custom_version() -> None:
    result = ReviewOnlyPolicy(
        review_threshold=1,
        policy_version="strict-v2",
    ).evaluate(_candidate())

    assert result.abstained is False
    assert result.policy_version == "strict-v2"


def test_confidence_equal_to_threshold_is_reviewable_not_insufficient() -> None:
    candidate = _candidate(ingredient_score=-0.05)

    result = ReviewOnlyPolicy(review_threshold=0.65).evaluate(candidate)

    assert result.confidence == pytest.approx(0.65)
    assert result.abstained is False
    assert result.reason_codes == (
        PolicyReason.REVIEW_REQUIRED,
        PolicyReason.AMBIGUOUS_SCORE,
    )


def test_confidence_below_threshold_abstains_with_exact_reason_order() -> None:
    candidate = _candidate(ingredient_score=-0.06)

    result = ReviewOnlyPolicy(review_threshold=0.65).evaluate(candidate)

    assert result.confidence == pytest.approx(0.64)
    assert result.abstained is True
    assert result.reason_codes == (
        PolicyReason.REVIEW_REQUIRED,
        PolicyReason.INSUFFICIENT_EVIDENCE,
    )


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        (K.IDENTIFIER, PolicyReason.IDENTIFIER_CONFLICT),
        (K.INGREDIENT, PolicyReason.INGREDIENT_CONFLICT),
        (K.STRENGTH, PolicyReason.STRENGTH_CONFLICT),
        (K.UNIT, PolicyReason.UNIT_CONFLICT),
        (K.FORM, PolicyReason.FORM_CONFLICT),
        (K.ROUTE, PolicyReason.ROUTE_CONFLICT),
        (K.TEMPORAL, PolicyReason.TEMPORAL_CONFLICT),
    ],
)
def test_every_blocking_conflict_maps_to_its_policy_reason(
    kind: K,
    reason: PolicyReason,
) -> None:
    candidate = _candidate()
    slot = {
        K.IDENTIFIER: "identifiers",
        K.INGREDIENT: "ingredients",
        K.STRENGTH: "strength",
        K.UNIT: "unit",
        K.FORM: "form",
        K.ROUTE: "route",
        K.TEMPORAL: "temporal",
    }[kind]
    conflicting = candidate.features.model_copy(
        update={
            slot: feature(kind, D.CONFLICT, 0, f"{kind.value} conflict"),
        }
    )

    result = ReviewOnlyPolicy().evaluate(
        candidate.model_copy(update={"features": conflicting})
    )

    assert result.abstained is True
    assert reason in result.reason_codes
    assert result.reason_codes.count(reason) == 1


def test_one_present_core_feature_prevents_missing_core_classification() -> (
    None
):
    candidate = _candidate()
    missing = {
        slot: feature(kind, D.MISSING, 0, "Missing")
        for slot, kind in (
            ("identifiers", K.IDENTIFIER),
            ("ingredients", K.INGREDIENT),
            ("strength", K.STRENGTH),
            ("unit", K.UNIT),
            ("form", K.FORM),
            ("route", K.ROUTE),
        )
    }
    missing["ingredients"] = feature(
        K.INGREDIENT,
        D.AGREEMENT,
        0.65,
        "Present",
    )
    features = candidate.features.model_copy(update=missing)

    result = ReviewOnlyPolicy().evaluate(
        candidate.model_copy(update={"features": features})
    )

    assert result.abstained is False
    assert PolicyReason.MISSING_CORE_EVIDENCE not in result.reason_codes
    assert PolicyReason.SEMANTIC_ONLY not in result.reason_codes
    assert PolicyReason.RXNORM_ONLY not in result.reason_codes
