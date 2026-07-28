"""Reusable jurisdiction adapter and source-catalog contracts."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
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
