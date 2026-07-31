"""Metamorphic invariants for medicine normalization."""

from hypothesis import given
from hypothesis import strategies as st

from global_medicines_atlas.matching_normalization import (
    build_features,
    normalize_text,
)

_MEDICINE_WORDS = st.lists(
    st.from_regex(r"[A-Za-z][A-Za-z0-9]{0,11}", fullmatch=True),
    min_size=1,
    max_size=6,
).map(" ".join)


@given(_MEDICINE_WORDS)
def test_case_and_whitespace_transforms_preserve_comparison_identity(
    value: str,
) -> None:
    """Equivalent presentation changes must retain matching identity."""

    baseline = normalize_text(value).comparison_text
    transformed = f"\t {value.swapcase().replace(' ', '   ')} \n"

    assert normalize_text(transformed).comparison_text == baseline


@given(
    name=_MEDICINE_WORDS,
    ingredients=st.lists(_MEDICINE_WORDS, min_size=1, max_size=6, unique=True),
)
def test_ingredient_permutation_preserves_feature_identity(
    name: str,
    ingredients: list[str],
) -> None:
    """Source ordering must not alter canonical matching features."""

    forward = build_features(name=name, ingredients=tuple(ingredients))
    reverse = build_features(
        name=name, ingredients=tuple(reversed(ingredients))
    )

    assert forward == reverse


def test_normalization_collisions_do_not_retain_source_order() -> None:
    """Equivalent comparison forms use deterministic source tie-breakers."""

    forward = build_features(name="Combination", ingredients=("A", "a"))
    reverse = build_features(name="Combination", ingredients=("a", "A"))

    assert forward == reverse
