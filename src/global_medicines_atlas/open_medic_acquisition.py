"""Resolve and validate official Open Medic annual archive releases."""

from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
from typing import Final
from urllib.parse import parse_qs, urljoin, urlparse
from zipfile import BadZipFile, ZipFile

from pydantic import AnyHttpUrl, Field

from .models import FrozenModel

OFFICIAL_HOST: Final = "open-data-assurance-maladie.ameli.fr"
EXPECTED_YEARS: Final = tuple(range(2014, 2026))
REFUSAL_MARKER: Final = b"chargements atteinte"


class OpenMedicRelease(FrozenModel):
    """One exact official annual Open Medic release."""

    year: int = Field(ge=2014, le=2025)
    archive_url: AnyHttpUrl
    filename: str


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(href)


def resolve_open_medic_release(
    page: bytes, *, page_url: str, year: int
) -> OpenMedicRelease:
    """Resolve the short-lived official archive URL from a token page."""
    if year not in EXPECTED_YEARS:
        raise ValueError("Open Medic year is outside the reviewed series")
    parser = _Links()
    parser.feed(page.decode("iso-8859-1"))
    expected = f"Open_MEDIC_Base_Complete/OPEN_MEDIC_{year}.zip"
    matches: list[str] = []
    for href in parser.hrefs:
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        query = parse_qs(parsed.query)
        official_endpoint = (
            parsed.scheme == "https"
            and parsed.hostname == OFFICIAL_HOST
            and parsed.path.endswith("/medicaments/download_file.php")
        )
        exact_resource = (
            query.get("file") == [expected]
            and len(query.get("token", [])) == 1
            and query["token"][0]
        )
        if official_endpoint and exact_resource:
            matches.append(absolute)
    if len(matches) != 1:
        raise ValueError("expected one exact official Open Medic archive link")
    return OpenMedicRelease(
        year=year,
        archive_url=matches[0],
        filename=f"OPEN_MEDIC_{year}.zip",
    )


def inspect_open_medic_archive(payload: bytes, *, year: int) -> tuple[str, ...]:
    """Reject limiter responses and unsafe or year-mismatched ZIP payloads."""
    if REFUSAL_MARKER in payload:
        raise ValueError("Open Medic upstream download limit refusal")
    try:
        with ZipFile(BytesIO(payload)) as archive:
            names = tuple(sorted(archive.namelist()))
            if not names or archive.testzip() is not None:
                raise ValueError("Open Medic archive integrity check failed")
    except BadZipFile as error:
        raise ValueError("Open Medic payload is not a ZIP archive") from error
    if not any(str(year) in name for name in names):
        raise ValueError(
            "Open Medic archive does not identify its release year"
        )
    return names
