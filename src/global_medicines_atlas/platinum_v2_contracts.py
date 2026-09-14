"""Additive v2 contracts for dimensions absent from the stable v1 surface.

These models deliberately do not alter ``product_contracts``.  A future v2
transport can adopt them while existing v1 clients retain their fixed schema
and exhaustive enum handling.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from .product_contracts import (
    AsOfClocks,
    EvidenceAvailability,
    JurisdictionCode,
    NonBlank,
    PageMetadata,
    PageRequest,
    ProductModel,
    ProductState,
    ProvenanceLink,
    Terminology,
    Uncertainty,
)

V2_API_VERSION = "v2"
V2_API_BASE_PATH = f"/api/{V2_API_VERSION}"


class V2EvidenceDimension(StrEnum):
    """Five independent dimensions exposed only by the additive v2 surface."""

    SERVICE_BENEFIT = "service_benefit"
    FUNDING = "funding"
    REGULATORY = "regulatory"
    FORMULARY = "formulary"
    TERMINOLOGY = "terminology"


class V2ComparisonQuery(PageRequest, AsOfClocks):
    """Bounded comparison selection for a v2-compatible service adapter."""

    concept_id: NonBlank
    jurisdictions: tuple[JurisdictionCode, ...] = Field(
        min_length=1,
        max_length=50,
    )
    dimensions: tuple[V2EvidenceDimension, ...] = Field(
        min_length=1,
        max_length=5,
    )

    @model_validator(mode="after")
    def unique_filters(self) -> Self:
        if len(set(self.jurisdictions)) != len(self.jurisdictions):
            raise ValueError("jurisdictions must be unique")
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("dimensions must be unique")
        return self


class V2ResponseMetadata(ProductModel):
    """Response metadata that explicitly declares the additive API version."""

    api_version: Literal["v2"] = V2_API_VERSION
    generated_at: AwareDatetime
    clocks: AsOfClocks
    page: PageMetadata


class V2Conclusion(ProductModel):
    """One v2 evidence conclusion without collapsing its semantic dimension."""

    concept_id: NonBlank
    jurisdiction: JurisdictionCode
    dimension: V2EvidenceDimension
    state: ProductState
    status_code: NonBlank | None = None
    terminology: Terminology
    provenance: tuple[ProvenanceLink, ...] = ()
    evidence_availability: EvidenceAvailability
    evidence_unavailable_reason: NonBlank | None = None
    uncertainty: Uncertainty
    valid_time: AsOfClocks

    @model_validator(mode="after")
    def evidence_is_explicit(self) -> Self:
        if self.evidence_availability is EvidenceAvailability.AVAILABLE:
            if not self.provenance:
                raise ValueError(
                    "available evidence requires at least one provenance link",
                )
            if self.evidence_unavailable_reason is not None:
                raise ValueError(
                    "available evidence cannot have an unavailable reason",
                )
        elif self.evidence_availability is EvidenceAvailability.UNAVAILABLE:
            if self.provenance:
                raise ValueError(
                    "unavailable evidence cannot include provenance links",
                )
            if self.evidence_unavailable_reason is None:
                raise ValueError(
                    "unavailable evidence requires an explicit reason",
                )
        elif self.evidence_unavailable_reason is not None:
            raise ValueError(
                "not-required evidence cannot have an unavailable reason",
            )

        if (
            self.state
            in {
                ProductState.CONFIRMED,
                ProductState.INFERRED,
                ProductState.CONFLICTING,
            }
            and self.evidence_availability is not EvidenceAvailability.AVAILABLE
        ):
            raise ValueError(f"{self.state} conclusions require evidence")
        if (
            self.state in {ProductState.UNKNOWN, ProductState.NOT_COVERED}
            and self.status_code is not None
        ):
            raise ValueError(
                "unknown and not-covered conclusions cannot imply a status",
            )
        return self


class V2ComparisonResponse(ProductModel):
    """Additive v2 result envelope for independently scoped conclusions."""

    metadata: V2ResponseMetadata
    conclusions: tuple[V2Conclusion, ...]

    @model_validator(mode="after")
    def page_matches_conclusions(self) -> Self:
        if self.metadata.page.returned != len(self.conclusions):
            raise ValueError("page returned count must match conclusions")
        return self


__all__ = [
    "V2_API_BASE_PATH",
    "V2_API_VERSION",
    "V2ComparisonQuery",
    "V2ComparisonResponse",
    "V2Conclusion",
    "V2EvidenceDimension",
    "V2ResponseMetadata",
]
