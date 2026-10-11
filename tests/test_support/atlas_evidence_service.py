"""Synthetic Atlas service used by installed-distribution browser E2E."""

from __future__ import annotations

from datetime import UTC, datetime

from global_medicines_atlas.platinum_v2_contracts import (
    V2ComparisonQuery,
    V2ComparisonResponse,
    V2Conclusion,
    V2ResponseMetadata,
)
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    ComparisonQuery,
    ComparisonResponse,
    ConceptDetail,
    ConceptSearchQuery,
    ConceptSearchResponse,
    ConceptSummary,
    CoverageItem,
    CoverageQuery,
    CoverageResponse,
    DiscoveryMetadata,
    EvidenceAvailability,
    EvidenceContext,
    EvidenceDimension,
    MatchExplanation,
    MatchMethod,
    PageMetadata,
    ProductConclusion,
    ProductState,
    ProvenanceLink,
    ResponseMetadata,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


class InstalledAtlasEvidenceService:
    """Small synthetic service that preserves unknown evidence semantics."""

    def concept_detail(self, concept_id: str) -> ConceptDetail:
        return ConceptDetail(
            concept_id=concept_id,
            preferred_name="Example medicine",
            concept_type="medicinal_product",
        )

    def search_concepts(
        self, query: ConceptSearchQuery
    ) -> ConceptSearchResponse:
        return ConceptSearchResponse(
            metadata=DiscoveryMetadata(
                generated_at=NOW,
                page=PageMetadata(limit=query.limit, returned=1),
            ),
            concepts=(
                ConceptSummary(
                    concept_id="rx:fixture",
                    preferred_name="Example medicine",
                    concept_type="medicinal_product",
                    jurisdictions=("NZ",),
                    explanation=MatchExplanation(
                        method=MatchMethod.NORMALIZED_PREFERRED_NAME,
                        matched_value="Example medicine",
                        normalized_query=query.query.casefold(),
                    ),
                ),
            ),
        )

    def comparisons(self, query: ComparisonQuery) -> ComparisonResponse:
        conclusion = ProductConclusion(
            concept_id=query.concept_id,
            jurisdiction="NZ",
            dimension=EvidenceDimension.REGULATORY,
            state=ProductState.UNKNOWN,
            terminology=Terminology(
                native_code="unknown",
                native_label="No source assertion in this synthetic fixture",
                native_system="fixture",
                canonical_code=query.concept_id,
                canonical_label="Example medicine",
                canonical_system="atlas",
            ),
            provenance=(
                ProvenanceLink(
                    source_id="Synthetic public evidence",
                    source_uri="https://fixtures.invalid/evidence",
                    retrieved_at=NOW,
                ),
            ),
            evidence_availability=EvidenceAvailability.AVAILABLE,
            uncertainty=Uncertainty(
                level=UncertaintyLevel.UNKNOWN,
                reason="No source assertion is present in this fixture.",
            ),
            evidence_context=EvidenceContext(
                schema_era="fixture-v1",
                comparison_cohort="synthetic",
                entity_granularity="medicine_item",
            ),
            valid_time=AsOfClocks(
                valid_at=query.valid_at,
                observed_at=query.observed_at,
            ),
        )
        return ComparisonResponse(
            metadata=ResponseMetadata(
                generated_at=NOW,
                clocks=AsOfClocks(
                    valid_at=query.valid_at,
                    observed_at=query.observed_at,
                ),
                page=PageMetadata(limit=query.limit, returned=1),
            ),
            conclusions=(conclusion,),
        )

    def coverage(self, query: CoverageQuery) -> CoverageResponse:
        item = CoverageItem(
            jurisdiction="NZ",
            dimension=EvidenceDimension.REGULATORY,
            state=ProductState.UNKNOWN,
            covered_count=0,
            evidence_context=EvidenceContext(
                schema_era="fixture-v1",
                comparison_cohort="synthetic",
                entity_granularity="coverage_record",
            ),
            valid_time=AsOfClocks(
                valid_at=query.valid_at,
                observed_at=query.observed_at,
            ),
        )
        return CoverageResponse(
            metadata=ResponseMetadata(
                generated_at=NOW,
                clocks=AsOfClocks(
                    valid_at=query.valid_at,
                    observed_at=query.observed_at,
                ),
                page=PageMetadata(limit=query.limit, returned=1),
            ),
            coverage=(item,),
        )

    def v2_comparisons(self, query: V2ComparisonQuery) -> V2ComparisonResponse:
        clocks = AsOfClocks(
            valid_at=query.valid_at,
            observed_at=query.observed_at,
        )
        conclusions = tuple(
            V2Conclusion(
                concept_id=query.concept_id,
                jurisdiction=jurisdiction,
                dimension=dimension,
                state=ProductState.UNKNOWN,
                terminology=Terminology(
                    native_code=dimension.value,
                    native_label=f"No source assertion for {dimension.value}",
                    native_system="synthetic-fixture",
                ),
                evidence_availability=EvidenceAvailability.UNAVAILABLE,
                evidence_unavailable_reason=(
                    "No source assertion is present in this fixture."
                ),
                uncertainty=Uncertainty(
                    level=UncertaintyLevel.UNKNOWN,
                    reason="Synthetic v2 fixture has no dimension evidence.",
                ),
                evidence_context=EvidenceContext(
                    schema_era="fixture-v2",
                    comparison_cohort="synthetic",
                    entity_granularity="medicine_item",
                ),
                valid_time=clocks,
            )
            for jurisdiction in query.jurisdictions
            for dimension in query.dimensions
        )
        return V2ComparisonResponse(
            metadata=V2ResponseMetadata(
                generated_at=NOW,
                clocks=clocks,
                page=PageMetadata(
                    limit=query.limit,
                    returned=len(conclusions),
                ),
            ),
            conclusions=conclusions,
            comparison_validity=(),
            validity_completeness="partial",
        )
