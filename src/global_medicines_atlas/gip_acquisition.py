"""Fail-closed inventory contracts for GIP medicines open data."""

from __future__ import annotations

import re
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import urljoin

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel

SOURCE_ID = "nl-gipdatabank"
_HOST = "www.zorgcijfersdatabank.nl"
_TITLE = re.compile(
    r"^GIP (?P<family>Farmacie|farmacie|Addon|addon) Zvw "
    r"(?P<shape>meerjaren|lftgesl) (?P<period>[0-9]{4}(?:-[0-9]{4})?)_"
    r"(?P<version>[0-9]{8})$"
)


class GIPRelease(FrozenModel):
    """One source-native GIP medicine CSV advertised by the landing page."""

    title: str = Field(min_length=1)
    family: Literal["farmacie", "addon"]
    shape: Literal["meerjaren", "lftgesl"]
    period: str = Field(pattern=r"^[0-9]{4}(?:-[0-9]{4})?$")
    version_date: date
    download_url: AnyHttpUrl

    @model_validator(mode="after")
    def official_scope(self) -> GIPRelease:
        if self.download_url.host != _HOST:
            raise ValueError(
                "GIP downloads must stay on zorgcijfersdatabank.nl"
            )
        if self.family == "addon" and self.shape != "meerjaren":
            raise ValueError("the official Add-on corpus is rolling-table only")
        return self


class GIPAuthorization(FrozenModel):
    """Maintainer authority binding the exact GIP medicine inventory."""

    schema_id: Literal["global-medicines-atlas.gip-acquisition-authorization"]
    schema_version: Literal[1]
    decision_date: date | None
    decision_status: Literal["pending", "approved_internal", "approved_public"]
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    landing_url: AnyHttpUrl
    rights_url: AnyHttpUrl
    expected_release_count: Literal[28]
    expected_title_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_scope(self) -> GIPAuthorization:
        if self.landing_url.host != _HOST or self.rights_url.host != _HOST:
            raise ValueError(
                "GIP authority must stay on zorgcijfersdatabank.nl"
            )
        if self.decision_status == "pending":
            if (
                self.decision_date is not None
                or self.acquisition_authorized
                or self.internal_retention_authorized
                or self.public_release_authorized
                or self.external_publication_authorized
            ):
                raise ValueError(
                    "pending GIP decision cannot authorize payloads"
                )
        elif self.decision_status == "approved_internal" and not all((
            self.decision_date is not None,
            self.acquisition_authorized,
            self.internal_retention_authorized,
            not self.public_release_authorized,
            not self.external_publication_authorized,
        )):
            raise ValueError(
                "approved GIP acquisition requires dated authority"
            )
        elif self.decision_status == "approved_public" and not all((
            self.decision_date is not None,
            self.acquisition_authorized,
            self.internal_retention_authorized,
            self.public_release_authorized,
            self.external_publication_authorized,
        )):
            raise ValueError(
                "approved public GIP authority requires acquisition, retention, release, and publication"
            )
        return self

    def require_payload_authority(self) -> None:
        """Raise unless internal acquisition and retention are approved."""
        if self.decision_status not in {"approved_internal", "approved_public"}:
            raise PermissionError("GIP payload acquisition decision is pending")


class GIPInventory(FrozenModel):
    """Exact current medicine-family inventory from the official landing page."""

    source_id: Literal["nl-gipdatabank"] = SOURCE_ID
    release_count: int
    releases: tuple[GIPRelease, ...]


class _GIPLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._in_title = False
        self._title: list[str] = []
        self.items: list[tuple[str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if (
            tag.casefold() == "a"
            and "file-download" in (attributes.get("class") or "").split()
        ):
            self._href = attributes.get("href")
        elif (
            self._href is not None
            and tag.casefold() == "h4"
            and "title" in (attributes.get("class") or "").split()
        ):
            self._in_title = True

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "h4" and self._in_title:
            self._in_title = False
        elif tag.casefold() == "a" and self._href is not None:
            title = " ".join("".join(self._title).split())
            if title:
                self.items.append((title, self._href))
            self._href = None
            self._title = []


def parse_gip_inventory(
    payload: bytes, *, authorization: GIPAuthorization
) -> GIPInventory:
    """Parse and bind every Farmacie/Add-on medicine CSV without fetching it."""
    parser = _GIPLinks()
    parser.feed(payload.decode("utf-8"))
    releases: list[GIPRelease] = []
    for title, href in parser.items:
        match = _TITLE.fullmatch(title)
        if match is None:
            continue
        family: Literal["farmacie", "addon"] = (
            "addon"
            if match.group("family").casefold() == "addon"
            else "farmacie"
        )
        shape: Literal["meerjaren", "lftgesl"] = (
            "lftgesl" if match.group("shape") == "lftgesl" else "meerjaren"
        )
        if family == "addon" and shape != "meerjaren":
            raise ValueError("unexpected Add-on release shape")
        releases.append(
            GIPRelease(
                title=title,
                family=family,
                shape=shape,
                period=match.group("period"),
                version_date=date.strptime(match.group("version"), "%d%m%Y"),
                download_url=AnyHttpUrl(
                    urljoin(str(authorization.landing_url), href)
                ),
            )
        )
    titles = sorted(item.title for item in releases)
    digest = sha256(("\n".join(titles) + "\n").encode()).hexdigest()
    if (
        len(releases) != authorization.expected_release_count
        or digest != authorization.expected_title_set_sha256
    ):
        raise ValueError("GIP medicine release inventory drifted")
    return GIPInventory(release_count=len(releases), releases=tuple(releases))
