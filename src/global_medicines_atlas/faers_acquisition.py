"""Complete internal acquisition of official FDA AERS/FAERS ASCII releases."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterable
from datetime import UTC, date, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urljoin, urlsplit

import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, Field, model_validator

if TYPE_CHECKING:
    import httpx

from .acquisition import (
    AcquisitionPolicy,
    acquire_source,
    acquire_source_by_ranges,
)
from .bronze_admission import (
    BronzeAdmissionState,
    latest_admission_for_receipt,
)
from .bronze_landing import (
    BronzeAcquisition,
    BronzeLanding,
    land_bronze_payload,
    write_rebuildable_layers,
)
from .bronze_recovery import reconstruct_bronze
from .models import FrozenModel
from .receipts import (
    EvidenceClass,
    FailureReceipt,
    SourceReceipt,
    temporal_identity_from_source,
)
from .reuse_gate import evaluate_reuse_gate
from .source_catalog import MedicineDataSource, load_source_catalog
from .us_live_bronze import (
    AuthorizedUSSource,
    bind_us_acquisition_rights,
    copy_evidentiary_truth,
    endpoint_source,
    recoverable_us_source_record_batch,
    write_private_corpus_archive,
)

ARCHIVE_FILENAME = "faers-history.private.tar"
MANIFEST_FILENAME = "faers-history.manifest.json"
CHECKSUM_FILENAME = "SHA256SUMS"
_SOURCE_ID = "us-fda-faers"
_ALLOWED_HOSTS = frozenset({"fis.fda.gov", "www.fda.gov"})
_QUARTER = re.compile(r"^(20\d{2})-Q([1-4])$")
_ASCII_RELEASE = re.compile(
    r"/(?:aers|faers)_ascii_(20\d{2})q([1-4])\.zip$", re.IGNORECASE
)
_QUARTERS_PER_YEAR = 4


def _quarter_ordinal(value: str) -> int:
    match = _QUARTER.fullmatch(value)
    if match is None:
        raise ValueError("release identity must use YYYY-QN")
    return int(match.group(1)) * 4 + int(match.group(2)) - 1


def _quarter_bounds(value: str) -> tuple[datetime, datetime]:
    match = _QUARTER.fullmatch(value)
    if match is None:  # pragma: no cover - validated model input
        raise ValueError("release identity must use YYYY-QN")
    year = int(match.group(1))
    quarter = int(match.group(2))
    start_month = 1 + (quarter - 1) * 3
    start = datetime(year, start_month, 1, tzinfo=UTC)
    end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if quarter == _QUARTERS_PER_YEAR
        else datetime(year, start_month + 3, 1, tzinfo=UTC)
    )
    return start, end


class FAERSDocument(FrozenModel):
    """One official documentation or discovery surface."""

    document_id: str = Field(min_length=1)
    url: AnyHttpUrl
    discover_releases: bool = False

    @model_validator(mode="after")
    def official_host(self) -> FAERSDocument:
        if self.url.host not in _ALLOWED_HOSTS:
            raise ValueError("documentation must use an official FDA host")
        return self


class FAERSAuthorization(FrozenModel):
    """Existing maintainer authority narrowed to exact quarterly coverage."""

    schema_id: Literal["global-medicines-atlas.faers-live-authorization"]
    schema_version: Literal[1]
    decision_date: date
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    expected_first_release: str
    expected_last_release: str
    expected_release_count: int = Field(ge=1, le=128)
    max_releases: int = Field(ge=1, le=128)
    max_total_bytes: int = Field(ge=1, le=32 * 1024 * 1024 * 1024)
    max_release_bytes: int = Field(ge=1, le=1024 * 1024 * 1024)
    range_chunk_bytes: int = Field(ge=64, le=64 * 1024 * 1024)
    range_concurrency: int = Field(ge=1, le=8)
    documentation: tuple[FAERSDocument, ...]

    @model_validator(mode="after")
    def exact_internal_scope(self) -> FAERSAuthorization:
        if not self.acquisition_authorized:
            raise ValueError("FAERS acquisition must be explicitly authorized")
        if not self.internal_retention_authorized:
            raise ValueError("internal retention must be authorized")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("authorization must remain internal-only")
        contiguous = (
            _quarter_ordinal(self.expected_last_release)
            - _quarter_ordinal(self.expected_first_release)
            + 1
        )
        if self.expected_release_count != contiguous:
            raise ValueError(
                "expected release count must equal contiguous quarter count"
            )
        if self.max_releases != self.expected_release_count:
            raise ValueError("max releases must equal expected release count")
        ids = [item.document_id for item in self.documentation]
        if len(ids) != len(set(ids)):
            raise ValueError("documentation IDs must be unique")
        if not any(item.discover_releases for item in self.documentation):
            raise ValueError("one documentation surface must discover releases")
        return self


class FAERSRelease(FrozenModel):
    """One exact official source-faithful quarterly representation."""

    release_id: str
    url: AnyHttpUrl
    representation: Literal["ascii"] = "ascii"


class FAERSCorpusItem(FrozenModel):
    """Redacted acquisition result with no report-level source fields."""

    item_id: str
    kind: Literal["documentation", "quarterly_release"]
    url: AnyHttpUrl
    status: Literal["succeeded", "failed"]
    acquisition_id: str | None = None
    payload_sha256: str | None = None
    payload_byte_count: int | None = None
    admission_state: str | None = None
    source_records_projected: bool = False
    source_record_count: int | None = Field(default=None, ge=0)
    failure_code: str | None = None


class FAERSCorpusManifest(FrozenModel):
    """Verified private archive receipt for the complete quarterly exercise."""

    schema_id: Literal["global-medicines-atlas.faers-live-corpus"] = (
        "global-medicines-atlas.faers-live-corpus"
    )
    schema_version: Literal[1] = 1
    exercised_at: datetime
    evidence_class: Literal["live_internal_historical"] = (
        "live_internal_historical"
    )
    external_publication_performed: Literal[False] = False
    first_release: str
    last_release: str
    release_count: int
    documentation_count: int
    succeeded_count: int
    failed_count: int
    accepted_count: int
    quarantined_count: int
    recovered_count: int
    source_record_projection_count: int
    source_record_rows: int
    recovered_source_record_projection_count: int
    source_record_parquet_pairs_byte_identical: int
    quarter_coverage_complete: bool
    items: tuple[FAERSCorpusItem, ...]
    archive_filename: Literal["faers-history.private.tar"] = ARCHIVE_FILENAME
    archive_sha256: str
    archive_byte_count: int


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "a":
            return
        href = next((value for key, value in attrs if key == "href"), None)
        if href:
            self.hrefs.append(href)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _byte_identical_source_record_pairs(bronze: Path, clean_room: Path) -> int:
    relative_products = {
        path.relative_to(bronze / "parquet"): path
        for path in (bronze / "parquet").rglob("source_records.parquet")
    }
    return sum(
        recovered.is_file()
        and _file_sha256(original) == _file_sha256(recovered)
        for relative, original in relative_products.items()
        if (recovered := clean_room / "parquet" / relative)
    )


def _receipt_indexes(
    bronze: Path,
) -> tuple[dict[str, SourceReceipt], dict[str, SourceReceipt]]:
    by_uri: dict[str, SourceReceipt] = {}
    by_version: dict[str, SourceReceipt] = {}
    for path in (bronze / "receipts" / _SOURCE_ID).glob("*.json"):
        receipt = SourceReceipt.model_validate_json(path.read_bytes())
        uri = str(receipt.retrieval.uri)
        if uri in by_uri:
            raise ValueError(f"duplicate FAERS receipt URI: {uri}")
        by_uri[uri] = receipt
        temporal = receipt.temporal
        if temporal is not None and temporal.source_version is not None:
            version = temporal.source_version
            if version in by_version:
                raise ValueError(f"duplicate FAERS source version: {version}")
            by_version[version] = receipt
    return by_uri, by_version


def _existing_item(
    *,
    item_id: str,
    kind: Literal["documentation", "quarterly_release"],
    url: AnyHttpUrl,
    receipt: SourceReceipt,
    bronze: Path,
) -> FAERSCorpusItem:
    temporal = receipt.temporal
    if temporal is None:
        raise ValueError("FAERS acquisition requires temporal identity")
    receipt_path = (
        bronze / "receipts" / _SOURCE_ID / f"{temporal.acquisition_id}.json"
    )
    admission = latest_admission_for_receipt(
        receipt_path=receipt_path, receipt=receipt
    )
    product = (
        bronze
        / "parquet"
        / _SOURCE_ID
        / temporal.acquisition_id
        / "source_records.parquet"
    )
    projected = product.is_file()
    return FAERSCorpusItem(
        item_id=item_id,
        kind=kind,
        url=url,
        status="succeeded",
        acquisition_id=temporal.acquisition_id,
        payload_sha256=receipt.payload.sha256,
        payload_byte_count=receipt.payload.byte_count,
        admission_state=admission.state.value,
        source_records_projected=projected,
        source_record_count=(
            pq.ParquetFile(product).metadata.num_rows if projected else None
        ),
    )


def discover_faers_ascii_releases(
    payload: bytes,
    base_url: str = "https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html",
) -> tuple[FAERSRelease, ...]:
    """Discover one official ASCII representation for each public quarter."""
    parser = _AnchorParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    releases: dict[str, FAERSRelease] = {}
    for href in parser.hrefs:
        absolute = urljoin(base_url, href).split("#", 1)[0]
        parsed = urlsplit(absolute)
        if parsed.scheme != "https" or parsed.hostname != "fis.fda.gov":
            continue
        match = _ASCII_RELEASE.search(parsed.path)
        if match is None:
            continue
        release_id = f"{match.group(1)}-Q{match.group(2)}"
        candidate = FAERSRelease.model_validate({
            "release_id": release_id,
            "url": absolute,
        })
        prior = releases.get(release_id)
        if (
            prior is not None
            and str(prior.url).casefold() != absolute.casefold()
        ):
            raise ValueError(f"multiple ASCII URLs found for {release_id}")
        releases[release_id] = candidate
    return tuple(
        releases[key] for key in sorted(releases, key=_quarter_ordinal)
    )


def _catalog_source(
    catalog: tuple[MedicineDataSource, ...],
) -> MedicineDataSource:
    return next(source for source in catalog if source.source_id == _SOURCE_ID)


def _landing_item(
    *,
    item_id: str,
    kind: Literal["documentation", "quarterly_release"],
    url: AnyHttpUrl,
    receipt: SourceReceipt,
    landing: BronzeAcquisition | BronzeLanding,
    source_record_count: int | None,
) -> FAERSCorpusItem:
    temporal = receipt.temporal
    if temporal is None:
        raise ValueError("FAERS acquisition requires temporal identity")
    return FAERSCorpusItem(
        item_id=item_id,
        kind=kind,
        url=url,
        status="succeeded",
        acquisition_id=temporal.acquisition_id,
        payload_sha256=receipt.payload.sha256,
        payload_byte_count=receipt.payload.byte_count,
        admission_state=landing.admission.state.value,
        source_records_projected=(
            isinstance(landing, BronzeLanding)
            and landing.source_records_path is not None
        ),
        source_record_count=source_record_count,
    )


def exercise_faers_history(  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements]
    *,
    repository_root: Path,
    output_dir: Path,
    authorization_path: Path,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    observed_at: datetime | None = None,
    resume: bool = False,
) -> FAERSCorpusManifest:
    """Acquire, project, recover, and privately archive every public quarter."""
    authorization = FAERSAuthorization.model_validate_json(
        authorization_path.read_bytes()
    )
    output_nonempty = output_dir.exists() and any(output_dir.iterdir())
    if output_nonempty and not resume:
        raise FileExistsError("output directory must be empty")
    if resume and not output_nonempty:
        raise FileNotFoundError("resume requires an existing partial corpus")
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = output_dir / "runs" / "corpus"
    bronze = corpus / "bronze"
    downloads = corpus / "downloads"
    evidence = corpus / "evidence"
    evidence.mkdir(parents=True, exist_ok=resume)
    copied_authorization = evidence / authorization_path.name
    if resume:
        if (
            not copied_authorization.is_file()
            or copied_authorization.read_bytes()
            != authorization_path.read_bytes()
        ):
            raise ValueError(
                "resume authorization does not match partial corpus"
            )
        if any(
            (output_dir / filename).exists()
            for filename in (
                ARCHIVE_FILENAME,
                MANIFEST_FILENAME,
                CHECKSUM_FILENAME,
            )
        ):
            raise FileExistsError("resume refuses a finalized FAERS corpus")
    else:
        shutil.copy2(authorization_path, copied_authorization)
    sources = tuple(load_source_catalog() if catalog is None else catalog)
    source = _catalog_source(sources)
    decision = evaluate_reuse_gate(
        _SOURCE_ID, repository_root=repository_root, catalog=sources
    )
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("acquisition time must be timezone-aware")
    results: list[FAERSCorpusItem] = []
    discovery_payloads: list[tuple[bytes, str]] = []
    receipts_by_uri, receipts_by_version = (
        _receipt_indexes(bronze) if resume else ({}, {})
    )

    for document in authorization.documentation:
        item = AuthorizedUSSource(
            source_id=_SOURCE_ID,
            endpoint=document.url,
            media_hint="html",
            rights_profile="government_public_domain_policy_review",
            max_bytes=16 * 1024 * 1024,
        )
        bound_source = endpoint_source(item, (source,))
        destination = (
            downloads / "documentation" / f"{document.document_id}.html"
        )
        if resume and destination.is_file():
            receipt = receipts_by_uri.get(str(document.url))
            if receipt is None or not receipt.payload.matches(
                destination.read_bytes()
            ):
                raise ValueError(
                    "partial documentation lacks matching receipt: "
                    f"{document.document_id}"
                )
            results.append(
                _existing_item(
                    item_id=document.document_id,
                    kind="documentation",
                    url=document.url,
                    receipt=receipt,
                    bronze=bronze,
                )
            )
            if document.discover_releases:
                discovery_payloads.append((
                    destination.read_bytes(),
                    str(document.url),
                ))
            continue
        receipt = acquire_source(
            _SOURCE_ID,
            destination,
            repository_root=output_dir,
            catalog=(bound_source,),
            policy=AcquisitionPolicy(
                timeout_seconds=90,
                max_bytes=item.max_bytes,
                max_redirects=5,
                allowed_content_types=("text/html", "text/plain"),
            ),
            transport=transport,
            evidence_class=EvidenceClass.LIVE,
            clock=lambda: timestamp,
            reuse_decision=decision,
        )
        if isinstance(receipt, FailureReceipt):
            results.append(
                FAERSCorpusItem(
                    item_id=document.document_id,
                    kind="documentation",
                    url=document.url,
                    status="failed",
                    failure_code=receipt.failure_code,
                )
            )
            continue
        payload = destination.read_bytes()
        bound = bind_us_acquisition_rights(item, receipt, timestamp)
        landing = land_bronze_payload(
            payload,
            bound,
            bronze_root=bronze,
            media_hint="html",
            reuse=decision,
            admission_decided_at=timestamp,
            transformation_completed_at=timestamp,
        )
        results.append(
            _landing_item(
                item_id=document.document_id,
                kind="documentation",
                url=document.url,
                receipt=bound,
                landing=landing,
                source_record_count=None,
            )
        )
        if document.discover_releases:
            discovery_payloads.append((payload, str(document.url)))

    discovered: dict[str, FAERSRelease] = {}
    for payload, base_url in discovery_payloads:
        for release in discover_faers_ascii_releases(payload, base_url):
            discovered[release.release_id] = release
    releases = tuple(
        discovered[key] for key in sorted(discovered, key=_quarter_ordinal)
    )
    expected_ids = tuple(
        f"{ordinal // 4}-Q{ordinal % 4 + 1}"
        for ordinal in range(
            _quarter_ordinal(authorization.expected_first_release),
            _quarter_ordinal(authorization.expected_last_release) + 1,
        )
    )
    if (
        tuple(item.release_id for item in releases) != expected_ids
        or len(releases) != authorization.expected_release_count
        or len(releases) > authorization.max_releases
    ):
        raise ValueError(
            "official FAERS inventory does not match authorization"
        )
    (evidence / "release-inventory.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in releases],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    total_bytes = 0
    for release in releases:
        remaining = authorization.max_total_bytes - total_bytes
        if remaining <= 0:
            raise ValueError("FAERS acquisition exceeded total byte budget")
        item = AuthorizedUSSource(
            source_id=_SOURCE_ID,
            endpoint=release.url,
            media_hint="zip",
            rights_profile="government_public_domain_policy_review",
            max_bytes=min(authorization.max_release_bytes, remaining),
        )
        bound_source = endpoint_source(item, (source,))
        destination = downloads / "releases" / f"{release.release_id}.zip"
        if resume and destination.is_file():
            receipt = receipts_by_version.get(release.release_id)
            payload = destination.read_bytes()
            if receipt is None or not receipt.payload.matches(payload):
                raise ValueError(
                    "partial release lacks matching receipt: "
                    f"{release.release_id}"
                )
            total_bytes += len(payload)
            existing = _existing_item(
                item_id=release.release_id,
                kind="quarterly_release",
                url=release.url,
                receipt=receipt,
                bronze=bronze,
            )
            if existing.source_records_projected:
                results.append(existing)
                continue
            bound = receipt
            temporal = bound.temporal
            if temporal is None:  # pragma: no cover - receipt validation
                raise ValueError("FAERS acquisition requires temporal identity")
            landing_timestamp = temporal.retrieved_at
            repair_existing = True
        else:
            receipt = acquire_source_by_ranges(
                _SOURCE_ID,
                destination,
                repository_root=output_dir,
                chunk_bytes=authorization.range_chunk_bytes,
                catalog=(bound_source,),
                policy=AcquisitionPolicy(
                    timeout_seconds=120,
                    max_bytes=item.max_bytes,
                    max_attempts=3,
                    max_concurrency_per_host=authorization.range_concurrency,
                    max_redirects=3,
                    allowed_content_types=(
                        "application/zip",
                        "application/x-zip-compressed",
                        "application/octet-stream",
                        "binary/octet-stream",
                    ),
                ),
                transport=transport,
                evidence_class=EvidenceClass.LIVE,
                clock=lambda: timestamp,
                reuse_decision=decision,
                source_native_version=release.release_id,
            )
            if isinstance(receipt, FailureReceipt):
                results.append(
                    FAERSCorpusItem(
                        item_id=release.release_id,
                        kind="quarterly_release",
                        url=release.url,
                        status="failed",
                        failure_code=receipt.failure_code,
                    )
                )
                continue
            payload = destination.read_bytes()
            total_bytes += len(payload)
            valid_from, valid_to = _quarter_bounds(release.release_id)
            temporal = temporal_identity_from_source(
                retrieved_at=timestamp,
                source_id=_SOURCE_ID,
                payload_sha256=receipt.payload.sha256,
                valid_from=valid_from,
                valid_to=valid_to,
                source_version=release.release_id,
                original_uri=str(release.url),
            )
            versioned = receipt.model_copy(update={"temporal": temporal})
            bound = bind_us_acquisition_rights(item, versioned, timestamp)
            landing_timestamp = timestamp
            repair_existing = False
        source_records = recoverable_us_source_record_batch(
            _SOURCE_ID, payload, "zip"
        )
        if repair_existing:
            content_id = temporal.content_id or bound.payload.sha256
            payload_matches = tuple(
                (bronze / "payloads" / "by_content" / content_id).glob(
                    "payload.*"
                )
            )
            if len(payload_matches) != 1:
                raise ValueError(
                    "partial release lacks exactly one immutable payload"
                )
            receipt_path = (
                bronze
                / "receipts"
                / _SOURCE_ID
                / f"{temporal.acquisition_id}.json"
            )
            admission = latest_admission_for_receipt(
                receipt_path=receipt_path, receipt=bound
            )
            product_dir = (
                bronze / "parquet" / _SOURCE_ID / temporal.acquisition_id
            )
            lineage_dir = (
                bronze / "lineage" / _SOURCE_ID / temporal.acquisition_id
            )
            write_rebuildable_layers(
                bound,
                payload,
                payload_path=payload_matches[0],
                parquet_path=product_dir / "acquisition_manifest.parquet",
                lineage_path=(
                    lineage_dir / "acquisition_manifest.openlineage.json"
                ),
                bronze_root=bronze,
                admission=admission,
                source_records=source_records,
                source_records_path=product_dir / "source_records.parquet",
                source_records_lineage_path=(
                    lineage_dir / "source_records.openlineage.json"
                ),
            )
            results.append(
                _existing_item(
                    item_id=release.release_id,
                    kind="quarterly_release",
                    url=release.url,
                    receipt=bound,
                    bronze=bronze,
                )
            )
            continue
        landing = land_bronze_payload(
            payload,
            bound,
            bronze_root=bronze,
            media_hint="zip",
            reuse=decision,
            admission_decided_at=landing_timestamp,
            transformation_completed_at=landing_timestamp,
            source_records=source_records,
        )
        if not isinstance(landing, BronzeLanding):
            raise TypeError("FAERS release must produce a Bronze landing")
        results.append(
            _landing_item(
                item_id=release.release_id,
                kind="quarterly_release",
                url=release.url,
                receipt=bound,
                landing=landing,
                source_record_count=(
                    source_records.table.num_rows
                    if source_records is not None
                    else None
                ),
            )
        )

    (evidence / "redacted-acquisition-results.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in results],
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
    archive_digest, archive_size = write_private_corpus_archive(
        corpus, output_dir / ARCHIVE_FILENAME
    )
    succeeded = tuple(item for item in results if item.status == "succeeded")
    release_results = tuple(
        item for item in results if item.kind == "quarterly_release"
    )
    projected = tuple(
        item for item in release_results if item.source_records_projected
    )
    recovered_source_records = sum(
        1 for _ in (clean_room / "parquet").rglob("source_records.parquet")
    )
    byte_identical_source_records = _byte_identical_source_record_pairs(
        bronze, clean_room
    )
    complete = (
        len(release_results) == authorization.expected_release_count
        and all(item.status == "succeeded" for item in release_results)
        and all(
            item.admission_state == BronzeAdmissionState.ACCEPTED.value
            for item in release_results
        )
        and len(projected) == authorization.expected_release_count
        and recovered_source_records == authorization.expected_release_count
        and byte_identical_source_records
        == authorization.expected_release_count
    )
    manifest = FAERSCorpusManifest(
        exercised_at=timestamp,
        first_release=authorization.expected_first_release,
        last_release=authorization.expected_last_release,
        release_count=len(release_results),
        documentation_count=sum(
            item.kind == "documentation" for item in results
        ),
        succeeded_count=len(succeeded),
        failed_count=len(results) - len(succeeded),
        accepted_count=sum(
            item.admission_state == BronzeAdmissionState.ACCEPTED.value
            for item in succeeded
        ),
        quarantined_count=sum(
            item.admission_state == BronzeAdmissionState.QUARANTINED.value
            for item in succeeded
        ),
        recovered_count=len(recovery.landings),
        source_record_projection_count=len(projected),
        source_record_rows=sum(
            item.source_record_count or 0 for item in projected
        ),
        recovered_source_record_projection_count=recovered_source_records,
        source_record_parquet_pairs_byte_identical=(
            byte_identical_source_records
        ),
        quarter_coverage_complete=complete,
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
