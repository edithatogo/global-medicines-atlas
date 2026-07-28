from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from global_medicines_atlas.matching_features import (
    FeatureDisposition,
    FeatureKind,
    MatchFeatures,
    feature,
    utc_now,
)
from global_medicines_atlas.matching_models import MappingLevel


def _features(**overrides: object) -> MatchFeatures:
    values = {
        "mapping_level": MappingLevel.MEDICINAL_PRODUCT,
        "identifiers": feature(
            FeatureKind.IDENTIFIER,
            FeatureDisposition.AGREEMENT,
            0.35,
            "Shared reviewed identifier",
        ),
        "ingredients": feature(
            FeatureKind.INGREDIENT,
            FeatureDisposition.AGREEMENT,
            0.25,
            "Ingredient sets agree",
        ),
        "strength": feature(
            FeatureKind.STRENGTH,
            FeatureDisposition.AGREEMENT,
            0.1,
            "Strength agrees",
        ),
        "unit": feature(
            FeatureKind.UNIT,
            FeatureDisposition.AGREEMENT,
            0.05,
            "Units agree",
        ),
        "form": feature(
            FeatureKind.FORM,
            FeatureDisposition.AGREEMENT,
            0.05,
            "Forms agree",
        ),
        "route": feature(
            FeatureKind.ROUTE,
            FeatureDisposition.MISSING,
            0,
            "Target route missing",
        ),
        "lexical": feature(
            FeatureKind.LEXICAL,
            FeatureDisposition.AGREEMENT,
            0.1,
            "Names are similar",
        ),
        "semantic": feature(
            FeatureKind.SEMANTIC,
            FeatureDisposition.NOT_APPLICABLE,
            0,
            "Semantic index unavailable",
        ),
        "rxnorm": feature(
            FeatureKind.RXNORM,
            FeatureDisposition.AGREEMENT,
            0.05,
            "Same RxNorm candidate",
        ),
        "temporal": feature(
            FeatureKind.TEMPORAL,
            FeatureDisposition.AGREEMENT,
            0.05,
            "Evidence periods overlap",
        ),
        "feature_version": "v1",
        "evaluated_at": datetime(2026, 7, 29, tzinfo=UTC),
    }
    values.update(overrides)
    return MatchFeatures.model_validate(values)


def test_features_explain_score_conflicts_and_missing_evidence() -> None:
    features = _features(
        penalties=(
            feature(
                FeatureKind.FORM,
                FeatureDisposition.CONFLICT,
                -0.2,
                "Modified-release form conflicts",
            ),
        )
    )
    assert features.raw_score == pytest.approx(0.8)
    assert FeatureKind.FORM in features.conflicts
    assert features.missing == (FeatureKind.ROUTE,)
    assert [item.kind for item in features.ordered_evidence[:3]] == [
        FeatureKind.IDENTIFIER,
        FeatureKind.INGREDIENT,
        FeatureKind.STRENGTH,
    ]


def test_feature_slots_and_penalties_fail_closed() -> None:
    with pytest.raises(ValidationError, match="identifiers must contain"):
        _features(
            identifiers=feature(
                FeatureKind.LEXICAL,
                FeatureDisposition.AGREEMENT,
                0.2,
                "Wrong slot",
            )
        )


def test_default_clock_is_timezone_aware() -> None:
    assert utc_now().tzinfo is not None
    with pytest.raises(ValidationError, match="non-positive"):
        _features(
            penalties=(
                feature(
                    FeatureKind.FORM,
                    FeatureDisposition.CONFLICT,
                    0.1,
                    "Invalid positive penalty",
                ),
            )
        )
