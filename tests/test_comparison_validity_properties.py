"""Property invariants for comparison-validity abstention and claims."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from global_medicines_atlas.comparison_validity import (
    evaluate_comparison_validity,
)
from global_medicines_atlas.product_contracts import (
    ComparisonDimensionState,
    ComparisonValidityDimension,
    ComparisonValidityDimensions,
    ComparisonValidityOutcome,
)

DIMENSION_NAMES = (
    "granularity",
    "indication",
    "population",
    "mapping",
    "normalization",
)


def observed(state: ComparisonDimensionState) -> ComparisonValidityDimension:
    if state is ComparisonDimensionState.UNKNOWN:
        return ComparisonValidityDimension(state=state)
    return ComparisonValidityDimension(
        state=state,
        left_value="left",
        right_value="right",
        evidence_ids=("source:record",),
    )


@given(
    states=st.lists(
        st.sampled_from(list(ComparisonDimensionState)),
        min_size=5,
        max_size=5,
    )
)
def test_outcome_precedence_and_clinical_claims_are_invariant(
    states: list[ComparisonDimensionState],
) -> None:
    dimensions = ComparisonValidityDimensions.model_validate(
        dict(zip(DIMENSION_NAMES, map(observed, states), strict=True))
    )
    verdict = evaluate_comparison_validity(
        left_subject_id="left:subject",
        right_subject_id="right:subject",
        dimensions=dimensions,
    )

    if ComparisonDimensionState.MISMATCH in states:
        assert (
            verdict.outcome
            is ComparisonValidityOutcome.INAPPROPRIATE_COMPARISON
        )
    elif ComparisonDimensionState.UNKNOWN in states:
        assert (
            verdict.outcome is ComparisonValidityOutcome.INSUFFICIENT_EVIDENCE
        )
    elif ComparisonDimensionState.COMPATIBLE in states:
        assert verdict.outcome is ComparisonValidityOutcome.VALID_WITH_CAVEATS
    else:
        assert verdict.outcome is ComparisonValidityOutcome.VALID
    assert not any((
        verdict.establishes_medicine_equivalence,
        verdict.establishes_substitutability,
        verdict.establishes_therapeutic_interchangeability,
        verdict.establishes_equal_benefit,
    ))
