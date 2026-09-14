"""Compatibility-preserving v2 product-contract controls."""

from datetime import UTC, datetime

import pytest

from global_medicines_atlas.platinum_v2_contracts import (
    V2ComparisonQuery,
    V2ComparisonResponse,
    V2Conclusion,
    V2EvidenceDimension,
    V2ResponseMetadata,
)
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    EvidenceAvailability,
    PageMetadata,
    ProductState,
    ProvenanceLink,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)


def test_v2_adds_dimensions_without_changing_v1_contracts() -> None:
    assert {dimension.value for dimension in V2EvidenceDimension} == {
        "service_benefit",
        "funding",
        "regulatory",
        "formulary",
        "terminology",
    }
    clock = datetime(2026, 9, 14, tzinfo=UTC)
    query = V2ComparisonQuery(
        concept_id="rx:fixture",
        jurisdictions=("AU",),
        dimensions=(
            V2EvidenceDimension.SERVICE_BENEFIT,
            V2EvidenceDimension.TERMINOLOGY,
        ),
        valid_at=clock,
        observed_at=clock,
    )
    metadata = V2ResponseMetadata(
        generated_at=clock,
        clocks=AsOfClocks(valid_at=clock, observed_at=clock),
        page=PageMetadata(limit=10, returned=0),
    )

    assert query.dimensions[0] is V2EvidenceDimension.SERVICE_BENEFIT
    assert metadata.api_version == "v2"


@pytest.mark.parametrize(
    ("jurisdictions", "dimensions", "message"),
    [
        (
            ("AU", "AU"),
            (V2EvidenceDimension.FUNDING,),
            "jurisdictions must be unique",
        ),
        (
            ("AU",),
            (V2EvidenceDimension.FUNDING, V2EvidenceDimension.FUNDING),
            "dimensions must be unique",
        ),
    ],
)
def test_v2_comparison_rejects_duplicate_filters(
    jurisdictions: tuple[str, ...],
    dimensions: tuple[V2EvidenceDimension, ...],
    message: str,
) -> None:
    clock = datetime(2026, 9, 14, tzinfo=UTC)
    with pytest.raises(ValueError, match=message):
        V2ComparisonQuery(
            concept_id="rx:fixture",
            jurisdictions=jurisdictions,
            dimensions=dimensions,
            valid_at=clock,
            observed_at=clock,
        )


def test_v2_response_preserves_five_dimension_conclusions() -> None:
    clock = datetime(2026, 9, 14, tzinfo=UTC)
    clocks = AsOfClocks(valid_at=clock, observed_at=clock)
    response = V2ComparisonResponse(
        metadata=V2ResponseMetadata(
            generated_at=clock,
            clocks=clocks,
            page=PageMetadata(limit=10, returned=1),
        ),
        conclusions=(
            V2Conclusion(
                concept_id="mbs:23",
                jurisdiction="AU",
                dimension=V2EvidenceDimension.SERVICE_BENEFIT,
                state=ProductState.UNKNOWN,
                terminology=Terminology(
                    native_code="23",
                    native_label="General practitioner attendance",
                    native_system="MBS",
                ),
                evidence_availability=EvidenceAvailability.UNAVAILABLE,
                evidence_unavailable_reason="No source assertion is available.",
                uncertainty=Uncertainty(
                    level=UncertaintyLevel.UNKNOWN,
                    reason="Fixture has no source assertion.",
                ),
                valid_time=clocks,
            ),
        ),
    )

    assert response.metadata.api_version == "v2"
    assert (
        response.conclusions[0].dimension is V2EvidenceDimension.SERVICE_BENEFIT
    )


def test_v2_response_rejects_inconsistent_page_count() -> None:
    clock = datetime(2026, 9, 14, tzinfo=UTC)
    with pytest.raises(ValueError, match="returned count"):
        V2ComparisonResponse(
            metadata=V2ResponseMetadata(
                generated_at=clock,
                clocks=AsOfClocks(valid_at=clock, observed_at=clock),
                page=PageMetadata(limit=10, returned=1),
            ),
            conclusions=(),
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {
                "state": ProductState.CONFIRMED,
                "evidence_availability": EvidenceAvailability.UNAVAILABLE,
            },
            "confirmed conclusions require evidence",
        ),
        (
            {
                "evidence_availability": EvidenceAvailability.AVAILABLE,
                "evidence_unavailable_reason": None,
            },
            "available evidence requires at least one provenance link",
        ),
        (
            {
                "evidence_availability": EvidenceAvailability.AVAILABLE,
                "evidence_unavailable_reason": "Incorrectly supplied",
                "provenance": (
                    ProvenanceLink(
                        source_id="fixture",
                        source_uri="https://example.invalid/source",
                        retrieved_at=datetime(2026, 9, 14, tzinfo=UTC),
                    ),
                ),
            },
            "available evidence cannot have an unavailable reason",
        ),
        (
            {"evidence_unavailable_reason": None},
            "unavailable evidence requires an explicit reason",
        ),
        (
            {"status_code": "active"},
            "unknown and not-covered conclusions cannot imply a status",
        ),
        (
            {
                "provenance": (
                    ProvenanceLink(
                        source_id="fixture",
                        source_uri="https://example.invalid/source",
                        retrieved_at=datetime(2026, 9, 14, tzinfo=UTC),
                    ),
                ),
            },
            "unavailable evidence cannot include provenance links",
        ),
        (
            {
                "evidence_availability": EvidenceAvailability.NOT_REQUIRED,
            },
            "not-required evidence cannot have an unavailable reason",
        ),
    ],
)
def test_v2_conclusion_enforces_explicit_evidence(
    changes: dict[str, object], message: str
) -> None:
    clock = datetime(2026, 9, 14, tzinfo=UTC)
    values: dict[str, object] = {
        "concept_id": "mbs:23",
        "jurisdiction": "AU",
        "dimension": V2EvidenceDimension.SERVICE_BENEFIT,
        "state": ProductState.UNKNOWN,
        "terminology": Terminology(
            native_code="23",
            native_label="General practitioner attendance",
            native_system="MBS",
        ),
        "evidence_availability": EvidenceAvailability.UNAVAILABLE,
        "evidence_unavailable_reason": "No source assertion is available.",
        "uncertainty": Uncertainty(
            level=UncertaintyLevel.UNKNOWN,
            reason="Fixture has no source assertion.",
        ),
        "valid_time": AsOfClocks(valid_at=clock, observed_at=clock),
    }
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        V2Conclusion(**values)
