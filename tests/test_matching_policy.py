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
    assert not result.abstained
    assert PolicyReason.REVIEW_REQUIRED in result.reason_codes
    assert PolicyReason.AMBIGUOUS_SCORE in result.reason_codes


def test_core_conflict_forces_abstention_and_explains_reason() -> None:
    result = ReviewOnlyPolicy().evaluate(
        _candidate(
            ingredient_disposition=D.CONFLICT,
            ingredient_score=-0.4,
        )
    )
    assert result.review_state is ReviewState.PENDING_REVIEW
    assert result.abstained
    assert PolicyReason.INGREDIENT_CONFLICT in result.reason_codes
    assert PolicyReason.INSUFFICIENT_EVIDENCE in result.reason_codes


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
