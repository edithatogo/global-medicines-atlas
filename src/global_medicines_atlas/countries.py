"""Reusable jurisdiction adapter and source-catalog contracts."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import Field

from .models import CanonicalMedicineRecord, FrozenModel


class SourceDimension(StrEnum):
    REGULATORY = "regulatory"
    FUNDING = "funding"
    FORMULARY = "formulary"
    TERMINOLOGY = "terminology"


class Capability(StrEnum):
    ACQUISITION = "acquisition"
    FIXTURE_PARSER = "fixture_parser"
    SOURCE_PARSER = "source_parser"
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    CANONICAL_PROJECTION = "canonical_projection"
    LIVE_RECEIPT = "live_receipt"
    PRODUCTION_QUALIFICATION = "production_qualification"


class SourceCapabilityDeclaration(FrozenModel):
    """Auditable mapping from executable implementations to one source."""

    source_id: str = Field(min_length=1)
    capabilities: frozenset[Capability] = Field(min_length=1)
    implementations: tuple[str, ...] = Field(min_length=1)


class CatalogCapabilitySource(Protocol):
    @property
    def source_id(self) -> str: ...

    @property
    def integration_layer(self) -> object: ...


class SourceCapabilityRegistry:
    """One-to-one implementation mapping with source-level capabilities."""

    def __init__(
        self,
        declarations: Sequence[SourceCapabilityDeclaration],
    ) -> None:
        self._declarations = tuple(declarations)
        implementation_sources: dict[str, str] = {}
        for declaration in self._declarations:
            for implementation in declaration.implementations:
                previous = implementation_sources.setdefault(
                    implementation,
                    declaration.source_id,
                )
                if previous != declaration.source_id:
                    raise ValueError(
                        f"{implementation} maps to both {previous} and "
                        f"{declaration.source_id}"
                    )
        self._implementation_sources = implementation_sources

    def __iter__(self) -> Iterator[SourceCapabilityDeclaration]:
        return iter(self._declarations)

    def source_id_for(self, implementation: str) -> str:
        return self._implementation_sources[implementation]

    def capabilities_for(self, source_id: str) -> frozenset[Capability]:
        return frozenset(
            capability
            for declaration in self._declarations
            if declaration.source_id == source_id
            for capability in declaration.capabilities
        )

    def validate_catalog(
        self,
        sources: Iterable[CatalogCapabilitySource],
    ) -> None:
        catalog = {source.source_id: source for source in sources}
        catalog_ids = set(catalog)
        missing = sorted({
            declaration.source_id
            for declaration in self._declarations
            if declaration.source_id not in catalog_ids
        })
        if missing:
            raise ValueError(
                f"capability registry uses unknown source IDs: {missing}"
            )
        mature_layers = {"parser", "live_receipt"}
        for declaration in self._declarations:
            source = catalog[declaration.source_id]
            capabilities = declaration.capabilities
            fixture_only = Capability.FIXTURE_PARSER in capabilities
            source_parser = Capability.SOURCE_PARSER in capabilities
            if (
                fixture_only
                and Capability.SYNTHETIC_FIXTURE not in capabilities
            ):
                raise ValueError(
                    f"{source.source_id} fixture parser requires synthetic "
                    "fixture capability"
                )
            integration_layer = str(source.integration_layer)
            if source_parser and integration_layer not in mature_layers:
                raise ValueError(
                    f"{source.source_id} source parser conflicts with catalog "
                    f"integration layer {integration_layer}"
                )
            if (
                Capability.CANONICAL_PROJECTION in capabilities
                and not fixture_only
                and not source_parser
            ):
                raise ValueError(
                    f"{source.source_id} canonical projection requires a "
                    "fixture or source parser"
                )


class JurisdictionSource(FrozenModel):
    source_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    authority: str = Field(min_length=1)
    dimension: SourceDimension
    homepage: str = Field(min_length=1)
    coverage_note: str = Field(min_length=1)


class CountryAdapter(Protocol):
    @property
    def jurisdiction(self) -> str: ...

    @property
    def sources(self) -> tuple[JurisdictionSource, ...]: ...

    def canonical_records(self) -> Iterable[CanonicalMedicineRecord]: ...


@dataclass(frozen=True, slots=True)
class DeclarativeCountryAdapter:
    """Source contract for a jurisdiction whose ingestion is not implemented yet."""

    jurisdiction: str
    sources: tuple[JurisdictionSource, ...]

    def canonical_records(self) -> Iterator[CanonicalMedicineRecord]:
        return iter(())


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, CountryAdapter] = {}

    def register(self, adapter: CountryAdapter) -> None:
        key = adapter.jurisdiction.upper()
        if key in self._adapters:
            raise ValueError(f"Adapter already registered for {key}")
        dimensions = {source.dimension for source in adapter.sources}
        if SourceDimension.REGULATORY not in dimensions:
            raise ValueError(f"{key} adapter requires a regulatory source")
        self._adapters[key] = adapter

    def get(self, jurisdiction: str) -> CountryAdapter:
        return self._adapters[jurisdiction.upper()]

    def jurisdictions(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def _source(
    source_id: str,
    jurisdiction: str,
    authority: str,
    dimension: SourceDimension,
    homepage: str,
    coverage_note: str,
) -> JurisdictionSource:
    return JurisdictionSource(
        source_id=source_id,
        jurisdiction=jurisdiction,
        authority=authority,
        dimension=dimension,
        homepage=homepage,
        coverage_note=coverage_note,
    )


def builtin_registry() -> AdapterRegistry:
    """Return the first evidence-source cohort; declarations are not ingestors."""
    adapters = (
        DeclarativeCountryAdapter(
            "NZL",
            (
                _source(
                    "nz-medsafe",
                    "NZL",
                    "Medsafe",
                    SourceDimension.REGULATORY,
                    "https://www.medsafe.govt.nz/regulatory/dbsearch.asp",
                    "New Zealand medicine product and application records.",
                ),
                _source(
                    "nz-pharmac",
                    "NZL",
                    "Pharmac",
                    SourceDimension.FUNDING,
                    "https://schedule.pharmac.govt.nz/ScheduleOnline.php",
                    "New Zealand Pharmaceutical Schedule funding decisions.",
                ),
            ),
        ),
        DeclarativeCountryAdapter(
            "AUS",
            (
                _source(
                    "au-artg",
                    "AUS",
                    "Therapeutic Goods Administration",
                    SourceDimension.REGULATORY,
                    "https://www.tga.gov.au/resources/artg",
                    "Australian Register of Therapeutic Goods entries.",
                ),
                _source(
                    "au-pbs",
                    "AUS",
                    "Department of Health, Disability and Ageing",
                    SourceDimension.FUNDING,
                    "https://www.pbs.gov.au/pbs/home",
                    "Australian Pharmaceutical Benefits Scheme listings.",
                ),
            ),
        ),
        DeclarativeCountryAdapter(
            "USA",
            (
                _source(
                    "us-drugs-at-fda",
                    "USA",
                    "Food and Drug Administration",
                    SourceDimension.REGULATORY,
                    "https://www.accessdata.fda.gov/scripts/cder/daf/",
                    "FDA-approved drug products and approval history.",
                ),
            ),
        ),
        DeclarativeCountryAdapter(
            "GBR",
            (
                _source(
                    "gb-mhra-products",
                    "GBR",
                    "Medicines and Healthcare products Regulatory Agency",
                    SourceDimension.REGULATORY,
                    "https://products.mhra.gov.uk/",
                    "United Kingdom authorised medicinal products.",
                ),
                _source(
                    "gb-nhs-dmd",
                    "GBR",
                    "NHS Business Services Authority",
                    SourceDimension.FORMULARY,
                    "https://www.nhsbsa.nhs.uk/pharmacies-gp-practices-and-appliance-contractors/dictionary-medicines-and-devices-dmd",
                    "NHS dictionary of medicines and devices; not itself approval evidence.",
                ),
            ),
        ),
        DeclarativeCountryAdapter(
            "CAN",
            (
                _source(
                    "ca-dpd",
                    "CAN",
                    "Health Canada",
                    SourceDimension.REGULATORY,
                    "https://health-products.canada.ca/dpd-bdpp/",
                    "Canadian Drug Product Database records.",
                ),
            ),
        ),
        DeclarativeCountryAdapter(
            "JPN",
            (
                _source(
                    "jp-pmda",
                    "JPN",
                    "Pharmaceuticals and Medical Devices Agency",
                    SourceDimension.REGULATORY,
                    "https://www.pmda.go.jp/english/review-services/reviews/approved-information/drugs/0002.html",
                    "Japanese new-drug approval information.",
                ),
                _source(
                    "jp-mhlw-nhi",
                    "JPN",
                    "Ministry of Health, Labour and Welfare",
                    SourceDimension.FUNDING,
                    "https://www.mhlw.go.jp/english/policy/health-medical/pharmaceuticals/index.html",
                    "National Health Insurance drug pricing source contract.",
                ),
            ),
        ),
        DeclarativeCountryAdapter(
            "EU",
            (
                _source(
                    "eu-ema-epar",
                    "EU",
                    "European Medicines Agency",
                    SourceDimension.REGULATORY,
                    "https://www.ema.europa.eu/en/medicines",
                    "Centrally assessed medicines only; national authorisations remain separate.",
                ),
            ),
        ),
    )
    registry = AdapterRegistry()
    for adapter in adapters:
        registry.register(adapter)
    return registry


def builtin_source_capabilities() -> SourceCapabilityRegistry:
    """Return fail-closed capabilities for executable source implementations.

    Implementation identifiers are stable ``module:symbol`` references. Each
    identifier occurs once, so code cannot silently imply two source records.
    Live-receipt and production-qualification capabilities are deliberately
    absent until receipt-backed evidence exists.
    """

    acquisition = frozenset({Capability.ACQUISITION})
    fixture_projected = frozenset({
        Capability.FIXTURE_PARSER,
        Capability.SYNTHETIC_FIXTURE,
        Capability.CANONICAL_PROJECTION,
    })
    source_projected = frozenset({
        Capability.SOURCE_PARSER,
        Capability.CANONICAL_PROJECTION,
    })
    return SourceCapabilityRegistry((
        SourceCapabilityDeclaration(
            source_id="au-artg",
            capabilities=fixture_projected,
            implementations=("adapters.au_artg:project_artg_csv",),
        ),
        SourceCapabilityDeclaration(
            source_id="au-pbs-historical-xml",
            capabilities=fixture_projected,
            implementations=("adapters.au_pbs:project_pbs_xml",),
        ),
        SourceCapabilityDeclaration(
            source_id="ca-dpd",
            capabilities=fixture_projected,
            implementations=(
                "adapters.canada:project_dpd_api",
                "adapters.canada:project_dpd_bulk",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="ca-noc",
            capabilities=fixture_projected,
            implementations=("adapters.canada:project_noc_extract",),
        ),
        SourceCapabilityDeclaration(
            source_id="eu-ema-medicines",
            capabilities=fixture_projected,
            implementations=(
                "adapters.european_union:project_ema_medicine_csv",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="eu-union-register",
            capabilities=fixture_projected,
            implementations=(
                "adapters.european_union:project_union_register_xml",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="jp-pmda-approvals",
            capabilities=fixture_projected,
            implementations=("adapters.japan:project_pmda_approval_csv",),
        ),
        SourceCapabilityDeclaration(
            source_id="jp-mhlw-nhi-price",
            capabilities=fixture_projected,
            implementations=("adapters.japan:project_mhlw_nhi_price_csv",),
        ),
        SourceCapabilityDeclaration(
            source_id="nz-medsafe-products",
            capabilities=fixture_projected,
            implementations=(
                "adapters.nz_medsafe:project_medsafe_registry_csv",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="nz-pharmac-schedule-xml",
            capabilities=fixture_projected,
            implementations=(
                "adapters.nz_pharmac:project_pharmac_schedule_xml",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="gb-mhra-products",
            capabilities=fixture_projected,
            implementations=(
                "adapters.united_kingdom:project_mhra_products_csv",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="gb-nice-ta",
            capabilities=fixture_projected,
            implementations=(
                "adapters.united_kingdom:project_nice_appraisals_xml",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="us-cms-partd-formulary",
            capabilities=fixture_projected,
            implementations=("adapters.us_cms_partd:project_cms_partd_csv",),
        ),
        SourceCapabilityDeclaration(
            source_id="us-drugsfda",
            capabilities=source_projected | acquisition,
            implementations=(
                "adapters.us_acquisition:acquire_drugsfda_api",
                "adapters.us_acquisition:acquire_drugsfda_bulk",
                "adapters.us_drugsfda:project_drugsfda_api",
                "adapters.us_drugsfda:project_drugsfda_bulk",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="global-rxnorm",
            capabilities=source_projected,
            implementations=(
                "terminology:LocalRxNormResolver",
                "terminology:bootstrap_rxnorm_resolver",
            ),
        ),
    ))
