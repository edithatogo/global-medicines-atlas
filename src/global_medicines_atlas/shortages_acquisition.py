"""Internal acquisition of current and historical FDA shortage surfaces."""

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
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, model_validator

if TYPE_CHECKING:
    import httpx

from .acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
    acquire_source,
)
from .bronze_admission import BronzeAdmissionState
from .bronze_landing import BronzeLanding, land_bronze_payload
from .bronze_recovery import reconstruct_bronze
from .models import FrozenModel
from .receipts import (
    EvidenceClass,
    FailureReceipt,
    SourceReceipt,
    temporal_identity_from_source,
)
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

SOURCE_ID = "us-fda-drug-shortages"
ARCHIVE_FILENAME = "fda-shortages-live.private.tar"
MANIFEST_FILENAME = "fda-shortages-live.manifest.json"
CHECKSUM_FILENAME = "SHA256SUMS"
_TIMESTAMP = re.compile(r"^[0-9]{14}$")
_CDX_HEADER = ("timestamp", "original", "statuscode", "mimetype", "digest")
_LIVE_HOSTS = (
    "api.fda.gov",
    "download.open.fda.gov",
    "web.archive.org",
    "www.fda.gov",
)


class _ReusableBoundTransport(BoundIPAddressTransport):
    """Keep validated authority pools alive across the bounded corpus run."""

    def close(self) -> None:
        """Let short-lived clients release responses without closing pools."""

    def close_pools(self) -> None:
        """Close every validated authority pool after the corpus run."""
        super().close()


class FDAShortagesAuthorization(FrozenModel):
    """Exact internal-only authority for the bounded shortages exercise."""

    schema_id: Literal[
        "global-medicines-atlas.fda-shortages-live-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    max_total_bytes: int = Field(ge=1, le=2 * 1024 * 1024 * 1024)
    max_surface_bytes: int = Field(ge=1, le=512 * 1024 * 1024)
    archive_request_interval_seconds: float = Field(ge=0, le=5)
    cdx_url: AnyHttpUrl
    expected_historical_capture_count: int = Field(ge=1, le=512)
    expected_first_capture: str
    expected_last_capture: str
    capture_replay_overrides: dict[str, AnyHttpUrl]
    download_index_url: AnyHttpUrl
    expected_bulk_url: AnyHttpUrl
    documentation_url: AnyHttpUrl

    @model_validator(mode="after")
    def exact_internal_scope(self) -> FDAShortagesAuthorization:
        if not self.acquisition_authorized:
            raise ValueError(
                "shortages acquisition must be explicitly authorized"
            )
        if not self.internal_retention_authorized:
            raise ValueError("internal retention must be authorized")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("authorization must remain internal-only")
        if self.cdx_url.host != "web.archive.org":
            raise ValueError(
                "historical inventory must use Internet Archive CDX"
            )
        if self.download_index_url.host != "api.fda.gov":
            raise ValueError("download inventory must use official openFDA")
        if self.expected_bulk_url.host != "download.open.fda.gov":
            raise ValueError("bulk export must use official openFDA download")
        if self.documentation_url.host != "www.fda.gov":
            raise ValueError("documentation must use official FDA")
        if not _TIMESTAMP.fullmatch(
            self.expected_first_capture
        ) or not _TIMESTAMP.fullmatch(self.expected_last_capture):
            raise ValueError("capture bounds must be 14-digit timestamps")
        if any(
            not _TIMESTAMP.fullmatch(timestamp) or url.host != "web.archive.org"
            for timestamp, url in self.capture_replay_overrides.items()
        ):
            raise ValueError(
                "capture replay overrides must stay in archive scope"
            )
        return self


class ShortageCapture(FrozenModel):
    """One content-preserving monthly capture of the official FDA list."""

    timestamp: str
    original: AnyHttpUrl
    digest: str = Field(min_length=1)
    replay_url: AnyHttpUrl


class ShortageItem(FrozenModel):
    """Redacted acquisition outcome without source payload fields."""

    surface_id: str
    url: AnyHttpUrl
    status: Literal["succeeded", "failed"]
    source_version: str | None = None
    acquisition_id: str | None = None
    payload_sha256: str | None = None
    payload_byte_count: int | None = None
    admission_state: str | None = None
    source_records_projected: bool = False
    source_record_count: int | None = Field(default=None, ge=0)
    failure_code: str | None = None


class FDAShortagesManifest(FrozenModel):
    """Private archive receipt for current and historical shortage surfaces."""

    schema_id: Literal["global-medicines-atlas.fda-shortages-live-corpus"] = (
        "global-medicines-atlas.fda-shortages-live-corpus"
    )
    schema_version: Literal[1] = 1
    exercised_at: datetime
    evidence_class: Literal["live_internal_historical"] = (
        "live_internal_historical"
    )
    external_publication_performed: Literal[False] = False
    prompt_complete: Literal[False] = False
    historical_detail_snapshot_coverage_complete: Literal[False] = False
    current_export_date: date
    current_record_count: int
    historical_capture_inventory_count: int
    historical_capture_inventory_complete: bool
    historical_capture_succeeded_count: int
    historical_capture_failed_count: int
    surface_count: int
    succeeded_count: int
    failed_count: int
    accepted_count: int
    quarantined_count: int
    recovered_count: int
    source_record_projection_count: int
    source_record_rows: int
    recovered_source_record_projection_count: int
    source_record_parquet_pairs_byte_identical: int
    items: tuple[ShortageItem, ...]
    archive_filename: Literal["fda-shortages-live.private.tar"] = (
        ARCHIVE_FILENAME
    )
    archive_sha256: str
    archive_byte_count: int


def parse_cdx_inventory(payload: bytes) -> tuple[ShortageCapture, ...]:
    """Validate the monthly CDX inventory without treating it as source data."""
    raw = json.loads(payload)
    if not isinstance(raw, list) or not raw or tuple(raw[0]) != _CDX_HEADER:
        raise ValueError("CDX inventory header drifted")
    captures: list[ShortageCapture] = []
    months: set[str] = set()
    for number, row in enumerate(raw[1:], start=1):
        if not isinstance(row, list) or len(row) != len(_CDX_HEADER):
            raise ValueError(f"CDX inventory row {number} drifted")
        timestamp, original, status, media, digest = (
            str(value) for value in row
        )
        parsed = urlsplit(original)
        if (
            not _TIMESTAMP.fullmatch(timestamp)
            or status != "200"
            or media != "text/html"
            or parsed.hostname != "www.accessdata.fda.gov"
            or parsed.path.casefold() != "/scripts/drugshortages/default.cfm"
        ):
            raise ValueError(f"CDX capture {number} is outside official scope")
        month = timestamp[:6]
        if month in months:
            raise ValueError("CDX inventory has duplicate monthly captures")
        months.add(month)
        captures.append(
            ShortageCapture(
                timestamp=timestamp,
                original=AnyHttpUrl(original),
                digest=digest,
                replay_url=AnyHttpUrl(
                    f"https://web.archive.org/web/{timestamp}id_/{original}"
                ),
            )
        )
    return tuple(captures)


def parse_download_inventory(
    payload: bytes,
) -> tuple[date, AnyHttpUrl, int, date]:
    raw = json.loads(payload)
    try:
        updated = raw["meta"]["last_updated"]
        shortages = raw["results"]["drug"]["shortages"]
        partitions = shortages["partitions"]
    except (KeyError, TypeError) as error:
        raise ValueError("openFDA inventory lacks drug shortages") from error
    if not isinstance(partitions, list) or len(partitions) != 1:
        raise ValueError("openFDA shortages partition count drifted")
    partition = partitions[0]
    records = int(partition["records"])
    if records != int(shortages["total_records"]):
        raise ValueError("openFDA shortages inventory record count drifted")
    return (
        date.fromisoformat(str(updated)),
        AnyHttpUrl(str(partition["file"])),
        records,
        date.fromisoformat(str(shortages["export_date"])),
    )


def _catalog_source(
    catalog: tuple[MedicineDataSource, ...],
) -> MedicineDataSource:
    return next(source for source in catalog if source.source_id == SOURCE_ID)


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


def _policy(media_hint: str, max_bytes: int) -> AcquisitionPolicy:
    allowed = {
        "json": ("application/json", "text/json", "text/plain"),
        "zip": (
            "application/zip",
            "application/x-zip-compressed",
            "application/octet-stream",
        ),
        "html": ("text/html", "text/plain", "application/octet-stream"),
    }[media_hint]
    return AcquisitionPolicy(
        timeout_seconds=90,
        max_bytes=max_bytes,
        max_redirects=5,
        allowed_content_types=allowed,
    )


def _acquire_one(
    *,
    surface_id: str,
    url: AnyHttpUrl,
    media_hint: Literal["json", "zip", "html"],
    rights_profile: Literal[
        "scoped_cc0_metadata_only", "government_public_domain_policy_review"
    ],
    source_version: str,
    repository_root: Path,
    downloads: Path,
    bronze: Path,
    source: MedicineDataSource,
    decision: ReuseGateDecision,
    observed_at: datetime,
    max_bytes: int,
    transport: httpx.BaseTransport | None,
    project_source_records: bool = False,
    expected_record_count: int | None = None,
) -> tuple[ShortageItem, bytes | None]:
    item = AuthorizedUSSource(
        source_id=SOURCE_ID,
        endpoint=url,
        media_hint=media_hint,
        rights_profile=rights_profile,
        max_bytes=max_bytes,
    )
    destination = downloads / f"{surface_id}.{media_hint}"
    receipt = acquire_source(
        SOURCE_ID,
        destination,
        repository_root=repository_root,
        catalog=(endpoint_source(item, (source,)),),
        policy=_policy(media_hint, max_bytes),
        transport=transport,
        evidence_class=EvidenceClass.LIVE,
        clock=lambda: observed_at,
        reuse_decision=decision,
    )
    if isinstance(receipt, FailureReceipt):
        return ShortageItem(
            surface_id=surface_id,
            url=url,
            status="failed",
            source_version=source_version,
            failure_code=receipt.failure_code,
        ), None
    payload = destination.read_bytes()
    source_records = (
        recoverable_us_source_record_batch(SOURCE_ID, payload, media_hint)
        if project_source_records
        else None
    )
    if project_source_records and (
        source_records is None
        or source_records.table.num_rows != expected_record_count
    ):
        raise ValueError("openFDA shortages payload record count drifted")
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
    if temporal is None:  # pragma: no cover - supplied above
        raise ValueError("shortage acquisition requires temporal identity")
    return ShortageItem(
        surface_id=surface_id,
        url=url,
        status="succeeded",
        source_version=source_version,
        acquisition_id=temporal.acquisition_id,
        payload_sha256=bound.payload.sha256,
        payload_byte_count=bound.payload.byte_count,
        admission_state=landing.admission.state.value,
        source_records_projected=(
            isinstance(landing, BronzeLanding)
            and landing.source_records_path is not None
        ),
        source_record_count=(
            source_records.table.num_rows
            if source_records is not None
            else None
        ),
    ), payload


def exercise_fda_shortages(  # ruff: ignore[too-many-locals,too-many-statements]
    *,
    repository_root: Path,
    output_dir: Path,
    authorization_path: Path,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    observed_at: datetime | None = None,
    capture_timestamps: frozenset[str] | None = None,
) -> FDAShortagesManifest:
    """Acquire, land, recover, and privately archive bounded shortage history."""
    authorization = FDAShortagesAuthorization.model_validate_json(
        authorization_path.read_bytes()
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = output_dir / "runs/corpus"
    bronze = corpus / "bronze"
    downloads = corpus / "downloads"
    evidence = corpus / "evidence"
    evidence.mkdir(parents=True)
    shutil.copy2(authorization_path, evidence / authorization_path.name)
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("acquisition time must be timezone-aware")
    sources = tuple(load_source_catalog() if catalog is None else catalog)
    source = _catalog_source(sources)
    decision = evaluate_reuse_gate(
        SOURCE_ID, repository_root=repository_root, catalog=sources
    )
    results: list[ShortageItem] = []
    total_bytes = 0
    owned_transport = (
        _ReusableBoundTransport(
            policy=AcquisitionPolicy(allowed_hosts=_LIVE_HOSTS)
        )
        if transport is None
        else None
    )
    run_transport = transport or owned_transport

    def acquire(
        *,
        surface_id: str,
        url: AnyHttpUrl,
        media_hint: Literal["json", "zip", "html"],
        rights_profile: Literal[
            "scoped_cc0_metadata_only", "government_public_domain_policy_review"
        ],
        source_version: str,
        project_source_records: bool = False,
        expected_record_count: int | None = None,
    ) -> bytes | None:
        nonlocal total_bytes
        remaining = authorization.max_total_bytes - total_bytes
        if remaining <= 0:
            raise ValueError("shortages acquisition exceeded total byte budget")
        result, payload = _acquire_one(
            surface_id=surface_id,
            url=url,
            media_hint=media_hint,
            rights_profile=rights_profile,
            source_version=source_version,
            repository_root=output_dir,
            downloads=downloads,
            bronze=bronze,
            source=source,
            decision=decision,
            observed_at=timestamp,
            max_bytes=min(authorization.max_surface_bytes, remaining),
            transport=run_transport,
            project_source_records=project_source_records,
            expected_record_count=expected_record_count,
        )
        results.append(result)
        total_bytes += 0 if payload is None else len(payload)
        return payload

    cdx_payload = acquire(
        surface_id="wayback-cdx-inventory",
        url=authorization.cdx_url,
        media_hint="json",
        rights_profile="government_public_domain_policy_review",
        source_version=f"wayback-cdx-{timestamp.date().isoformat()}",
    )
    if cdx_payload is None:
        raise TypeError("historical capture inventory acquisition failed")
    captures = parse_cdx_inventory(cdx_payload)
    if (
        len(captures) != authorization.expected_historical_capture_count
        or captures[0].timestamp != authorization.expected_first_capture
        or captures[-1].timestamp != authorization.expected_last_capture
    ):
        raise ValueError("historical capture inventory drifted")
    known_timestamps = frozenset(item.timestamp for item in captures)
    if not set(authorization.capture_replay_overrides).issubset(
        known_timestamps
    ):
        raise ValueError("capture replay override is outside the inventory")
    captures = tuple(
        item.model_copy(
            update={
                "replay_url": authorization.capture_replay_overrides.get(
                    item.timestamp, item.replay_url
                )
            }
        )
        for item in captures
    )
    if capture_timestamps is not None and (
        not capture_timestamps
        or not capture_timestamps.issubset(known_timestamps)
    ):
        raise ValueError("capture retry scope is outside the inventory")
    target_captures = tuple(
        item
        for item in captures
        if capture_timestamps is None or item.timestamp in capture_timestamps
    )
    (evidence / "historical-capture-inventory.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in captures], indent=2
        )
        + "\n",
        encoding="utf-8",
    )

    index_payload = acquire(
        surface_id="openfda-download-index",
        url=authorization.download_index_url,
        media_hint="json",
        rights_profile="scoped_cc0_metadata_only",
        source_version=f"download-index-{timestamp.date().isoformat()}",
    )
    if index_payload is None:
        raise TypeError("openFDA download inventory acquisition failed")
    _index_date, bulk_url, record_count, export_date = parse_download_inventory(
        index_payload
    )
    if str(bulk_url) != str(authorization.expected_bulk_url):
        raise ValueError("openFDA shortages bulk URL drifted")

    acquire(
        surface_id="openfda-shortages-bulk",
        url=bulk_url,
        media_hint="zip",
        rights_profile="scoped_cc0_metadata_only",
        source_version=f"drug-shortages-{export_date.isoformat()}",
        project_source_records=True,
        expected_record_count=record_count,
    )

    acquire(
        surface_id="fda-shortages-documentation",
        url=authorization.documentation_url,
        media_hint="html",
        rights_profile="government_public_domain_policy_review",
        source_version=f"documentation-{timestamp.date().isoformat()}",
    )
    for capture in target_captures:
        if transport is None:
            time.sleep(authorization.archive_request_interval_seconds)
        acquire(
            surface_id=f"historical-list-{capture.timestamp}",
            url=capture.replay_url,
            media_hint="html",
            rights_profile="government_public_domain_policy_review",
            source_version=f"list-snapshot-{capture.timestamp}",
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
    historical = tuple(
        item
        for item in results
        if item.surface_id.startswith("historical-list-")
    )
    manifest = FDAShortagesManifest(
        exercised_at=timestamp,
        current_export_date=export_date,
        current_record_count=record_count,
        historical_capture_inventory_count=len(captures),
        historical_capture_inventory_complete=True,
        historical_capture_succeeded_count=sum(
            item.status == "succeeded" for item in historical
        ),
        historical_capture_failed_count=sum(
            item.status == "failed" for item in historical
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
        source_record_projection_count=sum(
            item.source_records_projected for item in succeeded
        ),
        source_record_rows=sum(
            item.source_record_count or 0 for item in succeeded
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
    if owned_transport is not None:
        owned_transport.close_pools()
    return manifest
