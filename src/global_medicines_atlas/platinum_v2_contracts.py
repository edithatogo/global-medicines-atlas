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
    JurisdictionCode,
    NonBlank,
    PageMetadata,
    PageRequest,
    ProductModel,
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


__all__ = [
    "V2_API_BASE_PATH",
    "V2_API_VERSION",
    "V2ComparisonQuery",
    "V2EvidenceDimension",
    "V2ResponseMetadata",
]
