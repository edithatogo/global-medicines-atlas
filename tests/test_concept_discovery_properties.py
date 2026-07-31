"""Property tests for bounded deterministic discovery normalization."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from global_medicines_atlas.product_contracts import ConceptSearchQuery
from global_medicines_atlas.terminology import normalize_name


@given(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd", "Zs"),
            blacklist_characters=("\x00",),
        ),
        min_size=1,
        max_size=100,
    ).filter(lambda value: bool(value.strip()))
)
def test_normalization_is_idempotent_for_bounded_queries(value: str) -> None:
    query = ConceptSearchQuery(query=value)
    normalized = normalize_name(query.query)

    assert normalize_name(normalized) == normalized


@given(st.integers(min_value=1, max_value=250))
def test_page_bound_is_preserved(limit: int) -> None:
    assert ConceptSearchQuery(query="aspirin", limit=limit).limit == limit
