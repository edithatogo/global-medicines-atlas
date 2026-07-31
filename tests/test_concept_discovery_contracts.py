"""Unit contracts for deterministic, non-equivalence concept discovery."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from global_medicines_atlas.product_contracts import (
    ConceptSearchQuery,
    MatchExplanation,
    MatchMethod,
)


def test_search_query_is_bounded_and_normalizes_jurisdictions() -> None:
    query = ConceptSearchQuery(
        query="  acetaminophen  ", jurisdictions=("nz", "AU"), limit=10
    )

    assert query.query == "acetaminophen"
    assert query.jurisdictions == ("NZ", "AU")


@pytest.mark.parametrize("query", ["", " ", "x" * 201])
def test_search_query_rejects_empty_or_unbounded_input(query: str) -> None:
    with pytest.raises(ValidationError):
        ConceptSearchQuery(query=query)


def test_search_query_rejects_duplicate_jurisdictions() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        ConceptSearchQuery(query="aspirin", jurisdictions=("NZ", "nz"))


@pytest.mark.parametrize("method", list(MatchMethod))
def test_match_explanation_never_establishes_equivalence(
    method: MatchMethod,
) -> None:
    explanation = MatchExplanation(
        method=method,
        matched_value="Aspirin",
        normalized_query="aspirin",
    )

    assert explanation.establishes_equivalence is False


def test_match_explanation_cannot_claim_equivalence() -> None:
    with pytest.raises(ValidationError):
        MatchExplanation(
            method=MatchMethod.EXACT_CONCEPT_ID,
            matched_value="rx:1",
            normalized_query="rx 1",
            establishes_equivalence=True,
        )
