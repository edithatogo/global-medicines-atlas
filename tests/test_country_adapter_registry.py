"""Reusable jurisdiction adapter registry tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from global_medicines_atlas.countries import (
    AdapterRegistry,
    JurisdictionSource,
    SourceDimension,
    builtin_registry,
)


@dataclass(frozen=True)
class EmptyAdapter:
    jurisdiction: str
    sources: tuple[JurisdictionSource, ...]

    def canonical_records(self):
        return ()


def source(jurisdiction: str, dimension: SourceDimension) -> JurisdictionSource:
    return JurisdictionSource(
        source_id=f"{jurisdiction.lower()}-{dimension}",
        jurisdiction=jurisdiction,
        authority="Example authority",
        dimension=dimension,
        homepage="https://example.invalid",
        coverage_note="Contract-only fixture.",
    )


def test_registry_accepts_any_jurisdiction_with_regulatory_source() -> None:
    registry = AdapterRegistry()
    registry.register(
        EmptyAdapter(
            jurisdiction="NZ",
            sources=(
                source("NZ", SourceDimension.REGULATORY),
                source("NZ", SourceDimension.FUNDING),
            ),
        )
    )

    assert registry.jurisdictions() == ("NZ",)
    assert registry.get("nz").jurisdiction == "NZ"


def test_registry_rejects_missing_regulatory_dimension() -> None:
    registry = AdapterRegistry()
    with pytest.raises(ValueError, match="regulatory"):
        registry.register(
            EmptyAdapter(
                jurisdiction="NZ",
                sources=(source("NZ", SourceDimension.FUNDING),),
            )
        )


def test_registry_rejects_duplicate_jurisdiction() -> None:
    registry = AdapterRegistry()
    adapter = EmptyAdapter(
        jurisdiction="AU",
        sources=(source("AU", SourceDimension.REGULATORY),),
    )
    registry.register(adapter)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(adapter)


def test_builtin_registry_covers_representative_first_cohort() -> None:
    registry = builtin_registry()

    assert registry.jurisdictions() == (
        "AUS",
        "CAN",
        "EU",
        "GBR",
        "JPN",
        "NZL",
        "USA",
    )
    assert tuple(registry.get("AUS").canonical_records()) == ()


def test_builtin_sources_do_not_conflate_regulation_and_funding() -> None:
    registry = builtin_registry()
    nz_sources = registry.get("NZL").sources

    regulatory = [
        source
        for source in nz_sources
        if source.dimension == SourceDimension.REGULATORY
    ]
    funding = [
        source
        for source in nz_sources
        if source.dimension == SourceDimension.FUNDING
    ]
    assert [source.source_id for source in regulatory] == ["nz-medsafe"]
    assert [source.source_id for source in funding] == ["nz-pharmac"]
