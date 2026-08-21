"""Bounded discovery of rights evidence on official source pages."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from typing import Final
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import AwareDatetime, Field

from .models import FrozenModel

DEFAULT_MAX_BYTES: Final = 2 * 1024 * 1024
RIGHTS_MARKERS: Final = (
    "copyright",
    "creative commons",
    "licence",
    "license",
    "legal notice",
    "open data",
    "reuse",
    "terms",
)


class RightsLink(FrozenModel):
    """Candidate official or linked rights policy discovered in HTML."""

    url: str
    label: str


class RightsDiscoveryReceipt(FrozenModel):
    """Bounded observation of one official source landing page."""

    source_url: str
    final_url: str | None = None
    observed_at: AwareDatetime
    outcome: str
    http_status: int | None = None
    media_type: str | None = None
    content_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    observed_bytes: int = Field(ge=0)
    rights_links: tuple[RightsLink, ...] = ()
    failure_reason: str | None = None


class _RightsLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.href: str | None = None
        self.text: list[str] = []
        self.links: list[RightsLink] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        values = dict(attrs)
        self.href = values.get("href")
        self.text = []

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self.href is None:
            return
        label = " ".join("".join(self.text).split())
        target = urljoin(self.base_url, self.href)
        searchable = f"{label} {target}".casefold()
        if any(marker in searchable for marker in RIGHTS_MARKERS):
            parsed = urlparse(target)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                self.links.append(RightsLink(url=target, label=label or target))
        self.href = None
        self.text = []


def discover_rights_evidence(
    source_url: str,
    *,
    client: httpx.Client,
    observed_at: AwareDatetime,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> RightsDiscoveryReceipt:
    """Fetch one public page and discover candidate rights-policy links."""

    try:
        with client.stream("GET", source_url) as response:
            content, observed_bytes, exceeded = _bounded_content(
                response,
                max_bytes,
            )
    except httpx.HTTPError as error:
        return RightsDiscoveryReceipt(
            source_url=source_url,
            observed_at=observed_at,
            outcome="failed",
            observed_bytes=0,
            failure_reason=type(error).__name__,
        )
    if exceeded:
        return RightsDiscoveryReceipt(
            source_url=source_url,
            final_url=str(response.url),
            observed_at=observed_at,
            outcome="too_large",
            http_status=response.status_code,
            media_type=response.headers.get("content-type"),
            observed_bytes=observed_bytes,
            failure_reason="rights discovery byte limit exceeded",
        )
    media_type = response.headers.get("content-type")
    links: tuple[RightsLink, ...] = ()
    if media_type is not None and "html" in media_type.casefold():
        parser = _RightsLinkParser(str(response.url))
        parser.feed(
            content.decode(response.encoding or "utf-8", errors="replace")
        )
        unique = {(item.url, item.label): item for item in parser.links}
        links = tuple(unique[key] for key in sorted(unique))
    return RightsDiscoveryReceipt(
        source_url=source_url,
        final_url=str(response.url),
        observed_at=observed_at,
        outcome="observed" if response.is_success else "http_error",
        http_status=response.status_code,
        media_type=media_type,
        content_sha256=hashlib.sha256(content).hexdigest(),
        observed_bytes=len(content),
        rights_links=links,
        failure_reason=(
            None if response.is_success else f"HTTP {response.status_code}"
        ),
    )


def _bounded_content(
    response: httpx.Response,
    max_bytes: int,
) -> tuple[bytes, int, bool]:
    chunks: list[bytes] = []
    observed_bytes = 0
    for chunk in response.iter_bytes():
        observed_bytes += len(chunk)
        if observed_bytes > max_bytes:
            return b"", observed_bytes, True
        chunks.append(chunk)
    return b"".join(chunks), observed_bytes, False
