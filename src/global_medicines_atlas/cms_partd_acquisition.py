"""Fail-closed inventory contracts for CMS Medicare Part D public data."""

from __future__ import annotations

import json
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
from typing import Literal, cast

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel

_CMS_HOST = "data.cms.gov"
_GOVERNMENT_WORKS = "https://www.usa.gov/government-works"


class CMSPartDAuthorization(FrozenModel):
    """Maintainer authority binding both Prompt 31 CMS data families."""

    schema_id: Literal[
        "global-medicines-atlas.cms-partd-acquisition-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date | None
    decision_status: Literal["pending", "approved_internal"]
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    formulary_catalog_url: AnyHttpUrl
    spending_catalog_url: AnyHttpUrl
    agreement_url: AnyHttpUrl
    license_url: AnyHttpUrl
    expected_formulary_release_count: Literal[30]
    expected_formulary_url_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_spending_resource_count: Literal[3]
    expected_spending_url_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_scope(self) -> CMSPartDAuthorization:
        urls = (
            self.formulary_catalog_url,
            self.spending_catalog_url,
            self.agreement_url,
        )
        if any(url.host not in {_CMS_HOST, "catalog.data.gov"} for url in urls):
            raise ValueError("CMS Part D evidence must stay on official hosts")
        if str(self.license_url).rstrip("/") != _GOVERNMENT_WORKS:
            raise ValueError("CMS Part D licence identity drifted")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError(
                "CMS Part D publication must remain separately gated"
            )
        if self.decision_status == "pending":
            if (
                self.decision_date is not None
                or self.acquisition_authorized
                or self.internal_retention_authorized
            ):
                raise ValueError(
                    "pending CMS Part D decision cannot authorize payloads"
                )
        elif (
            self.decision_date is None
            or not self.acquisition_authorized
            or not self.internal_retention_authorized
        ):
            raise ValueError(
                "approved CMS Part D acquisition requires dated authority"
            )
        return self

    def require_payload_authority(self) -> None:
        """Raise unless internal acquisition and retention are approved."""
        if self.decision_status != "approved_internal":
            raise PermissionError(
                "CMS Part D payload acquisition decision is pending"
            )


class CMSPartDInventory(FrozenModel):
    """Exact current public resource inventory, without source payloads."""

    formulary_release_count: int
    formulary_urls: tuple[AnyHttpUrl, ...]
    spending_resource_count: int
    spending_urls: tuple[AnyHttpUrl, ...]


class _JSONLD(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._active = False
        self._chunks: list[str] = []
        self.documents: list[dict[str, object]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() == "script" and dict(attrs).get("type") == (
            "application/ld+json"
        ):
            self._active = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._active:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._active:
            value = cast("object", json.loads("".join(self._chunks)))
            if isinstance(value, dict):
                self.documents.append(cast("dict[str, object]", value))
            self._active = False


def _resource_urls(payload: bytes) -> tuple[AnyHttpUrl, ...]:
    parser = _JSONLD()
    parser.feed(payload.decode("utf-8"))
    datasets = [
        item for item in parser.documents if item.get("@type") == "Dataset"
    ]
    if len(datasets) != 1:
        raise ValueError("expected one CMS Part D Dataset JSON-LD document")
    dataset = datasets[0]
    if dataset.get("license") != _GOVERNMENT_WORKS:
        raise ValueError("CMS Part D catalogue licence drifted")
    distributions = dataset.get("distribution")
    if not isinstance(distributions, list):
        raise TypeError("CMS Part D catalogue distributions are missing")
    urls: list[AnyHttpUrl] = []
    for distribution_value in cast("list[object]", distributions):
        if not isinstance(distribution_value, dict):
            raise TypeError("CMS Part D distribution must be an object")
        distribution = cast("dict[str, object]", distribution_value)
        raw_url = distribution.get("contentUrl")
        if not isinstance(raw_url, str):
            raise TypeError("CMS Part D distribution URL is missing")
        url = AnyHttpUrl(raw_url)
        if url.host != _CMS_HOST:
            raise ValueError(
                "CMS Part D distributions must stay on data.cms.gov"
            )
        urls.append(url)
    return tuple(sorted(urls, key=str))


def _digest(urls: tuple[AnyHttpUrl, ...]) -> str:
    return sha256(
        ("\n".join(str(url) for url in urls) + "\n").encode()
    ).hexdigest()


def parse_cms_partd_inventory(
    formulary_catalog: bytes,
    spending_catalog: bytes,
    *,
    authorization: CMSPartDAuthorization,
) -> CMSPartDInventory:
    """Bind the two official catalogues without downloading dataset payloads."""
    formulary = _resource_urls(formulary_catalog)
    spending = _resource_urls(spending_catalog)
    if (
        len(formulary) != authorization.expected_formulary_release_count
        or _digest(formulary) != authorization.expected_formulary_url_set_sha256
    ):
        raise ValueError("CMS Part D formulary release inventory drifted")
    if (
        len(spending) != authorization.expected_spending_resource_count
        or _digest(spending) != authorization.expected_spending_url_set_sha256
    ):
        raise ValueError("CMS Part D spending resource inventory drifted")
    if any(not str(url).endswith(".zip") for url in formulary):
        raise ValueError(
            "CMS Part D formulary inventory must contain ZIP releases"
        )
    if sum(str(url).endswith(".csv") for url in spending) != 1:
        raise ValueError("CMS Part D spending inventory must contain one CSV")
    return CMSPartDInventory(
        formulary_release_count=len(formulary),
        formulary_urls=formulary,
        spending_resource_count=len(spending),
        spending_urls=spending,
    )
