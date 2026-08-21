"""Fail-closed public-surface contracts for Prompt 35 pharmacovigilance."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel

_SOURCE_IDS = (
    "global-umc-vigibase",
    "gb-mhra-yellow-card",
    "au-tga-daen",
    "ca-canada-vigilance",
    "jp-pmda-safety",
)
_CANADA_TABLES = (
    "Reports.txt",
    "Drug_Product.txt",
    "Drug_Product_Ingredients.txt",
    "Reactions.txt",
    "Outcome_LX.txt",
    "Gender_LX.txt",
    "Report_Type_LX.txt",
    "Seriousness_LX.txt",
    "Source_LX.txt",
    "Report_Links_LX.txt",
    "Report_Drug.txt",
    "Report_Drug_Indication.txt",
    "Literature_Reference.txt",
)
_CANADA_LISTED_TABLE_COUNT = len(_CANADA_TABLES)


class GlobalPvSourceAuthorization(FrozenModel):
    """One source-specific decision; public visibility is not payload authority."""

    source_id: Literal[
        "global-umc-vigibase",
        "gb-mhra-yellow-card",
        "au-tga-daen",
        "ca-canada-vigilance",
        "jp-pmda-safety",
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
    def fail_closed(self) -> GlobalPvSourceAuthorization:
        internal = (
            self.decision_date is not None
            and self.acquisition_authorized
            and self.internal_retention_authorized
        )
        public = (
            self.public_release_authorized
            and self.external_publication_authorized
        )
        if self.decision_status == "pending" and (internal or public):
            raise ValueError(
                "pending Prompt 35 decision cannot authorize payloads"
            )
        if self.decision_status == "approved_internal" and (
            not internal or public
        ):
            raise ValueError(
                "approved internal acquisition requires bounded authority"
            )
        if self.decision_status == "approved_public" and not (
            internal and public
        ):
            raise ValueError(
                "approved public acquisition requires complete authority"
            )
        return self

    def require_payload_authority(self) -> None:
        if self.decision_status not in {"approved_internal", "approved_public"}:
            raise PermissionError(
                f"{self.source_id} payload decision is pending"
            )


class GlobalPvAuthorization(FrozenModel):
    schema_id: Literal[
        "global-medicines-atlas.global-pv-acquisition-authorization"
    ]
    schema_version: Literal[1]
    sources: tuple[GlobalPvSourceAuthorization, ...]

    @model_validator(mode="after")
    def exact_sources(self) -> GlobalPvAuthorization:
        if tuple(item.source_id for item in self.sources) != _SOURCE_IDS:
            raise ValueError("Prompt 35 source identity or order drifted")
        return self


class PublicPvSurface(FrozenModel):
    source_id: str
    surface_kind: Literal[
        "restricted", "interactive_export", "bulk_metadata", "documents"
    ]
    artefacts: tuple[str, ...]
    limitation: str


def load_global_pv_authorization(path: Path) -> GlobalPvAuthorization:
    return GlobalPvAuthorization.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def parse_canada_vigilance_structure(payload: bytes) -> PublicPvSurface:
    """Inventory official metadata only; deliberately do not fetch the bulk ZIP."""
    text = payload.decode("utf-8")
    tables = tuple(dict.fromkeys(re.findall(r">([A-Za-z_]+\.txt)<", text)))
    if not all(table in tables for table in _CANADA_TABLES):
        raise ValueError("Canada Vigilance table inventory drifted")
    if (
        "comprised of 11 files" not in text
        or len(tables) != _CANADA_LISTED_TABLE_COUNT
    ):
        raise ValueError(
            "Canada Vigilance documented count discrepancy drifted"
        )
    return PublicPvSurface(
        source_id="ca-canada-vigilance",
        surface_kind="bulk_metadata",
        artefacts=tables,
        limitation="Official page says 11 files while listing 13; payload not acquired.",
    )


def parse_tga_daen_surface(payload: bytes) -> PublicPvSurface:
    text = payload.decode("utf-8")
    required = ("1 January 1971", "14 days", "150,000", "30,000")
    if not all(token in text for token in required):
        raise ValueError("TGA DAEN interactive export surface drifted")
    return PublicPvSurface(
        source_id="au-tga-daen",
        surface_kind="interactive_export",
        artefacts=("xlsx-current-layout", "csv-summarised"),
        limitation="Suspected associations are not causality; exports are query-bounded.",
    )


def parse_mhra_yellow_card_surface(payload: bytes) -> PublicPvSurface:
    text = payload.decode("utf-8")
    if (
        "interactive Drug Analysis Profiles" not in text
        or "active substance" not in text
    ):
        raise ValueError("MHRA Yellow Card iDAP surface drifted")
    return PublicPvSurface(
        source_id="gb-mhra-yellow-card",
        surface_kind="interactive_export",
        artefacts=("interactive-drug-analysis-profiles",),
        limitation="Public aggregate visualisations are not unrestricted case-level data.",
    )


def parse_pmda_safety_surface(payload: bytes) -> PublicPvSurface:
    text = payload.decode("utf-8")
    required = ("Post-marketing Safety", "only in Japanese", "since April 2004")
    if not all(token in text for token in required):
        raise ValueError("PMDA safety-document surface drifted")
    return PublicPvSurface(
        source_id="jp-pmda-safety",
        surface_kind="documents",
        artefacts=("alerts", "suspected-adr-cases", "safety-information"),
        limitation="Case reports are Japanese-only and do not establish causality.",
    )
