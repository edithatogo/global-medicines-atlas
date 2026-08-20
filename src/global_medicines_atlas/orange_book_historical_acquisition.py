"""Authorized internal acquisition of public FDA Orange Book history."""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Iterable
from datetime import UTC, date, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urljoin, urlsplit

from pydantic import AnyHttpUrl, Field, model_validator

if TYPE_CHECKING:
    import httpx

from .acquisition import AcquisitionPolicy, acquire_source
from .bronze_admission import BronzeAdmissionState
from .bronze_landing import BronzeLanding, land_bronze_payload
from .bronze_recovery import reconstruct_bronze
from .models import FrozenModel
from .receipts import EvidenceClass, FailureReceipt
from .reuse_gate import ReuseGateDecision, evaluate_reuse_gate
from .source_catalog import MedicineDataSource, load_source_catalog
from .us_live_bronze import (
    AuthorizedUSSource,
    bind_us_acquisition_rights,
    copy_evidentiary_truth,
    endpoint_source,
    recoverable_us_source_record_batch,
    write_private_corpus_archive,
)

ARCHIVE_FILENAME = "orange-book-history.private.tar"
MANIFEST_FILENAME = "orange-book-history.manifest.json"
CHECKSUM_FILENAME = "SHA256SUMS"
_ALLOWED_HOSTS = frozenset({"www.fda.gov", "wayback.archive-it.org"})
_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)


class OrangeBookSeed(FrozenModel):
    """One approved exact discovery or current-release surface."""

    release_id: str = Field(min_length=1)
    url: AnyHttpUrl
    media_hint: Literal["zip", "pdf", "html"]
    discover_links: bool = False

    @model_validator(mode="after")
    def official_host(self) -> OrangeBookSeed:
        if self.url.host not in _ALLOWED_HOSTS:
            raise ValueError(
                "seed must use an official FDA or FDA archive host"
            )
        return self


class OrangeBookHistoricalAuthorization(FrozenModel):
    """Explicit maintainer authority for bounded internal acquisition."""

    schema_id: Literal[
        "global-medicines-atlas.orange-book-historical-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    max_releases: int = Field(ge=1, le=512)
    max_total_bytes: int = Field(ge=1, le=8 * 1024 * 1024 * 1024)
    max_release_bytes: int = Field(ge=1, le=512 * 1024 * 1024)
    archive_request_interval_seconds: float = Field(ge=0, le=5)
    discovery_required: bool
    seeds: tuple[OrangeBookSeed, ...]

    @model_validator(mode="after")
    def internal_only(self) -> OrangeBookHistoricalAuthorization:
        if not self.acquisition_authorized:
            raise ValueError(
                "historical acquisition must be explicitly authorized"
            )
        if not self.internal_retention_authorized:
            raise ValueError("internal retention must be explicitly authorized")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("authorization must remain internal-only")
        ids = [seed.release_id for seed in self.seeds]
        if len(ids) != len(set(ids)):
            raise ValueError("seed release IDs must be unique")
        if self.discovery_required and not any(
            seed.discover_links for seed in self.seeds
        ):
            raise ValueError("at least one discovery seed is required")
        return self


class HistoricalRelease(FrozenModel):
    """One discovered or explicitly seeded Orange Book release."""

    release_id: str
    title: str
    url: AnyHttpUrl
    media_hint: Literal["zip", "pdf", "html"]
    discovery_source: str


class HistoricalAcquisitionItem(FrozenModel):
    """Redacted acquisition outcome containing no source payload fields."""

    release_id: str
    url: AnyHttpUrl
    status: Literal["succeeded", "failed"]
    acquisition_id: str | None = None
    payload_sha256: str | None = None
    payload_byte_count: int | None = None
    admission_state: str | None = None
    source_records_projected: bool = False
    failure_code: str | None = None


class OrangeBookHistoricalManifest(FrozenModel):
    """Private archive receipt for the historical Orange Book exercise."""

    schema_id: Literal[
        "global-medicines-atlas.orange-book-historical-corpus"
    ] = "global-medicines-atlas.orange-book-historical-corpus"
    schema_version: Literal[1] = 1
    exercised_at: datetime
    evidence_class: Literal["live_internal_historical"] = (
        "live_internal_historical"
    )
    external_publication_performed: Literal[False] = False
    historical_inventory_complete: bool
    release_count: int
    succeeded_count: int
    failed_count: int
    accepted_count: int
    quarantined_count: int
    recovered_count: int
    source_record_projection_count: int
    items: tuple[HistoricalAcquisitionItem, ...]
    archive_filename: Literal["orange-book-history.private.tar"] = (
        ARCHIVE_FILENAME
    )
    archive_sha256: str
    archive_byte_count: int


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() == "a":
            self._href = next(
                (value for key, value in attrs if key == "href"), None
            )
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


def _release_media(url: str, title: str) -> Literal["zip", "pdf", "html"]:
    lowered = f"{url} {title}".casefold()
    if ".zip" in lowered:
        return "zip"
    if ".pdf" in lowered or "/media/" in lowered:
        return "pdf"
    return "html"


def discover_monthly_releases(
    payload: bytes, base_url: str
) -> tuple[HistoricalRelease, ...]:
    """Extract official month-labelled release links from one FDA index."""
    parser = _AnchorParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    releases: dict[str, HistoricalRelease] = {}
    for href, title in parser.links:
        lowered = title.casefold()
        if not any(month in lowered for month in _MONTHS):
            continue
        if not any(character.isdigit() for character in title):
            continue
        absolute = urljoin(base_url, href).split("#", 1)[0]
        parsed = urlsplit(absolute)
        if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
            continue
        release_id = f"monthly-{sha256(absolute.encode()).hexdigest()[:16]}"
        releases[absolute] = HistoricalRelease(
            release_id=release_id,
            title=" ".join(title.split()),
            url=AnyHttpUrl(absolute),
            media_hint=_release_media(absolute, title),
            discovery_source=base_url,
        )
    return tuple(releases[url] for url in sorted(releases))


def _catalog_source(
    catalog: tuple[MedicineDataSource, ...],
) -> MedicineDataSource:
    return next(
        source for source in catalog if source.source_id == "us-fda-orange-book"
    )


def _acquire_one(
    release: HistoricalRelease,
    *,
    repository_root: Path,
    downloads: Path,
    bronze: Path,
    source: MedicineDataSource,
    decision: ReuseGateDecision,
    observed_at: datetime,
    max_bytes: int,
    transport: httpx.BaseTransport | None,
) -> tuple[HistoricalAcquisitionItem, bytes | None]:
    item = AuthorizedUSSource(
        source_id="us-fda-orange-book",
        endpoint=release.url,
        media_hint=release.media_hint,
        rights_profile="government_public_domain_policy_review",
        max_bytes=max_bytes,
    )
    bound_source = endpoint_source(item, (source,))
    destination = downloads / f"{release.release_id}.{release.media_hint}"
    receipt = acquire_source(
        item.source_id,
        destination,
        repository_root=repository_root,
        catalog=(bound_source,),
        policy=AcquisitionPolicy(
            timeout_seconds=90,
            max_bytes=max_bytes,
            max_redirects=5,
            allowed_content_types=(
                "application/pdf",
                "application/zip",
                "application/octet-stream",
                "application/x-zip-compressed",
                "binary/octet-stream",
                "text/html",
                "text/plain",
            ),
        ),
        transport=transport,
        evidence_class=EvidenceClass.LIVE,
        clock=lambda: observed_at,
        reuse_decision=decision,
    )
    if isinstance(receipt, FailureReceipt):
        return HistoricalAcquisitionItem(
            release_id=release.release_id,
            url=release.url,
            status="failed",
            failure_code=receipt.failure_code,
        ), None
    payload = destination.read_bytes()
    bound = bind_us_acquisition_rights(item, receipt, observed_at)
    source_records = (
        recoverable_us_source_record_batch(item.source_id, payload, "zip")
        if release.media_hint == "zip"
        else None
    )
    landing = land_bronze_payload(
        payload,
        bound,
        bronze_root=bronze,
        media_hint=release.media_hint,
        reuse=decision,
        admission_decided_at=observed_at,
        transformation_completed_at=observed_at,
        source_records=source_records,
    )
    temporal = bound.temporal
    if temporal is None:
        raise ValueError("historical acquisition requires temporal identity")
    return HistoricalAcquisitionItem(
        release_id=release.release_id,
        url=release.url,
        status="succeeded",
        acquisition_id=temporal.acquisition_id,
        payload_sha256=bound.payload.sha256,
        payload_byte_count=bound.payload.byte_count,
        admission_state=landing.admission.state.value,
        source_records_projected=(
            isinstance(landing, BronzeLanding)
            and landing.source_records_path is not None
        ),
    ), payload


def exercise_orange_book_history(  # ruff: ignore[too-many-locals,too-many-statements]
    *,
    repository_root: Path,
    output_dir: Path,
    authorization_path: Path,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    observed_at: datetime | None = None,
) -> OrangeBookHistoricalManifest:
    """Discover, acquire, land, recover, and privately archive Orange Book history."""
    authorization = OrangeBookHistoricalAuthorization.model_validate_json(
        authorization_path.read_bytes()
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = output_dir / "runs" / "corpus"
    bronze = corpus / "bronze"
    downloads = corpus / "downloads"
    evidence = corpus / "evidence"
    evidence.mkdir(parents=True)
    shutil.copy2(authorization_path, evidence / authorization_path.name)
    sources = tuple(load_source_catalog() if catalog is None else catalog)
    source = _catalog_source(sources)
    decision = evaluate_reuse_gate(
        source.source_id, repository_root=repository_root, catalog=sources
    )
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("acquisition time must be timezone-aware")

    seeded = tuple(
        HistoricalRelease(
            release_id=seed.release_id,
            title=seed.release_id,
            url=seed.url,
            media_hint=seed.media_hint,
            discovery_source="authorization",
        )
        for seed in authorization.seeds
    )
    results: list[HistoricalAcquisitionItem] = []
    payloads: dict[str, bytes] = {}
    total_bytes = 0

    def acquire(release: HistoricalRelease) -> None:
        nonlocal total_bytes
        if release.url.host == "wayback.archive-it.org":
            time.sleep(authorization.archive_request_interval_seconds)
        remaining = authorization.max_total_bytes - total_bytes
        if remaining <= 0:
            raise ValueError(
                "historical acquisition exceeded total byte budget"
            )
        result, payload = _acquire_one(
            release,
            repository_root=output_dir,
            downloads=downloads,
            bronze=bronze,
            source=source,
            decision=decision,
            observed_at=timestamp,
            max_bytes=min(authorization.max_release_bytes, remaining),
            transport=transport,
        )
        results.append(result)
        if payload is not None:
            payloads[release.release_id] = payload
            total_bytes += len(payload)

    for release in seeded:
        acquire(release)

    discovered: dict[str, HistoricalRelease] = {}
    discoverable = {
        seed.release_id for seed in authorization.seeds if seed.discover_links
    }
    for release in seeded:
        payload = payloads.get(release.release_id)
        if release.release_id not in discoverable or payload is None:
            continue
        for candidate in discover_monthly_releases(payload, str(release.url)):
            discovered[str(candidate.url)] = candidate
    seed_urls = {str(release.url) for release in seeded}
    releases = tuple(
        discovered[url] for url in sorted(discovered) if url not in seed_urls
    )
    if len(seeded) + len(releases) > authorization.max_releases:
        raise ValueError("discovered release count exceeds authorization")
    for release in releases:
        acquire(release)

    inventory = seeded + releases
    (evidence / "release-inventory.json").write_text(
        json.dumps(
            [release.model_dump(mode="json") for release in inventory],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (evidence / "redacted-acquisition-results.json").write_text(
        json.dumps(
            [result.model_dump(mode="json") for result in results],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    clean_room = corpus / "clean-room"
    copy_evidentiary_truth(bronze, clean_room)
    recovery = reconstruct_bronze(
        clean_room,
        fail_closed_on_incomplete=False,
        source_record_factory=recoverable_us_source_record_batch,
    )
    archive_path = output_dir / ARCHIVE_FILENAME
    archive_digest, archive_size = write_private_corpus_archive(
        corpus, archive_path
    )
    succeeded = tuple(item for item in results if item.status == "succeeded")
    accepted = tuple(
        item
        for item in succeeded
        if item.admission_state == BronzeAdmissionState.ACCEPTED.value
    )
    quarantined = tuple(
        item
        for item in succeeded
        if item.admission_state == BronzeAdmissionState.QUARANTINED.value
    )
    manifest = OrangeBookHistoricalManifest(
        exercised_at=timestamp,
        historical_inventory_complete=False,
        release_count=len(inventory),
        succeeded_count=len(succeeded),
        failed_count=len(results) - len(succeeded),
        accepted_count=len(accepted),
        quarantined_count=len(quarantined),
        recovered_count=len(recovery.landings),
        source_record_projection_count=sum(
            item.source_records_projected for item in succeeded
        ),
        items=tuple(results),
        archive_sha256=archive_digest,
        archive_byte_count=archive_size,
    )
    (output_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / CHECKSUM_FILENAME).write_text(
        f"{archive_digest}  {ARCHIVE_FILENAME}\n", encoding="utf-8"
    )
    return manifest
