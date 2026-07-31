import pytest

from global_medicines_atlas.matching_normalization import (
    build_features,
    normalize_strength,
    normalize_text,
    normalize_unit,
)


def test_unicode_normalization_is_reversible() -> None:
    value = "  Cafe\u0301  医薬品  500 MG "
    normalized = normalize_text(value)

    assert normalized.source == value
    assert normalized.unicode_text == "  Café  医薬品  500 MG "
    assert normalized.comparison_text == "café 医薬品 500 mg"
    assert normalized.tokens == ("café", "医薬品", "500", "mg")


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
    assert features.name.comparison_text == "paracetamol tablet"
    assert tuple(item.source for item in features.ingredients) == (
        "Paracetamol",
    )
    assert features.dose_form is not None
    assert features.dose_form.comparison_text == "film coated tablet"
    assert features.route is not None
    assert features.route.comparison_text == "oral"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("milligram", "mg"),
        ("milligrams", "mg"),
        ("microgram", "μg"),
        ("micrograms", "μg"),
        ("mcg", "μg"),
        ("μg", "μg"),
        ("millilitre", "ml"),
        ("millilitres", "ml"),
        ("International Units", "international units"),
    ],
)
def test_unit_aliases_and_unknown_units_have_exact_canonical_forms(
    source: str,
    expected: str,
) -> None:
    assert normalize_unit(source) == expected


def test_optional_unit_and_strength_values_remain_absent() -> None:
    assert normalize_unit(None) is None
    assert normalize_strength(None) is None
    assert normalize_strength("  ") is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("500.0", "500"),
        ("0,125", "0.125"),
        (5, "5"),
        (2.5, "2.5"),
        ("1e-06", "1e-06"),
        ("five MG", "five mg"),
    ],
)
def test_strength_normalization_is_exact(
    source: str | int | float,
    expected: str,
) -> None:
    assert normalize_strength(source) == expected


def test_feature_construction_sorts_ingredients_by_comparison_text() -> None:
    features = build_features(
        name="Combination",
        ingredients=("zinc", "Ácido", "acetate"),
    )

    assert tuple(item.comparison_text for item in features.ingredients) == (
        "acetate",
        "zinc",
        "ácido",
    )
    assert features.strength_value is None
    assert features.strength_unit is None
    assert features.dose_form is None
    assert features.route is None


def test_tokenization_preserves_decimal_punctuation_but_not_symbols() -> None:
    normalized = normalize_text("  A+B 12.5,mg / dose  ")

    assert normalized.comparison_text == "a b 12.5,mg dose"
    assert normalized.tokens == ("a", "b", "12.5,mg", "dose")


def test_blank_normalization_is_rejected() -> None:
    with pytest.raises(ValueError, match="blank"):
        normalize_text("   ")


def test_symbol_only_normalization_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unicode word"):
        normalize_text(" + / — ")
