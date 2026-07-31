"""Fail-closed comparison-validity evaluation.

Verdicts qualify only whether two evidence records may be compared for the
stated analytical purpose. They never establish clinical equivalence.
"""

from __future__ import annotations

from itertools import combinations

from .product_contracts import (
    ComparisonDimensionState,
    ComparisonValidity,
    ComparisonValidityDimension,
    ComparisonValidityDimensions,
    ComparisonValidityOutcome,
    ProductConclusion,
)


def evaluate_comparison_validity(
    *,
    left_subject_id: str,
    right_subject_id: str,
    dimensions: ComparisonValidityDimensions,
) -> ComparisonValidity:
    """Derive the only permitted outcome from explicit dimensional evidence."""
    named = (
        ("granularity", dimensions.granularity),
        ("indication", dimensions.indication),
        ("population", dimensions.population),
        ("mapping", dimensions.mapping),
        ("normalization", dimensions.normalization),
    )
    mismatches = tuple(
        name
        for name, dimension in named
        if dimension.state is ComparisonDimensionState.MISMATCH
    )
    states = {dimension.state for _, dimension in named}
    if mismatches:
        outcome = ComparisonValidityOutcome.INAPPROPRIATE_COMPARISON
        explanation = (
            "Status comparison is inappropriate because material dimensions "
            f"differ: {', '.join(mismatches)}."
        )
    elif ComparisonDimensionState.UNKNOWN in states:
        outcome = ComparisonValidityOutcome.INSUFFICIENT_EVIDENCE
        explanation = (
            "Status comparison is not qualified because one or more material "
            "dimensions lack explicit evidence."
        )
    elif ComparisonDimensionState.COMPATIBLE in states:
        outcome = ComparisonValidityOutcome.VALID_WITH_CAVEATS
        explanation = (
            "Evidence supports a bounded status comparison with stated "
            "dimensional caveats only."
        )
    else:
        outcome = ComparisonValidityOutcome.VALID
        explanation = (
            "Evidence supports a bounded status comparison at the stated "
            "dimensions only."
        )
    return ComparisonValidity(
        left_subject_id=left_subject_id,
        right_subject_id=right_subject_id,
        outcome=outcome,
        dimensions=dimensions,
        material_mismatches=mismatches,
        explanation=explanation,
    )


def abstaining_status_comparison_validity(
    conclusions: tuple[ProductConclusion, ...],
) -> tuple[ComparisonValidity, ...]:
    """Expose honest abstentions when status rows lack validity dimensions."""
    unknown = ComparisonValidityDimension(
        state=ComparisonDimensionState.UNKNOWN
    )
    dimensions = ComparisonValidityDimensions(
        granularity=unknown,
        indication=unknown,
        population=unknown,
        mapping=unknown,
        normalization=unknown,
    )
    assessments: list[ComparisonValidity] = []
    grouped: dict[str, list[ProductConclusion]] = {}
    for conclusion in conclusions:
        grouped.setdefault(conclusion.dimension.value, []).append(conclusion)
    for dimension, items in sorted(grouped.items()):
        ordered = sorted(items, key=lambda item: item.jurisdiction)
        for left, right in combinations(ordered, 2):
            if left.jurisdiction == right.jurisdiction:
                continue
            assessments.append(
                evaluate_comparison_validity(
                    left_subject_id=(
                        f"{left.concept_id}:{left.jurisdiction}:{dimension}"
                    ),
                    right_subject_id=(
                        f"{right.concept_id}:{right.jurisdiction}:{dimension}"
                    ),
                    dimensions=dimensions,
                )
            )
    return tuple(assessments)
