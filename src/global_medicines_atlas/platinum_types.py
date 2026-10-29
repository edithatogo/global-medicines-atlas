"""Dependency-light closed semantic types shared by Platinum boundaries."""

from __future__ import annotations

from typing import Literal

MAX_QUERY_OFFSET = 100_000_000
RESOURCE_ID_PATTERN = r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$"

SemanticDimension = Literal[
    "service_benefit",
    "funding",
    "formulary",
    "regulatory",
    "terminology",
]
PlatinumSemanticDimension = Literal[
    "service_benefit",
    "funding",
    "formulary",
    "regulatory",
    "terminology",
    "source_structure",
]
V1EntityGranularity = Literal[
    "service_item",
    "medicine_item",
    "evidence_edge",
    "history_event",
    "coverage_record",
    "provenance_record",
]
EntityGranularity = Literal[V1EntityGranularity, "source_record"]
Capability = Literal[
    "exact_v4_resolution",
    "anonymous_verified_read",
    "verified_cache_offline",
]


def validate_granularity_dimension(
    dimension: PlatinumSemanticDimension, granularity: EntityGranularity
) -> None:
    """Keep generic native source records out of domain-specific claims."""
    if granularity == "source_record" and dimension != "source_structure":
        raise ValueError("source records require source-structure semantics")


__all__ = [
    "MAX_QUERY_OFFSET",
    "RESOURCE_ID_PATTERN",
    "Capability",
    "EntityGranularity",
    "PlatinumSemanticDimension",
    "SemanticDimension",
    "V1EntityGranularity",
    "validate_granularity_dimension",
]
