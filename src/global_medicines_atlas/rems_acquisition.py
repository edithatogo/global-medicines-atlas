"""Internal acquisition of the complete public FDA REMS surface family."""

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import json
import re
import shutil
import time
from collections.abc import Iterable
from datetime import UTC, date, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import parse_qs, urljoin, urlsplit

from pydantic import AnyHttpUrl, Field, model_validator

if TYPE_CHECKING:
    import httpx

from .acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
    acquire_source,
)
from .bronze_admission import BronzeAdmissionState
from .bronze_landing import (
    BronzeLanding,
    SourceRecordBatch,
    land_bronze_payload,
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

SOURCE_ID = "us-fda-rems"
ARCHIVE_FILENAME = "fda-rems-live.private.tar"
MANIFEST_FILENAME = "fda-rems-live.manifest.json"
CHECKSUM_FILENAME = "SHA256SUMS"
_FDA_HOST = "www.accessdata.fda.gov"
_EXPECTED_EXPORT_COUNT = 4
_DETAIL_PATTERN = re.compile(
    r"^/scripts/cder/rems/index\.cfm\?event="
    r"(?:IndvRemsDetails|RemsDetails)\.page&REMS=[0-9]+$",
    re.IGNORECASE,
)


class _ReusableBoundTransport(BoundIPAddressTransport):
    """Keep validated FDA connection pools alive for the bounded run."""

    def close(self) -> None:
        """Let short-lived clients release responses without closing pools."""

    def close_pools(self) -> None:
        """Close every validated authority pool after the corpus run."""
        super().close()


class REMSExport(FrozenModel):
    """One exact source-native FDA REMS CSV surface."""

    surface_id: str = Field(min_length=1)
    url: AnyHttpUrl
    expected_filename: str = Field(pattern=r"^[A-Za-z0-9_]+\.csv$")
    max_bytes: int = Field(ge=1, le=64 * 1024 * 1024)


class FDARemsAuthorization(FrozenModel):
    """Exact internal-only authority for the bounded REMS corpus."""

    schema_id: Literal["global-medicines-atlas.fda-rems-live-authorization"]
    schema_version: Literal[1]
    decision_date: date
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    public_redistribution_rights_approved: bool
    index_url: AnyHttpUrl
    data_page_url: AnyHttpUrl
    exports: tuple[REMSExport, ...]
    expected_current_detail_count: int = Field(ge=1, le=512)
    expected_current_document_count: int = Field(ge=1, le=4096)
    max_total_bytes: int = Field(ge=1, le=4 * 1024 * 1024 * 1024)
    max_detail_page_bytes: int = Field(ge=1, le=32 * 1024 * 1024)
    max_document_bytes: int = Field(ge=1, le=512 * 1024 * 1024)
    request_interval_seconds: float = Field(ge=0, le=5)

    @model_validator(mode="after")
    def exact_internal_scope(self) -> FDARemsAuthorization:
        if not self.acquisition_authorized:
            raise ValueError("REMS acquisition must be explicitly authorized")
        if not self.internal_retention_authorized:
            raise ValueError("internal retention must be authorized")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("authorization must remain internal-only")
        if self.public_redistribution_rights_approved:
            raise ValueError(
                "REMS redistribution rights must remain fail closed"
            )
        if (
            self.index_url.host != _FDA_HOST
            or self.data_page_url.host != _FDA_HOST
        ):
            raise ValueError(
                "REMS inventory must stay on the official FDA host"
            )
        if (
            len(self.exports) != _EXPECTED_EXPORT_COUNT
            or len({item.surface_id for item in self.exports})
            != _EXPECTED_EXPORT_COUNT
        ):
            raise ValueError(
                "authorization must bind four distinct REMS CSV exports"
            )
        if any(item.url.host != _FDA_HOST for item in self.exports):
            raise ValueError("REMS exports must stay on the official FDA host")
        return self


class REMSDetail(FrozenModel):
    """One current REMS detail page from the authoritative index."""

    rems_id: str = Field(pattern=r"^[0-9]+$")
    url: AnyHttpUrl


class REMSDocument(FrozenModel):
    """One unique FDA-hosted document linked by current REMS pages."""

    url: AnyHttpUrl
    rems_ids: tuple[str, ...] = Field(min_length=1)
    titles: tuple[str, ...] = Field(min_length=1)


class REMSCorpusItem(FrozenModel):
    """Redacted acquisition outcome without source payload fields."""

    surface_id: str
    kind: Literal["index", "data_page", "csv", "detail", "document"]
    url: AnyHttpUrl
    status: Literal["succeeded", "failed"]
    source_version: str | None = None
    acquisition_id: str | None = None
    payload_sha256: str | None = None
    payload_byte_count: int | None = None
    admission_state: str | None = None
    parsed_source_record_count: int | None = Field(default=None, ge=0)
    source_records_projected: bool = False
    failure_code: str | None = None


class FDARemsManifest(FrozenModel):
    """Private archive receipt for one bounded FDA REMS corpus run."""

    schema_id: Literal["global-medicines-atlas.fda-rems-live-corpus"] = (
        "global-medicines-atlas.fda-rems-live-corpus"
    )
    schema_version: Literal[1] = 1
    exercised_at: datetime
    evidence_class: Literal["live_internal_documents"] = (
        "live_internal_documents"
    )
    public_release_authorized: Literal[False] = False
    external_publication_performed: Literal[False] = False
    prompt_complete: Literal[False] = False
    public_redistribution_rights_approved: Literal[False] = False
    current_detail_inventory_count: int
    current_detail_inventory_complete: bool
    current_document_inventory_count: int
    current_document_inventory_complete: bool
    target_document_count: int
    document_succeeded_count: int
    document_failed_count: int
    surface_count: int
    succeeded_count: int
    failed_count: int
    accepted_count: int
    quarantined_count: int
    recovered_count: int
    parsed_source_record_count: int
    source_record_projection_count: int
    recovered_source_record_projection_count: int
    source_record_parquet_pairs_byte_identical: int
    items: tuple[REMSCorpusItem, ...]
    archive_filename: Literal["fda-rems-live.private.tar"] = ARCHIVE_FILENAME
    archive_sha256: str
    archive_byte_count: int


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "a":
            return
        values = dict(attrs)
        href = values.get("href")
        if href:
            self.links.append((
                href.strip(),
                (values.get("title") or "").strip(),
            ))


def _links(payload: bytes) -> tuple[tuple[str, str], ...]:
    parser = _Links()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return tuple(parser.links)


def parse_current_detail_inventory(
    payload: bytes, *, base_url: AnyHttpUrl
) -> tuple[REMSDetail, ...]:
    """Extract and validate the exact current detail-page inventory."""
    details: dict[str, REMSDetail] = {}
    for href, _title in _links(payload):
        url = urljoin(str(base_url), href.split("#", maxsplit=1)[0])
        parsed = urlsplit(url)
        relative = f"{parsed.path}?{parsed.query}"
        if parsed.hostname != _FDA_HOST or not _DETAIL_PATTERN.fullmatch(
            relative
        ):
            continue
        rems_id = parse_qs(parsed.query).get("REMS", [""])[0]
        detail = REMSDetail(rems_id=rems_id, url=AnyHttpUrl(url))
        previous = details.get(rems_id)
        if previous is not None and previous.url != detail.url:
            raise ValueError(f"REMS {rems_id} has conflicting detail pages")
        details[rems_id] = detail
    if not details:
        raise ValueError("REMS index exposes no current detail pages")
    return tuple(details[key] for key in sorted(details, key=int))


def parse_document_inventory(
    pages: Iterable[tuple[REMSDetail, bytes]],
) -> tuple[REMSDocument, ...]:
    """Extract unique FDA-hosted REMS PDFs and their source relationships."""
    documents: dict[str, tuple[set[str], set[str]]] = {}
    for detail, payload in pages:
        for href, title in _links(payload):
            url = urljoin(str(detail.url), href.strip())
            parsed = urlsplit(url)
            if (
                parsed.hostname != _FDA_HOST
                or not parsed.path.casefold().startswith(
                    "/drugsatfda_docs/rems/"
                )
                or not parsed.path.casefold().endswith(".pdf")
            ):
                continue
            normalized = str(AnyHttpUrl(url))
            rems_ids, titles = documents.setdefault(normalized, (set(), set()))
            rems_ids.add(detail.rems_id)
            titles.add(title or Path(parsed.path).stem)
    return tuple(
        REMSDocument(
            url=AnyHttpUrl(url),
            rems_ids=tuple(sorted(rems_ids, key=int)),
            titles=tuple(sorted(titles)),
        )
        for url, (rems_ids, titles) in sorted(documents.items())
    )


def _catalog_source(
    catalog: tuple[MedicineDataSource, ...],
) -> MedicineDataSource:
    matches = tuple(item for item in catalog if item.source_id == SOURCE_ID)
    if len(matches) != 1:
        raise ValueError("FDA REMS catalog source must resolve once")
    return matches[0]


def _version_receipt(
    receipt: SourceReceipt, *, source_version: str, observed_at: datetime
) -> SourceReceipt:
    temporal = temporal_identity_from_source(
        retrieved_at=observed_at,
        source_id=receipt.source.source_id,
        payload_sha256=receipt.payload.sha256,
        source_version=source_version,
        original_uri=str(receipt.retrieval.uri),
    )
    return receipt.model_copy(update={"temporal": temporal})


def _policy(media_hint: str, max_bytes: int) -> AcquisitionPolicy:
    allowed = {
        "html": ("text/html", "text/plain", "application/octet-stream"),
        "csv": ("text/csv", "text/plain", "application/octet-stream"),
        "pdf": ("application/pdf", "application/octet-stream"),
    }[media_hint]
    return AcquisitionPolicy(
        timeout_seconds=120,
        max_bytes=max_bytes,
        max_redirects=5,
        allowed_content_types=allowed,
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _byte_identical_source_records(bronze: Path, clean_room: Path) -> int:
    products = tuple((bronze / "parquet").rglob("source_records.parquet"))
    return sum(
        recovered.is_file()
        and _file_sha256(original) == _file_sha256(recovered)
        for original in products
        if (
            recovered := clean_room
            / "parquet"
            / original.relative_to(bronze / "parquet")
        )
    )


def _surface_key(prefix: str, value: str) -> str:
    return f"{prefix}-{sha256(value.encode()).hexdigest()[:20]}"


def _run_fda_rems(  # ruff: ignore[too-many-locals,too-many-statements]
    *,
    repository_root: Path,
    output_dir: Path,
    authorization_path: Path,
    authorization: FDARemsAuthorization,
    catalog: tuple[MedicineDataSource, ...],
    transport: httpx.BaseTransport,
    observed_at: datetime,
    document_urls: frozenset[str] | None,
) -> FDARemsManifest:
    corpus = output_dir / "runs/corpus"
    bronze = corpus / "bronze"
    downloads = corpus / "downloads"
    evidence = corpus / "evidence"
    evidence.mkdir(parents=True)
    shutil.copy2(authorization_path, evidence / authorization_path.name)
    source = _catalog_source(catalog)
    decision = evaluate_reuse_gate(
        SOURCE_ID, repository_root=repository_root, catalog=catalog
    )
    results: list[REMSCorpusItem] = []
    total_bytes = 0

    def acquire(
        *,
        surface_id: str,
        kind: Literal["index", "data_page", "csv", "detail", "document"],
        url: AnyHttpUrl,
        media_hint: Literal["html", "csv", "pdf"],
        source_version: str,
        max_bytes: int,
        parse_records: bool = False,
    ) -> bytes | None:
        nonlocal total_bytes
        remaining = authorization.max_total_bytes - total_bytes
        if remaining <= 0:
            raise ValueError("REMS acquisition exceeded total byte budget")
        item = AuthorizedUSSource(
            source_id=SOURCE_ID,
            endpoint=url,
            media_hint=media_hint,
            rights_profile="government_public_domain_policy_review",
            max_bytes=min(max_bytes, remaining),
        )
        destination = downloads / f"{surface_id}.{media_hint}"
        receipt = acquire_source(
            SOURCE_ID,
            destination,
            repository_root=output_dir,
            catalog=(endpoint_source(item, (source,)),),
            policy=_policy(media_hint, item.max_bytes),
            transport=transport,
            evidence_class=EvidenceClass.LIVE,
            clock=lambda: observed_at,
            reuse_decision=decision,
        )
        if isinstance(receipt, FailureReceipt):
            results.append(
                REMSCorpusItem(
                    surface_id=surface_id,
                    kind=kind,
                    url=url,
                    status="failed",
                    source_version=source_version,
                    failure_code=receipt.failure_code,
                )
            )
            return None
        payload = destination.read_bytes()
        source_records: SourceRecordBatch | None = None
        if parse_records:
            source_records = recoverable_us_source_record_batch(
                SOURCE_ID, payload, media_hint
            )
            if source_records is None:
                raise ValueError("REMS CSV source-record parsing failed closed")
        bound = bind_us_acquisition_rights(
            item,
            _version_receipt(
                receipt, source_version=source_version, observed_at=observed_at
            ),
            observed_at,
        )
        landing = land_bronze_payload(
            payload,
            bound,
            bronze_root=bronze,
            media_hint=media_hint,
            reuse=decision,
            admission_decided_at=observed_at,
            transformation_completed_at=observed_at,
            source_records=source_records,
        )
        temporal = bound.temporal
        if temporal is None:  # pragma: no cover
            raise ValueError("REMS acquisition requires temporal identity")
        results.append(
            REMSCorpusItem(
                surface_id=surface_id,
                kind=kind,
                url=url,
                status="succeeded",
                source_version=source_version,
                acquisition_id=temporal.acquisition_id,
                payload_sha256=bound.payload.sha256,
                payload_byte_count=bound.payload.byte_count,
                admission_state=landing.admission.state.value,
                parsed_source_record_count=(
                    None
                    if source_records is None
                    else source_records.table.num_rows
                ),
                source_records_projected=(
                    isinstance(landing, BronzeLanding)
                    and landing.source_records_path is not None
                ),
            )
        )
        total_bytes += len(payload)
        return payload

    index_payload = acquire(
        surface_id="rems-current-index",
        kind="index",
        url=authorization.index_url,
        media_hint="html",
        source_version=f"current-index-{observed_at.date().isoformat()}",
        max_bytes=authorization.max_detail_page_bytes,
    )
    if index_payload is None:
        raise TypeError("REMS current index acquisition failed")
    details = parse_current_detail_inventory(
        index_payload, base_url=authorization.index_url
    )
    if len(details) != authorization.expected_current_detail_count:
        raise ValueError("REMS current detail inventory drifted")

    if (
        acquire(
            surface_id="rems-data-page",
            kind="data_page",
            url=authorization.data_page_url,
            media_hint="html",
            source_version=f"data-page-{observed_at.date().isoformat()}",
            max_bytes=authorization.max_detail_page_bytes,
        )
        is None
    ):
        raise TypeError("REMS data-page acquisition failed")

    for export in authorization.exports:
        if (
            acquire(
                surface_id=export.surface_id,
                kind="csv",
                url=export.url,
                media_hint="csv",
                source_version=f"{export.expected_filename}-{observed_at.date().isoformat()}",
                max_bytes=export.max_bytes,
                parse_records=True,
            )
            is None
        ):
            raise TypeError(f"REMS CSV acquisition failed: {export.surface_id}")

    detail_payloads: list[tuple[REMSDetail, bytes]] = []
    for detail in details:
        time.sleep(authorization.request_interval_seconds)
        payload = acquire(
            surface_id=f"rems-detail-{detail.rems_id}",
            kind="detail",
            url=detail.url,
            media_hint="html",
            source_version=f"detail-{detail.rems_id}-{observed_at.date().isoformat()}",
            max_bytes=authorization.max_detail_page_bytes,
        )
        if payload is None:
            raise TypeError(f"REMS detail acquisition failed: {detail.rems_id}")
        detail_payloads.append((detail, payload))

    documents = parse_document_inventory(detail_payloads)
    if len(documents) != authorization.expected_current_document_count:
        raise ValueError("REMS current document inventory drifted")
    known_urls = frozenset(str(item.url) for item in documents)
    if document_urls is not None and (
        not document_urls or not document_urls.issubset(known_urls)
    ):
        raise ValueError("REMS document retry scope is outside the inventory")
    targets = tuple(
        item
        for item in documents
        if document_urls is None or str(item.url) in document_urls
    )
    (evidence / "current-detail-inventory.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in details], indent=2)
        + "\n",
        encoding="utf-8",
    )
    (evidence / "current-document-inventory.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in documents], indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    for document in targets:
        time.sleep(authorization.request_interval_seconds)
        acquire(
            surface_id=_surface_key("rems-document", str(document.url)),
            kind="document",
            url=document.url,
            media_hint="pdf",
            source_version=f"document-{Path(urlsplit(str(document.url)).path).name}",
            max_bytes=authorization.max_document_bytes,
        )

    (evidence / "redacted-acquisition-results.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in results], indent=2)
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
    document_results = tuple(
        item for item in results if item.kind == "document"
    )
    manifest = FDARemsManifest(
        exercised_at=observed_at,
        current_detail_inventory_count=len(details),
        current_detail_inventory_complete=True,
        current_document_inventory_count=len(documents),
        current_document_inventory_complete=True,
        target_document_count=len(targets),
        document_succeeded_count=sum(
            item.status == "succeeded" for item in document_results
        ),
        document_failed_count=sum(
            item.status == "failed" for item in document_results
        ),
        surface_count=len(results),
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
        parsed_source_record_count=sum(
            item.parsed_source_record_count or 0 for item in succeeded
        ),
        source_record_projection_count=sum(
            item.source_records_projected for item in succeeded
        ),
        recovered_source_record_projection_count=sum(
            1 for _ in (clean_room / "parquet").rglob("source_records.parquet")
        ),
        source_record_parquet_pairs_byte_identical=_byte_identical_source_records(
            bronze, clean_room
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


def exercise_fda_rems(
    *,
    repository_root: Path,
    output_dir: Path,
    authorization_path: Path,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    observed_at: datetime | None = None,
    document_urls: frozenset[str] | None = None,
) -> FDARemsManifest:
    """Acquire, recover, and privately archive bounded public REMS surfaces."""
    authorization = FDARemsAuthorization.model_validate_json(
        authorization_path.read_bytes()
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("acquisition time must be timezone-aware")
    sources = tuple(load_source_catalog() if catalog is None else catalog)
    owned_transport = (
        _ReusableBoundTransport(
            policy=AcquisitionPolicy(allowed_hosts=(_FDA_HOST,))
        )
        if transport is None
        else None
    )
    run_transport = transport if transport is not None else owned_transport
    if run_transport is None:  # pragma: no cover - construction above
        raise TypeError("REMS acquisition transport is required")
    try:
        return _run_fda_rems(
            repository_root=repository_root,
            output_dir=output_dir,
            authorization_path=authorization_path,
            authorization=authorization,
            catalog=sources,
            transport=run_transport,
            observed_at=timestamp,
            document_urls=document_urls,
        )
    finally:
        if owned_transport is not None:
            owned_transport.close_pools()
