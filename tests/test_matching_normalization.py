import pytest

from global_medicines_atlas.matching_normalization import (
    build_features,
    normalize_text,
)


def test_unicode_normalization_is_reversible() -> None:
    value = "  Cafe\u0301  医薬品  500 MG "
    normalized = normalize_text(value)

    assert normalized.source == value
    assert "医薬品" in normalized.tokens
    assert normalized.unicode_text != value


def test_features_remain_explicit_and_units_are_canonical() -> None:
    features = build_features(
        name="Paracetamol tablet",
        ingredients=("Paracetamol",),
        strength_value="500.0",
        strength_unit="milligrams",
        dose_form="Film-coated tablet",
        route="Oral",
    )

    assert features.strength_value == "500"
    assert features.strength_unit == "mg"
    assert features.ingredients[0].source == "Paracetamol"
    assert features.dose_form is not None
    assert features.route is not None


def test_blank_normalization_is_rejected() -> None:
    with pytest.raises(ValueError, match="blank"):
        normalize_text("   ")
