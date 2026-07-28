"""Transparent lexical feature comparison."""

from __future__ import annotations

from difflib import SequenceMatcher

from pydantic import Field

from .matching_normalization import MatchingFeatures
from .models import FrozenModel


class LexicalEvidence(FrozenModel):
    feature: str = Field(min_length=1)
    source_value: str | None
    target_value: str | None
    score: float = Field(ge=0, le=1)
    compatible: bool | None = None


def _ratio(left: str, right: str) -> float:
    return round(SequenceMatcher(None, left, right, autojunk=False).ratio(), 6)


def compare_features(
    source: MatchingFeatures, target: MatchingFeatures
) -> tuple[LexicalEvidence, ...]:
    source_ingredients = "|".join(
        item.comparison_text for item in source.ingredients
    )
    target_ingredients = "|".join(
        item.comparison_text for item in target.ingredients
    )
    pairs = (
        ("name", source.name.comparison_text, target.name.comparison_text),
        ("ingredients", source_ingredients, target_ingredients),
        ("strength", source.strength_value, target.strength_value),
        ("unit", source.strength_unit, target.strength_unit),
        (
            "form",
            source.dose_form.comparison_text if source.dose_form else None,
            target.dose_form.comparison_text if target.dose_form else None,
        ),
        (
            "route",
            source.route.comparison_text if source.route else None,
            target.route.comparison_text if target.route else None,
        ),
    )
    evidence: list[LexicalEvidence] = []
    for feature, left, right in pairs:
        if left is None or right is None or not left or not right:
            score = 0.0
            compatible = None
        else:
            score = 1.0 if left == right else _ratio(left, right)
            compatible = left == right
        evidence.append(
            LexicalEvidence(
                feature=feature,
                source_value=left,
                target_value=right,
                score=score,
                compatible=compatible,
            )
        )
    return tuple(evidence)


def lexical_score(evidence: tuple[LexicalEvidence, ...]) -> float:
    weights = {
        "name": 0.30,
        "ingredients": 0.35,
        "strength": 0.15,
        "unit": 0.05,
        "form": 0.10,
        "route": 0.05,
    }
    available = [
        (item, weights[item.feature])
        for item in evidence
        if item.compatible is not None
    ]
    if not available:
        return 0.0
    total_weight = sum(weight for _, weight in available)
    return round(
        sum(item.score * weight for item, weight in available) / total_weight,
        6,
    )
