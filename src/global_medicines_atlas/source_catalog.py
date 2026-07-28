"""Governed catalog of authoritative medicine data access surfaces."""

from __future__ import annotations

import json
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import Field, HttpUrl, model_validator

from .countries import SourceDimension
from .logging import get_logger
from .models import FrozenModel

LOGGER = get_logger("source_catalog", component="source-catalog")


class AccessMode(StrEnum):
    API = "api"
    DOWNLOAD = "download"
    API_AND_DOWNLOAD = "api_and_download"
    WEB_SEARCH = "web_search"
    LICENSED_FEED = "licensed_feed"


class SourceReadiness(StrEnum):
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    CANDIDATE = "candidate"
    BLOCKED = "blocked"


class DiscoveryStatus(StrEnum):
    """Evidence level for a catalog declaration, never a currency claim."""

    DISCOVERY_ONLY = "discovery_only"
    DECLARATION_VERIFIED = "declaration_verified"
    RECEIPT_BACKED = "receipt_backed"


class MonitoringSchedule(FrozenModel):
    """Cadence contract for non-mutating source checks."""

    source_health: str = Field(min_length=1)
    schema_drift: str = Field(min_length=1)


class MedicineDataSource(FrozenModel):
    source_id: str = Field(min_length=1)
    jurisdictions: tuple[str, ...] = Field(min_length=1)
    authority: str = Field(min_length=1)
    title: str = Field(min_length=1)
    dimension: SourceDimension
    access_mode: AccessMode
    landing_page: HttpUrl
    api_url: HttpUrl | None = None
    download_url: HttpUrl | None = None
    update_cadence: str = Field(min_length=1)
    rights_status: str = Field(min_length=1)
    readiness: SourceReadiness
    discovery_status: DiscoveryStatus = DiscoveryStatus.DISCOVERY_ONLY
    implemented_ingestion: bool = False
    current_receipt_id: str | None = Field(default=None, min_length=1)
    monitoring: MonitoringSchedule = MonitoringSchedule(
        source_health="weekly",
        schema_drift="monthly",
    )
    evidence_limit: str = Field(min_length=1)

    @model_validator(mode="after")
    def access_surface_matches_mode(self) -> MedicineDataSource:
        if (
            self.access_mode in {AccessMode.API, AccessMode.API_AND_DOWNLOAD}
            and self.api_url is None
        ):
            raise ValueError("API access mode requires api_url")
        if (
            self.access_mode
            in {AccessMode.DOWNLOAD, AccessMode.API_AND_DOWNLOAD}
            and self.download_url is None
        ):
            raise ValueError("download access mode requires download_url")
        if self.current_receipt_id is not None and (
            self.discovery_status != DiscoveryStatus.RECEIPT_BACKED
        ):
            raise ValueError(
                "current receipt requires receipt-backed discovery status"
            )
        if self.implemented_ingestion != (
            self.readiness == SourceReadiness.IMPLEMENTED
        ):
            raise ValueError(
                "implemented_ingestion must agree with implemented readiness"
            )
        return self


class RegulatoryDenominator(FrozenModel):
    """WHO discovery-denominator fields awaiting receipt-backed verification."""

    included: bool
    wla: bool | None = None
    ml3: bool | None = None
    ml4: bool | None = None
    status: str = Field(min_length=1)
    evidence_limit: str = Field(min_length=1)


class JurisdictionCensusEntry(FrozenModel):
    jurisdiction: str = Field(min_length=2, max_length=3)
    name: str = Field(min_length=1)
    priority_cohorts: tuple[str, ...] = Field(min_length=1)
    regulatory_denominator: RegulatoryDenominator


class SourceCatalog(FrozenModel):
    schema_version: int = Field(ge=1)
    reviewed_at: date
    monitoring_contract: MonitoringSchedule
    jurisdictions: tuple[JurisdictionCensusEntry, ...]
    sources: tuple[MedicineDataSource, ...]

    @model_validator(mode="after")
    def monitoring_contract_is_applied(self) -> SourceCatalog:
        if any(
            source.monitoring != self.monitoring_contract
            for source in self.sources
        ):
            raise ValueError(
                "source monitoring must match the catalog monitoring contract"
            )
        return self


def load_catalog() -> SourceCatalog:
    path = Path(__file__).with_name("data") / "medicine_source_catalog.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    catalog = SourceCatalog.model_validate(payload)
    ids = [source.source_id for source in catalog.sources]
    if len(ids) != len(set(ids)):
        raise ValueError("Source catalog contains duplicate source_id values")
    jurisdiction_ids = [entry.jurisdiction for entry in catalog.jurisdictions]
    if len(jurisdiction_ids) != len(set(jurisdiction_ids)):
        raise ValueError("Source catalog contains duplicate jurisdictions")
    LOGGER.debug(
        "Loaded governed medicine source catalog",
        extra={"source_id": str(path)},
    )
    return catalog


def load_source_catalog() -> tuple[MedicineDataSource, ...]:
    return tuple(
        sorted(load_catalog().sources, key=lambda source: source.source_id)
    )


def sources_for(
    jurisdiction: str,
    dimension: SourceDimension | None = None,
) -> tuple[MedicineDataSource, ...]:
    code = jurisdiction.upper()
    return tuple(
        source
        for source in load_source_catalog()
        if code in source.jurisdictions
        and (dimension is None or source.dimension == dimension)
    )
