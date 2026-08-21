"""Fail-closed public-surface contracts for Nordic utilisation sources."""

from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel

_SOURCE_IDS = (
    "dk-medstat-utilisation",
    "no-norpd-utilisation",
    "se-socialstyrelsen-utilisation",
)
_DK_FILE = re.compile(r"^(?P<year>\d{4})_(?:atc_code|product_name)_data\.txt$")
_DK_METADATA_FILE_COUNT = 60


class NordicSourceAuthorization(FrozenModel):
    """One independent maintainer decision for one Nordic source."""

    source_id: Literal[
        "dk-medstat-utilisation",
        "no-norpd-utilisation",
        "se-socialstyrelsen-utilisation",
    ]
    decision_date: date | None
    decision_status: Literal["pending", "approved_internal"]
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    landing_url: AnyHttpUrl
    rights_url: AnyHttpUrl

    @model_validator(mode="after")
    def fail_closed(self) -> NordicSourceAuthorization:
        if self.public_release_authorized or self.external_publication_authorized:
            raise ValueError("Nordic publication must remain separately gated")
        if self.decision_status == "pending":
            if (
                self.decision_date is not None
                or self.acquisition_authorized
                or self.internal_retention_authorized
            ):
                raise ValueError("pending Nordic decision cannot authorize payloads")
        elif (
            self.decision_date is None
            or not self.acquisition_authorized
            or not self.internal_retention_authorized
        ):
            raise ValueError("approved Nordic acquisition requires dated authority")
        return self

    def require_payload_authority(self) -> None:
        """Raise unless this exact source has internal payload authority."""
        if self.decision_status != "approved_internal":
            raise PermissionError(f"{self.source_id} payload decision is pending")


class NordicAuthorization(FrozenModel):
    """Prompt 33 authority with deliberately independent source decisions."""

    schema_id: Literal[
        "global-medicines-atlas.nordic-utilisation-acquisition-authorization"
    ]
    schema_version: Literal[1]
    sources: tuple[NordicSourceAuthorization, ...]

    @model_validator(mode="after")
    def exact_sources(self) -> NordicAuthorization:
        if tuple(source.source_id for source in self.sources) != _SOURCE_IDS:
            raise ValueError("Nordic source identity or order drifted")
        return self


class DenmarkMetadataInventory(FrozenModel):
    """The public Medstat metadata downloads, not utilisation results."""

    first_year: int
    latest_year: int
    annual_metadata_file_count: int
    population_file_present: bool


class SwedenQueryInventory(FrozenModel):
    """The bounded public aggregate query surface, without query results."""

    resolution_modes: tuple[str, ...]
    annual_years: tuple[int, ...]
    monthly_years: tuple[int, ...]
    geography_count: int
    age_group_count: int
    sex_count: int
    measure_ids: tuple[int, ...]
    maximum_cells: int
    maximum_atc_codes: int


class _SurfaceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.select: str | None = None
        self.options: dict[str, list[str]] = {}
        self.links: list[str] = []
        self.labels: list[str] = []
        self._capture_link = False
        self._capture_label = False
        self._chunks: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        if tag == "select":
            self.select = values.get("id") or ""
            self.options.setdefault(self.select, [])
        elif tag == "option" and self.select is not None:
            self.options[self.select].append((values.get("value") or "").strip())
        elif tag == "a":
            self._capture_link = True
            self._chunks = []
        elif tag == "label" and (values.get("for") or "").startswith("matti_"):
            self._capture_label = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture_link or self._capture_label:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self.select = None
        elif tag == "a" and self._capture_link:
            self.links.append("".join(self._chunks).strip())
            self._capture_link = False
        elif tag == "label" and self._capture_label:
            self.labels.append("".join(self._chunks).strip())
            self._capture_label = False


def load_nordic_authorization(path: Path) -> NordicAuthorization:
    """Load the checked-in decision record."""
    return NordicAuthorization.model_validate_json(path.read_text(encoding="utf-8"))


def parse_denmark_metadata_inventory(payload: bytes) -> DenmarkMetadataInventory:
    """Verify the exact Medstat metadata-only download inventory."""
    parser = _SurfaceParser()
    parser.feed(payload.decode("utf-8"))
    names = [name for name in parser.links if name.endswith(".txt")]
    years = [int(match.group("year")) for name in names if (match := _DK_FILE.match(name))]
    if len(years) != _DK_METADATA_FILE_COUNT or sorted(set(years)) != list(
        range(1996, 2026)
    ):
        raise ValueError("Medstat annual metadata inventory drifted")
    if names.count("population_data.txt") != 1:
        raise ValueError("Medstat population metadata identity drifted")
    return DenmarkMetadataInventory(
        first_year=min(years),
        latest_year=max(years),
        annual_metadata_file_count=len(years),
        population_file_present=True,
    )


def parse_sweden_query_inventory(payload: bytes) -> SwedenQueryInventory:
    """Verify the current Socialstyrelsen aggregate query dimensions."""
    text = payload.decode("utf-8")
    parser = _SurfaceParser()
    parser.feed(text)
    expected_counts = {"ARMANAD_IND": 3, "OMR": 22, "AGI": 18, "KON": 3}
    if any(len(parser.options.get(key, ())) != value for key, value in expected_counts.items()):
        raise ValueError("Socialstyrelsen query dimensions drifted")
    annual = tuple(sorted(int(value) for value in parser.options.get("AR", ())))
    monthly = tuple(sorted(int(value) for value in parser.options.get("AR_MANAD", ())))
    if annual != tuple(range(2006, 2026)) or monthly != tuple(range(2006, 2027)):
        raise ValueError("Socialstyrelsen year inventory drifted")
    measures = tuple(
        sorted(
            {
                int(value.split("_")[1])
                for value in re.findall(r"matti_\d+_1", text)
            }
        )
    )
    if measures != (1, 2, 3, 4, 9):
        raise ValueError("Socialstyrelsen measure inventory drifted")
    if "max antal 70 000" not in text or "fler än 100 ATC-koder" not in text:
        raise ValueError("Socialstyrelsen query limits drifted")
    return SwedenQueryInventory(
        resolution_modes=tuple(parser.options["ARMANAD_IND"]),
        annual_years=annual,
        monthly_years=monthly,
        geography_count=22,
        age_group_count=18,
        sex_count=3,
        measure_ids=measures,
        maximum_cells=70_000,
        maximum_atc_codes=100,
    )
