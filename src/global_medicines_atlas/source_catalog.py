"""Governed catalog of authoritative medicine data access surfaces."""

from __future__ import annotations

import json
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
        return self


def load_source_catalog() -> tuple[MedicineDataSource, ...]:
    path = Path(__file__).with_name("data") / "medicine_source_catalog.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = tuple(
        MedicineDataSource.model_validate(row) for row in payload["sources"]
    )
    ids = [source.source_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("Source catalog contains duplicate source_id values")
    LOGGER.debug(
        "Loaded governed medicine source catalog",
        extra={"source_id": str(path)},
    )
    return tuple(sorted(sources, key=lambda source: source.source_id))


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
