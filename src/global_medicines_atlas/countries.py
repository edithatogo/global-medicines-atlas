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
    PARSER = "parser"
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    CANONICAL_PROJECTION = "canonical_projection"
    LIVE_RECEIPT = "live_receipt"
    PRODUCTION_QUALIFICATION = "production_qualification"


class SourceCapabilityDeclaration(FrozenModel):
    """Auditable mapping from executable implementations to one source."""

    source_id: str = Field(min_length=1)
    capabilities: frozenset[Capability] = Field(min_length=1)
    implementations: tuple[str, ...] = Field(min_length=1)


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

    def validate_catalog(self, source_ids: Iterable[str]) -> None:
        catalog_ids = set(source_ids)
        missing = sorted({
            declaration.source_id
            for declaration in self._declarations
            if declaration.source_id not in catalog_ids
        })
        if missing:
            raise ValueError(
                f"capability registry uses unknown source IDs: {missing}"
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
    projected = frozenset({
        Capability.PARSER,
        Capability.SYNTHETIC_FIXTURE,
        Capability.CANONICAL_PROJECTION,
    })
    parser = frozenset({
        Capability.PARSER,
        Capability.CANONICAL_PROJECTION,
    })
    return SourceCapabilityRegistry((
        SourceCapabilityDeclaration(
            source_id="au-artg",
            capabilities=parser,
            implementations=("adapters.au_artg:project_artg_csv",),
        ),
        SourceCapabilityDeclaration(
            source_id="au-pbs-historical-xml",
            capabilities=parser,
            implementations=("adapters.au_pbs:project_pbs_xml",),
        ),
        SourceCapabilityDeclaration(
            source_id="ca-dpd",
            capabilities=projected,
            implementations=(
                "adapters.canada:project_dpd_api",
                "adapters.canada:project_dpd_bulk",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="ca-noc",
            capabilities=parser,
            implementations=("adapters.canada:project_noc_extract",),
        ),
        SourceCapabilityDeclaration(
            source_id="eu-ema-medicines",
            capabilities=projected,
            implementations=(
                "adapters.european_union:project_ema_medicine_csv",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="eu-union-register",
            capabilities=parser,
            implementations=(
                "adapters.european_union:project_union_register_xml",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="jp-pmda-approvals",
            capabilities=projected,
            implementations=("adapters.japan:project_pmda_approval_csv",),
        ),
        SourceCapabilityDeclaration(
            source_id="jp-mhlw-nhi-price",
            capabilities=parser,
            implementations=("adapters.japan:project_mhlw_nhi_price_csv",),
        ),
        SourceCapabilityDeclaration(
            source_id="nz-medsafe-products",
            capabilities=parser,
            implementations=(
                "adapters.nz_medsafe:project_medsafe_registry_csv",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="nz-pharmac-schedule-xml",
            capabilities=parser,
            implementations=(
                "adapters.nz_pharmac:project_pharmac_schedule_xml",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="gb-mhra-products",
            capabilities=projected,
            implementations=(
                "adapters.united_kingdom:project_mhra_products_csv",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="gb-nice-ta",
            capabilities=parser,
            implementations=(
                "adapters.united_kingdom:project_nice_appraisals_xml",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="us-cms-partd-formulary",
            capabilities=parser,
            implementations=("adapters.us_cms_partd:project_cms_partd_csv",),
        ),
        SourceCapabilityDeclaration(
            source_id="us-drugsfda",
            capabilities=parser | acquisition,
            implementations=(
                "adapters.us_acquisition:acquire_drugsfda_api",
                "adapters.us_acquisition:acquire_drugsfda_bulk",
                "adapters.us_drugsfda:project_drugsfda_api",
                "adapters.us_drugsfda:project_drugsfda_bulk",
            ),
        ),
        SourceCapabilityDeclaration(
            source_id="global-rxnorm",
            capabilities=projected,
            implementations=(
                "terminology:LocalRxNormResolver",
                "terminology:bootstrap_rxnorm_resolver",
            ),
        ),
    ))
