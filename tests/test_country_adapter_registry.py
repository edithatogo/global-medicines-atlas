"""Reusable jurisdiction adapter registry tests."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

import pytest

from global_medicines_atlas.countries import (
    AdapterRegistry,
    Capability,
    JurisdictionSource,
    SourceCapabilityDeclaration,
    SourceCapabilityRegistry,
    SourceDimension,
    builtin_registry,
    builtin_source_capabilities,
)
from global_medicines_atlas.source_catalog import load_source_catalog


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


def test_every_implementation_maps_to_exactly_one_catalog_source() -> None:
    catalog_ids = {source.source_id for source in load_source_catalog()}
    declarations = builtin_source_capabilities()
    implementation_ids = [
        implementation
        for declaration in declarations
        for implementation in declaration.implementations
    ]

    assert implementation_ids
    assert len(implementation_ids) == len(set(implementation_ids))
    assert all(
        declaration.source_id in catalog_ids for declaration in declarations
    )
    assert all(declaration.capabilities for declaration in declarations)
    declarations.validate_catalog(load_source_catalog())
    for implementation in implementation_ids:
        module_name, symbol_name = implementation.split(":", maxsplit=1)
        module = import_module(f"global_medicines_atlas.{module_name}")
        assert getattr(module, symbol_name)
        assert declarations.source_id_for(implementation) in catalog_ids


def test_capability_registry_rejects_implementation_aliasing() -> None:
    implementation = "adapters.example:parse"
    declarations = tuple(
        SourceCapabilityDeclaration(
            source_id=source_id,
            capabilities=frozenset({Capability.SOURCE_PARSER}),
            implementations=(implementation,),
        )
        for source_id in ("source-one", "source-two")
    )

    with pytest.raises(
        ValueError, match="maps to both source-one and source-two"
    ):
        SourceCapabilityRegistry(declarations)


def test_capability_registry_distinguishes_evidence_layers() -> None:
    declarations = {
        declaration.source_id: declaration
        for declaration in builtin_source_capabilities()
    }

    assert Capability.SOURCE_PARSER in declarations["us-drugsfda"].capabilities
    assert (
        Capability.CANONICAL_PROJECTION
        in declarations["nz-medsafe-products"].capabilities
    )
    assert (
        Capability.FIXTURE_PARSER
        in declarations["nz-medsafe-products"].capabilities
    )
    assert (
        Capability.SOURCE_PARSER
        not in declarations["nz-medsafe-products"].capabilities
    )
    assert (
        Capability.SYNTHETIC_FIXTURE
        in declarations["eu-ema-medicines"].capabilities
    )
    assert (
        Capability.LIVE_RECEIPT not in declarations["us-drugsfda"].capabilities
    )
    assert all(
        Capability.PRODUCTION_QUALIFICATION not in declaration.capabilities
        for declaration in declarations.values()
    )


def test_fixture_parser_matches_fixture_catalog_integration_maturity() -> None:
    catalog = load_source_catalog()
    registry = builtin_source_capabilities()

    registry.validate_catalog(catalog)

    medsafe = next(
        source
        for source in catalog
        if source.source_id == "nz-medsafe-products"
    )
    assert medsafe.integration_layer.value == "fixture"
    assert Capability.FIXTURE_PARSER in registry.capabilities_for(
        medsafe.source_id
    )


def test_source_parser_must_agree_with_catalog_integration_maturity() -> None:
    catalog = load_source_catalog()
    registry = SourceCapabilityRegistry((
        SourceCapabilityDeclaration(
            source_id="nz-medsafe-products",
            capabilities=frozenset({
                Capability.SOURCE_PARSER,
                Capability.CANONICAL_PROJECTION,
            }),
            implementations=(
                "adapters.nz_medsafe:project_medsafe_registry_csv",
            ),
        ),
    ))

    with pytest.raises(ValueError, match="conflicts with catalog"):
        registry.validate_catalog(catalog)


def test_fixture_parser_requires_explicit_fixture_capability() -> None:
    catalog = load_source_catalog()
    registry = SourceCapabilityRegistry((
        SourceCapabilityDeclaration(
            source_id="nz-medsafe-products",
            capabilities=frozenset({Capability.FIXTURE_PARSER}),
            implementations=("fixture:parser",),
        ),
    ))

    with pytest.raises(ValueError, match="requires synthetic fixture"):
        registry.validate_catalog(catalog)
