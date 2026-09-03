"""Dependency-light closed semantic types shared by Platinum boundaries."""

from __future__ import annotations

from typing import Literal

RESOURCE_ID_PATTERN = r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$"

SemanticDimension = Literal[
    "service_benefit", "funding", "formulary", "regulatory", "terminology"
]
EntityGranularity = Literal[
    "service_item",
    "medicine_item",
    "evidence_edge",
    "history_event",
    "coverage_record",
    "provenance_record",
]
Capability = Literal[
    "exact_v4_resolution",
    "anonymous_verified_read",
    "verified_cache_offline",
]

__all__ = [
    "RESOURCE_ID_PATTERN",
    "Capability",
    "EntityGranularity",
    "SemanticDimension",
]
