"""Fail-closed public-surface contracts for Prompt 34 utilisation sources."""

from __future__ import annotations

import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel

_SOURCE_IDS = (
    "fr-open-medic",
    "jp-mhlw-ndb-utilisation",
    "ca-cihi-nhex-medicines",
    "ie-pcrs-reimbursement",
)
_OPEN_MEDIC_YEARS = tuple(range(2014, 2026))
_OPEN_MEDIC_RESOURCE_COUNT = 85
_OPEN_MEDIC_CSV_COUNT = 82
_CIHI_RELEVANT_LINK_COUNT = 2


class AdditionalUtilisationSourceAuthorization(FrozenModel):
    """One source-specific maintainer decision, never a family-wide grant."""

    source_id: Literal[
        "fr-open-medic",
        "jp-mhlw-ndb-utilisation",
        "ca-cihi-nhex-medicines",
        "ie-pcrs-reimbursement",
    ]
    decision_date: date | None
    decision_status: Literal["pending", "approved_internal", "approved_public"]
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    landing_url: AnyHttpUrl
    rights_url: AnyHttpUrl

    @model_validator(mode="after")
    def fail_closed(self) -> AdditionalUtilisationSourceAuthorization:
        payload_authority = (
            self.decision_date is not None,
            self.acquisition_authorized,
            self.internal_retention_authorized,
        )
        publication_authority = (
            self.public_release_authorized,
            self.external_publication_authorized,
        )
        if self.decision_status == "pending":
            if (
                self.decision_date is not None
                or self.acquisition_authorized
                or self.internal_retention_authorized
            ):
                raise ValueError(
                    "pending Prompt 34 decision cannot authorize payloads"
                )
        elif self.decision_status == "approved_internal" and not (
            payload_authority == (True, True, True)
            and publication_authority == (False, False)
        ):
            raise ValueError(
                "approved Prompt 34 acquisition requires dated authority"
            )
        elif self.decision_status == "approved_public" and not all((
            *payload_authority,
            *publication_authority,
        )):
            raise ValueError(
                "approved public acquisition requires complete authority"
            )
        return self

    def require_payload_authority(self) -> None:
        """Raise unless this exact source has internal payload authority."""
        if self.decision_status not in {"approved_internal", "approved_public"}:
            raise PermissionError(
                f"{self.source_id} payload decision is pending"
            )


class AdditionalUtilisationAuthorization(FrozenModel):
    """Prompt 34 authority with deliberately independent source decisions."""

    schema_id: Literal[
        "global-medicines-atlas.additional-utilisation-acquisition-authorization"
    ]
    schema_version: Literal[1]
    sources: tuple[AdditionalUtilisationSourceAuthorization, ...]

    @model_validator(mode="after")
    def exact_sources(self) -> AdditionalUtilisationAuthorization:
        if tuple(source.source_id for source in self.sources) != _SOURCE_IDS:
            raise ValueError("Prompt 34 source identity or order drifted")
        return self


class OpenMedicInventory(FrozenModel):
    """Official data.gouv.fr release inventory, without downloading payloads."""

    licence: str
    years: tuple[int, ...]
    resource_count: int
    csv_resource_count: int


class PublicSurfaceInventory(FrozenModel):
    """One bounded public HTML surface and its relevant artefact links."""

    source_id: str
    publication_year: int
    artefact_urls: tuple[str, ...]


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = None


def load_additional_utilisation_authorization(
    path: Path,
) -> AdditionalUtilisationAuthorization:
    """Load the checked-in source-specific decision record."""
    return AdditionalUtilisationAuthorization.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def parse_open_medic_inventory(payload: bytes) -> OpenMedicInventory:
    """Verify the bounded official Open Medic metadata inventory."""
    raw = cast("dict[str, Any]", json.loads(payload))
    if raw.get("license") != "fr-lo":
        raise ValueError("Open Medic licence identity drifted")
    resources = raw.get("resources")
    if not isinstance(resources, list):
        raise TypeError("Open Medic resources missing")
    typed_resources = cast("list[dict[str, Any]]", resources)
    years = tuple(
        sorted({
            int(match.group(1))
            for resource in typed_resources
            if (
                match := re.search(
                    r"\b(20\d{2})\b", str(resource.get("title", ""))
                )
            )
        })
    )
    if years != _OPEN_MEDIC_YEARS:
        raise ValueError("Open Medic year inventory drifted")
    csv_count = sum(
        str(resource.get("format", "")).lower() == "csv"
        for resource in typed_resources
    )
    if (
        len(typed_resources) != _OPEN_MEDIC_RESOURCE_COUNT
        or csv_count != _OPEN_MEDIC_CSV_COUNT
    ):
        raise ValueError("Open Medic resource inventory drifted")
    return OpenMedicInventory(
        licence="Licence Ouverte 2.0",
        years=years,
        resource_count=len(typed_resources),
        csv_resource_count=csv_count,
    )


def parse_japan_ndb_public_surface(payload: bytes) -> PublicSurfaceInventory:
    """Verify the sixth NDB public prefectural prescribing Tableau surface."""
    text = payload.decode("utf-8")
    workbook = re.search(r"<param name='name' value='(?P<name>[^']+)'", text)
    if (
        "第6回 処方薬 都道府県別 薬効分類別数量" not in text
        or "https%3A%2F%2Fpublic.tableau.com%2F" not in text
        or workbook is None
    ):
        raise ValueError("MHLW NDB public aggregate surface drifted")
    return PublicSurfaceInventory(
        source_id="jp-mhlw-ndb-utilisation",
        publication_year=2021,
        artefact_urls=(
            "https://public.tableau.com/views/"
            + workbook.group("name").replace("&#47;", "/"),
        ),
    )


def parse_cihi_nhex_public_surface(payload: bytes) -> PublicSurfaceInventory:
    """Verify the current public NHEX drug-expenditure and open-data links."""
    text = payload.decode("utf-8")
    parser = _Links()
    parser.feed(text)
    links = tuple(
        href
        for href, label in parser.links
        if "nhex-series-g-2025-en.xlsx" in href
        or "nhex-open-data-2025-en.xlsx" in href
        or "Expenditure on drugs" in label
    )
    if (
        "NHEX trends data" not in text
        or len(set(links)) != _CIHI_RELEVANT_LINK_COUNT
    ):
        raise ValueError("CIHI NHEX public surface drifted")
    return PublicSurfaceInventory(
        source_id="ca-cihi-nhex-medicines",
        publication_year=2025,
        artefact_urls=tuple(dict.fromkeys(links)),
    )


def parse_hse_pcrs_public_surface(payload: bytes) -> PublicSurfaceInventory:
    """Verify the current HSE PCRS claims-and-payments report surface."""
    text = payload.decode("utf-8")
    parser = _Links()
    parser.feed(text)
    links = tuple(
        href
        for href, _ in parser.links
        if href.endswith(
            "PCRS_Statistical_Analysis_of_Claims_and_Payments_2024.pdf"
        )
    )
    if (
        "PCRS Statistical Analysis of Claims and Payments 2024" not in text
        or len(links) != 1
    ):
        raise ValueError("HSE PCRS public report surface drifted")
    return PublicSurfaceInventory(
        source_id="ie-pcrs-reimbursement",
        publication_year=2024,
        artefact_urls=links,
    )
