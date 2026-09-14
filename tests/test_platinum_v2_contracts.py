"""Compatibility-preserving v2 product-contract controls."""

from datetime import UTC, datetime

from global_medicines_atlas.platinum_v2_contracts import (
    V2ComparisonQuery,
    V2EvidenceDimension,
    V2ResponseMetadata,
)
from global_medicines_atlas.product_contracts import AsOfClocks, PageMetadata


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
