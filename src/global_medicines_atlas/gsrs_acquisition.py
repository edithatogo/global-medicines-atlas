"""Fail-closed preflight contracts for FDA GSRS/UNII acquisition."""

from __future__ import annotations

import re
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import urljoin

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel

SOURCE_ID = "us-gsrs-unii"
_PRECISION_FDA_HOST = "precision.fda.gov"
_EXPECTED_RELEASE_COUNT = 68
_DATA_PATTERN = re.compile(
    r"^archive/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})/"
    r"UNII_Data[^/]*\.zip$"
)
_NAMES_PATTERN = re.compile(
    r"^archive/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})/"
    r"UNIIs[^/]*\.zip$"
)


class GSRSRelease(FrozenModel):
    """One paired, source-native FDA UNII release."""

    release_date: date
    data_url: AnyHttpUrl
    names_url: AnyHttpUrl

    @model_validator(mode="after")
    def official_hosts_and_matching_dates(self) -> GSRSRelease:
        if (
            self.data_url.host != _PRECISION_FDA_HOST
            or self.names_url.host != _PRECISION_FDA_HOST
        ):
            raise ValueError("GSRS releases must stay on precision.fda.gov")
        expected = self.release_date.isoformat()
        if expected not in str(self.data_url) or expected not in str(
            self.names_url
        ):
            raise ValueError("GSRS release URLs must match their release date")
        return self


class GSRSAuthorization(FrozenModel):
    """Source-specific rights and acquisition decision for GSRS/UNII."""

    schema_id: Literal[
        "global-medicines-atlas.gsrs-unii-acquisition-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date | None
    decision_status: Literal["pending", "approved_internal"]
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    archive_index_url: AnyHttpUrl
    licensing_url: AnyHttpUrl
    expected_release_count: int = Field(ge=1, le=256)
    expected_first_release: date
    expected_last_release: date
    expected_release_dates_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_scope(self) -> GSRSAuthorization:
        if self.archive_index_url.host != _PRECISION_FDA_HOST:
            raise ValueError(
                "GSRS archive index must stay on precision.fda.gov"
            )
        if self.licensing_url.host != "gsrs.ncats.nih.gov":
            raise ValueError("GSRS licensing evidence must stay on NCATS")
        if self.expected_release_count != _EXPECTED_RELEASE_COUNT:
            raise ValueError("GSRS authorization must bind all 68 releases")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("GSRS publication must remain separately gated")
        if self.decision_status == "pending":
            if (
                self.decision_date is not None
                or self.acquisition_authorized
                or self.internal_retention_authorized
            ):
                raise ValueError(
                    "pending GSRS decision cannot authorize payloads"
                )
        elif (
            self.decision_date is None
            or not self.acquisition_authorized
            or not self.internal_retention_authorized
        ):
            raise ValueError(
                "approved GSRS acquisition requires dated authority"
            )
        return self

    def require_payload_authority(self) -> None:
        """Raise unless the maintainer approved internal payload acquisition."""

        if self.decision_status != "approved_internal":
            raise PermissionError(
                "GSRS payload acquisition decision is pending"
            )


class GSRSInventory(FrozenModel):
    """Complete paired release inventory derived from the FDA archive index."""

    source_id: Literal["us-gsrs-unii"] = SOURCE_ID
    release_count: int
    first_release: date
    last_release: date
    releases: tuple[GSRSRelease, ...]


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(href)


def parse_gsrs_release_inventory(
    payload: bytes,
    *,
    base_url: AnyHttpUrl,
    authorization: GSRSAuthorization,
) -> GSRSInventory:
    """Parse and validate every paired dated FDA UNII archive release."""

    parser = _Links()
    parser.feed(payload.decode("utf-8"))
    data: dict[date, str] = {}
    names: dict[date, str] = {}
    for href in parser.hrefs:
        for pattern, target in ((_DATA_PATTERN, data), (_NAMES_PATTERN, names)):
            match = pattern.fullmatch(href)
            if match is None:
                continue
            release_date = date.fromisoformat(match.group("date"))
            absolute = urljoin(str(base_url), href)
            existing = target.setdefault(release_date, absolute)
            if existing != absolute:
                raise ValueError("conflicting GSRS release URL")
    if set(data) != set(names):
        raise ValueError("GSRS data and name release inventories differ")
    dates = sorted(data)
    dates_sha256 = sha256(
        ("\n".join(item.isoformat() for item in dates) + "\n").encode()
    ).hexdigest()
    if (
        len(dates) != authorization.expected_release_count
        or dates[0] != authorization.expected_first_release
        or dates[-1] != authorization.expected_last_release
        or dates_sha256 != authorization.expected_release_dates_sha256
    ):
        raise ValueError("GSRS release inventory drifted")
    releases = tuple(
        GSRSRelease(
            release_date=item,
            data_url=AnyHttpUrl(data[item]),
            names_url=AnyHttpUrl(names[item]),
        )
        for item in dates
    )
    return GSRSInventory(
        release_count=len(releases),
        first_release=dates[0],
        last_release=dates[-1],
        releases=releases,
    )
