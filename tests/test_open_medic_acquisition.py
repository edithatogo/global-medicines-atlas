"""Tests for official Open Medic token-page acquisition."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from global_medicines_atlas.open_medic_acquisition import (
    inspect_open_medic_archive,
    resolve_open_medic_release,
)

PAGE_URL = (
    "https://open-data-assurance-maladie.ameli.fr/medicaments/"
    "download.php?Dir_Rep=Open_MEDIC_Base_Complete&Annee=2025"
)


def _page(href: str) -> bytes:
    return f'<html><a href="{href}">release</a></html>'.encode()


def _archive(name: str = "OPEN_MEDIC_2025.CSV") -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr(name, "ATC;BOITES\nA01;1\n")
    return stream.getvalue()


def test_resolves_exact_official_token_link() -> None:
    release = resolve_open_medic_release(
        _page(
            "./download_file.php?token=abc123&file="
            "Open_MEDIC_Base_Complete/OPEN_MEDIC_2025.zip"
        ),
        page_url=PAGE_URL,
        year=2025,
    )
    assert release.filename == "OPEN_MEDIC_2025.zip"
    assert release.archive_url.host == "open-data-assurance-maladie.ameli.fr"


@pytest.mark.parametrize(
    "href",
    [
        "https://example.test/OPEN_MEDIC_2025.zip",
        "./download_file.php?token=abc123&file=other.zip",
        "./download_file.php?file=Open_MEDIC_Base_Complete/OPEN_MEDIC_2025.zip",
    ],
)
def test_resolver_rejects_substitution_or_incomplete_links(href: str) -> None:
    with pytest.raises(ValueError, match="one exact official"):
        resolve_open_medic_release(_page(href), page_url=PAGE_URL, year=2025)


def test_archive_integrity_and_year_are_required() -> None:
    assert inspect_open_medic_archive(_archive(), year=2025) == (
        "OPEN_MEDIC_2025.CSV",
    )
    with pytest.raises(ValueError, match="release year"):
        inspect_open_medic_archive(_archive("OPEN_MEDIC.CSV"), year=2025)
    with pytest.raises(ValueError, match="not a ZIP"):
        inspect_open_medic_archive(b"not a zip", year=2025)


def test_download_limit_receipt_is_not_admitted_as_archive() -> None:
    with pytest.raises(ValueError, match="download limit refusal"):
        inspect_open_medic_archive(
            b"Telechargement refuse: Limite de telechargements atteinte",
            year=2025,
        )
