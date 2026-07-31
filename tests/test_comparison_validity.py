"""Unit negative controls for comparison validity."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from global_medicines_atlas.comparison_validity import (
    evaluate_comparison_validity,
)
from global_medicines_atlas.product_contracts import (
    ComparisonDimensionState,
    ComparisonValidity,
    ComparisonValidityDimension,
    ComparisonValidityDimensions,
    ComparisonValidityOutcome,
)


def dimension(
    state: ComparisonDimensionState,
    *,
    left: str = "left",
    right: str = "right",
) -> ComparisonValidityDimension:
    if state is ComparisonDimensionState.UNKNOWN:
        return ComparisonValidityDimension(state=state)
    return ComparisonValidityDimension(
        state=state,
        left_value=left,
        right_value=right,
        evidence_ids=(f"evidence:{state.value}",),
    )


def dimensions(
    **overrides: ComparisonDimensionState,
) -> ComparisonValidityDimensions:
    values = {
        name: dimension(overrides.get(name, ComparisonDimensionState.ALIGNED))
        for name in (
            "granularity",
            "indication",
            "population",
            "mapping",
            "normalization",
        )
    }
    return ComparisonValidityDimensions.model_validate(values)


@pytest.mark.parametrize(
    "mismatch",
    ["granularity", "indication", "population", "mapping", "normalization"],
)
def test_each_material_mismatch_rejects_comparison(mismatch: str) -> None:
    verdict = evaluate_comparison_validity(
        left_subject_id="nz:medicine",
        right_subject_id="au:medicine",
        dimensions=dimensions(**{mismatch: ComparisonDimensionState.MISMATCH}),
    )

    assert verdict.outcome is ComparisonValidityOutcome.INAPPROPRIATE_COMPARISON
    assert verdict.material_mismatches == (mismatch,)
    assert not verdict.establishes_medicine_equivalence
    assert not verdict.establishes_substitutability
    assert not verdict.establishes_therapeutic_interchangeability
    assert not verdict.establishes_equal_benefit


def test_unknown_dimension_abstains_with_provenance_preserved() -> None:
    verdict = evaluate_comparison_validity(
        left_subject_id="nz:medicine",
        right_subject_id="us:medicine",
        dimensions=dimensions(population=ComparisonDimensionState.UNKNOWN),
    )

    assert verdict.outcome is ComparisonValidityOutcome.INSUFFICIENT_EVIDENCE
    assert verdict.dimensions.granularity.evidence_ids
    assert verdict.dimensions.population.evidence_ids == ()


def test_compatible_dimension_only_allows_caveated_status_comparison() -> None:
    verdict = evaluate_comparison_validity(
        left_subject_id="nz:medicine",
        right_subject_id="ca:medicine",
        dimensions=dimensions(indication=ComparisonDimensionState.COMPATIBLE),
    )

    assert verdict.outcome is ComparisonValidityOutcome.VALID_WITH_CAVEATS
    assert "status comparison" in verdict.explanation.lower()


def test_forged_outcome_and_missing_evidence_fail_closed() -> None:
    with pytest.raises(ValidationError, match="require evidence"):
        ComparisonValidityDimension(
            state=ComparisonDimensionState.MISMATCH,
            left_value="tablet",
            right_value="injection",
        )

    valid = evaluate_comparison_validity(
        left_subject_id="nz:medicine",
        right_subject_id="au:medicine",
        dimensions=dimensions(mapping=ComparisonDimensionState.MISMATCH),
    )
    payload = valid.model_dump()
    payload["outcome"] = "valid"
    with pytest.raises(ValidationError, match="outcome"):
        ComparisonValidity.model_validate(payload)


def test_regulatory_and_funding_subjects_cannot_be_silently_merged() -> None:
    with pytest.raises(ValidationError, match="distinct"):
        evaluate_comparison_validity(
            left_subject_id="nz:medicine:regulatory",
            right_subject_id="nz:medicine:regulatory",
            dimensions=dimensions(),
        )


def test_runtime_verdict_conforms_to_versioned_json_schema() -> None:
    verdict = evaluate_comparison_validity(
        left_subject_id="nz:medicine:regulatory",
        right_subject_id="au:medicine:regulatory",
        dimensions=dimensions(population=ComparisonDimensionState.UNKNOWN),
    )
    schema = json.loads(
        Path("schemas/comparison-validity-v1.json").read_text(encoding="utf-8")
    )

    jsonschema.validate(verdict.model_dump(mode="json"), schema)
