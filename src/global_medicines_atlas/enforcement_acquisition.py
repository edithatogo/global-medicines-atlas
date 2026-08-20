"""Internal acquisition of current FDA enforcement and recall surfaces."""

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import AnyHttpUrl, Field, model_validator

if TYPE_CHECKING:
    import httpx

from .acquisition import AcquisitionPolicy, acquire_source
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

ARCHIVE_FILENAME = "fda-enforcement-live.private.tar"
MANIFEST_FILENAME = "fda-enforcement-live.manifest.json"
CHECKSUM_FILENAME = "SHA256SUMS"
OVERLAP_FILENAME = "recall-enforcement-overlap-contract.json"
_BULK_SURFACE_ID = "openfda-enforcement-bulk"
_BULK_SOURCE_ID = "us-openfda-enforcement"
_NOTICE_SOURCE_ID = "us-fda-recalls-notices"
_DOWNLOAD_INDEX_URL = "https://api.fda.gov/download.json"
_BULK_URL = (
    "https://download.open.fda.gov/drug/enforcement/"
    "drug-enforcement-0001-of-0001.json.zip"
)
_EXPECTED_SURFACES = {
    "openfda-download-index": (
        _BULK_SOURCE_ID,
        _DOWNLOAD_INDEX_URL,
        "json",
        "scoped_cc0_metadata_only",
    ),
    "enforcement-documentation": (
        _BULK_SOURCE_ID,
        "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/enforcement-reports",
        "html",
        "government_public_domain_policy_review",
    ),
    "recall-notices-current-xlsx": (
        _NOTICE_SOURCE_ID,
        "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/datatables-data?_format=xlsx&page=",
        "xlsx",
        "government_public_domain_policy_review",
    ),
    "recall-notices-documentation": (
        _NOTICE_SOURCE_ID,
        "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
        "html",
        "government_public_domain_policy_review",
    ),
}


class FDAEnforcementSurface(FrozenModel):
    """One exact official current surface in the bounded exercise."""

    surface_id: str = Field(min_length=1)
    source_id: Literal["us-openfda-enforcement", "us-fda-recalls-notices"]
    url: AnyHttpUrl
    media_hint: Literal["json", "zip", "xlsx", "html"]
    rights_profile: Literal[
        "scoped_cc0_metadata_only",
        "government_public_domain_policy_review",
    ]
    max_bytes: int = Field(ge=1, le=512 * 1024 * 1024)


class FDAEnforcementAuthorization(FrozenModel):
    """Exact internal-only authority for current enforcement surfaces."""

    schema_id: Literal[
        "global-medicines-atlas.fda-enforcement-live-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    historical_notice_archive_complete: bool
    max_total_bytes: int = Field(ge=1, le=2 * 1024 * 1024 * 1024)
    expected_partition_count: int = Field(ge=1, le=32)
    expected_bulk_url: AnyHttpUrl
    surfaces: tuple[FDAEnforcementSurface, ...]

    @model_validator(mode="after")
    def exact_internal_scope(self) -> FDAEnforcementAuthorization:
        if not self.acquisition_authorized:
            raise ValueError(
                "FDA enforcement acquisition must be explicitly authorized"
            )
        if not self.internal_retention_authorized:
            raise ValueError("internal retention must be authorized")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("authorization must remain internal-only")
        if self.historical_notice_archive_complete:
            raise ValueError(
                "authorization cannot pre-authorize historical completeness"
            )
        if (
            self.expected_partition_count != 1
            or str(self.expected_bulk_url) != _BULK_URL
        ):
            raise ValueError(
                "authorization must bind the one official bulk partition"
            )
        observed = {
            item.surface_id: (
                item.source_id,
                str(item.url),
                item.media_hint,
                item.rights_profile,
            )
            for item in self.surfaces
        }
        if observed != _EXPECTED_SURFACES:
            raise ValueError(
                "authorization must match four exact current surfaces"
            )
        return self


class FDAEnforcementPartition(FrozenModel):
    """One source-native partition advertised by openFDA."""

    display_name: str
    file: AnyHttpUrl
    size_mb: str
    records: int = Field(ge=1)


class FDAEnforcementInventory(FrozenModel):
    """The exact current openFDA drug-enforcement inventory."""

    index_last_updated: date
    export_date: date
    partitions: tuple[FDAEnforcementPartition, ...]
    total_records: int = Field(ge=1)


class FDAEnforcementItem(FrozenModel):
    """Redacted result without source record fields."""

    surface_id: str
    source_id: str
    url: AnyHttpUrl
    status: Literal["succeeded", "failed"]
    acquisition_id: str | None = None
    source_version: str | None = None
    payload_sha256: str | None = None
    payload_byte_count: int | None = None
    admission_state: str | None = None
    source_records_projected: bool = False
    source_record_count: int | None = Field(default=None, ge=0)
    failure_code: str | None = None


class FDAEnforcementManifest(FrozenModel):
    """Private archive receipt for the current distinct source surfaces."""

    schema_id: Literal["global-medicines-atlas.fda-enforcement-live-corpus"] = (
        "global-medicines-atlas.fda-enforcement-live-corpus"
    )
    schema_version: Literal[1] = 1
    exercised_at: datetime
    evidence_class: Literal["live_bounded_internal"] = "live_bounded_internal"
    external_publication_performed: Literal[False] = False
    prompt_complete: Literal[False] = False
    historical_notice_archive_complete: Literal[False] = False
    inventory_export_date: date
    inventory_total_records: int
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
    current_notice_snapshot_acquired: bool
    items: tuple[FDAEnforcementItem, ...]
    archive_filename: Literal["fda-enforcement-live.private.tar"] = (
        ARCHIVE_FILENAME
    )
    archive_sha256: str
    archive_byte_count: int


def _catalog_source(
    source_id: str, catalog: tuple[MedicineDataSource, ...]
) -> MedicineDataSource:
    return next(source for source in catalog if source.source_id == source_id)


def _parse_inventory(payload: bytes) -> FDAEnforcementInventory:
    raw = json.loads(payload)
    try:
        meta = raw["meta"]
        enforcement = raw["results"]["drug"]["enforcement"]
    except (KeyError, TypeError) as error:
        raise ValueError("openFDA inventory lacks drug enforcement") from error
    return FDAEnforcementInventory.model_validate({
        "index_last_updated": meta["last_updated"],
        "export_date": enforcement["export_date"],
        "partitions": enforcement["partitions"],
        "total_records": enforcement["total_records"],
    })


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
        "json": ("application/json", "text/json", "text/plain"),
        "zip": (
            "application/zip",
            "application/x-zip-compressed",
            "application/octet-stream",
        ),
        "xlsx": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/octet-stream",
        ),
        "html": ("text/html", "text/plain"),
    }[media_hint]
    return AcquisitionPolicy(
        timeout_seconds=90,
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


def _land_success(
    *,
    surface_id: str,
    item: AuthorizedUSSource,
    payload: bytes,
    receipt: SourceReceipt,
    source_version: str,
    bronze: Path,
    decision: ReuseGateDecision,
    observed_at: datetime,
    source_records: SourceRecordBatch | None,
) -> FDAEnforcementItem:
    versioned = _version_receipt(
        receipt, source_version=source_version, observed_at=observed_at
    )
    bound = bind_us_acquisition_rights(item, versioned, observed_at)
    landing = land_bronze_payload(
        payload,
        bound,
        bronze_root=bronze,
        media_hint=item.media_hint,
        reuse=decision,
        admission_decided_at=observed_at,
        transformation_completed_at=observed_at,
        source_records=source_records,
    )
    temporal = bound.temporal
    if temporal is None:  # pragma: no cover - bound by _version_receipt
        raise ValueError(
            "FDA enforcement acquisition requires temporal identity"
        )
    return FDAEnforcementItem(
        surface_id=surface_id,
        source_id=item.source_id,
        url=AnyHttpUrl(str(item.endpoint)),
        status="succeeded",
        acquisition_id=temporal.acquisition_id,
        source_version=source_version,
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
    )


def _failure(
    surface_id: str,
    item: AuthorizedUSSource,
    receipt: FailureReceipt,
) -> FDAEnforcementItem:
    return FDAEnforcementItem(
        surface_id=surface_id,
        source_id=item.source_id,
        url=AnyHttpUrl(str(item.endpoint)),
        status="failed",
        failure_code=receipt.failure_code,
    )


def _acquire(
    *,
    surface_id: str,
    item: AuthorizedUSSource,
    destination: Path,
    output_dir: Path,
    bronze: Path,
    source: MedicineDataSource,
    decision: ReuseGateDecision,
    observed_at: datetime,
    transport: httpx.BaseTransport | None,
    source_version: str,
    source_records: SourceRecordBatch | None = None,
) -> tuple[FDAEnforcementItem, bytes | None]:
    receipt = acquire_source(
        item.source_id,
        destination,
        repository_root=output_dir,
        catalog=(source,),
        policy=_policy(item.media_hint, item.max_bytes),
        transport=transport,
        evidence_class=EvidenceClass.LIVE,
        clock=lambda: observed_at,
        reuse_decision=decision,
    )
    if isinstance(receipt, FailureReceipt):
        return _failure(surface_id, item, receipt), None
    payload = destination.read_bytes()
    return (
        _land_success(
            surface_id=surface_id,
            item=item,
            payload=payload,
            receipt=receipt,
            source_version=source_version,
            bronze=bronze,
            decision=decision,
            observed_at=observed_at,
            source_records=source_records,
        ),
        payload,
    )


def exercise_fda_enforcement(  # ruff: ignore[too-many-locals,too-many-statements]
    *,
    repository_root: Path,
    output_dir: Path,
    authorization_path: Path,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    observed_at: datetime | None = None,
) -> FDAEnforcementManifest:
    """Acquire, project, recover, and privately archive current FDA surfaces."""
    authorization = FDAEnforcementAuthorization.model_validate_json(
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
    decisions = {
        source_id: evaluate_reuse_gate(
            source_id, repository_root=repository_root, catalog=sources
        )
        for source_id in (_BULK_SOURCE_ID, _NOTICE_SOURCE_ID)
    }
    surfaces = {item.surface_id: item for item in authorization.surfaces}
    index_surface = surfaces.pop("openfda-download-index")
    index_item = AuthorizedUSSource(
        source_id=index_surface.source_id,
        endpoint=index_surface.url,
        media_hint=index_surface.media_hint,
        rights_profile=index_surface.rights_profile,
        max_bytes=index_surface.max_bytes,
    )
    index_source = endpoint_source(
        index_item, (_catalog_source(index_item.source_id, sources),)
    )
    index_destination = downloads / "openfda-download-index.json"
    index_receipt = acquire_source(
        index_item.source_id,
        index_destination,
        repository_root=output_dir,
        catalog=(index_source,),
        policy=_policy(index_item.media_hint, index_item.max_bytes),
        transport=transport,
        evidence_class=EvidenceClass.LIVE,
        clock=lambda: timestamp,
        reuse_decision=decisions[index_item.source_id],
    )
    if isinstance(index_receipt, FailureReceipt):
        raise TypeError("openFDA download inventory acquisition failed")
    index_payload = index_destination.read_bytes()
    inventory = _parse_inventory(index_payload)
    if len(inventory.partitions) != authorization.expected_partition_count:
        raise ValueError("openFDA enforcement partition count drifted")
    partition = inventory.partitions[0]
    if str(partition.file) != str(authorization.expected_bulk_url):
        raise ValueError("openFDA enforcement bulk URL drifted")
    if partition.records != inventory.total_records:
        raise ValueError("openFDA enforcement inventory record count drifted")
    results = [
        _land_success(
            surface_id=index_surface.surface_id,
            item=index_item,
            payload=index_payload,
            receipt=index_receipt,
            source_version=f"download-index-{inventory.index_last_updated.isoformat()}",
            bronze=bronze,
            decision=decisions[index_item.source_id],
            observed_at=timestamp,
            source_records=None,
        )
    ]
    total_bytes = len(index_payload)

    bulk_item = AuthorizedUSSource(
        source_id=_BULK_SOURCE_ID,
        endpoint=partition.file,
        media_hint="zip",
        rights_profile="scoped_cc0_metadata_only",
        max_bytes=min(
            512 * 1024 * 1024,
            authorization.max_total_bytes - total_bytes,
        ),
    )
    bulk_source = endpoint_source(
        bulk_item, (_catalog_source(_BULK_SOURCE_ID, sources),)
    )
    bulk_destination = (
        downloads / f"drug-enforcement-{inventory.export_date}.zip"
    )
    bulk_receipt = acquire_source(
        _BULK_SOURCE_ID,
        bulk_destination,
        repository_root=output_dir,
        catalog=(bulk_source,),
        policy=_policy("zip", bulk_item.max_bytes),
        transport=transport,
        evidence_class=EvidenceClass.LIVE,
        clock=lambda: timestamp,
        reuse_decision=decisions[_BULK_SOURCE_ID],
    )
    if isinstance(bulk_receipt, FailureReceipt):
        results.append(_failure(_BULK_SURFACE_ID, bulk_item, bulk_receipt))
    else:
        bulk_payload = bulk_destination.read_bytes()
        total_bytes += len(bulk_payload)
        source_records = recoverable_us_source_record_batch(
            _BULK_SOURCE_ID, bulk_payload, "zip"
        )
        if source_records is None:
            raise ValueError("openFDA enforcement bulk lacks source records")
        if source_records.table.num_rows != inventory.total_records:
            raise ValueError("openFDA enforcement payload record count drifted")
        results.append(
            _land_success(
                surface_id=_BULK_SURFACE_ID,
                item=bulk_item,
                payload=bulk_payload,
                receipt=bulk_receipt,
                source_version=f"drug-enforcement-{inventory.export_date.isoformat()}",
                bronze=bronze,
                decision=decisions[_BULK_SOURCE_ID],
                observed_at=timestamp,
                source_records=source_records,
            )
        )

    for surface in surfaces.values():
        remaining = authorization.max_total_bytes - total_bytes
        if remaining <= 0:
            raise ValueError(
                "FDA enforcement acquisition exceeded total byte budget"
            )
        item = AuthorizedUSSource(
            source_id=surface.source_id,
            endpoint=surface.url,
            media_hint=surface.media_hint,
            rights_profile=surface.rights_profile,
            max_bytes=min(surface.max_bytes, remaining),
        )
        source = endpoint_source(
            item, (_catalog_source(item.source_id, sources),)
        )
        destination = downloads / f"{surface.surface_id}.{surface.media_hint}"
        result, payload = _acquire(
            surface_id=surface.surface_id,
            item=item,
            destination=destination,
            output_dir=output_dir,
            bronze=bronze,
            source=source,
            decision=decisions[item.source_id],
            observed_at=timestamp,
            transport=transport,
            source_version=f"{surface.surface_id}-{timestamp.date().isoformat()}",
        )
        results.append(result)
        total_bytes += 0 if payload is None else len(payload)

    overlap = {
        "schema_id": "global-medicines-atlas.recall-enforcement-overlap-contract",
        "schema_version": 1,
        "enforcement_source_id": _BULK_SOURCE_ID,
        "notice_source_id": _NOTICE_SOURCE_ID,
        "enforcement_identity_fields": ["recall_number", "event_id"],
        "notice_snapshot_identity_fields": [
            "Date",
            "Brand-Names",
            "Product-Description",
            "Company-Name",
        ],
        "automatic_record_linkage_performed": False,
        "silent_deduplication_performed": False,
        "relationship": (
            "The Enforcement Report includes all FDA-monitored recalls after "
            "classification or early listing; the notice snapshot contains only "
            "selected public announcements and exposes no stable recall_number or "
            "event_id. Preserve both provenances independently until a reviewed "
            "source-native link is available."
        ),
    }
    (evidence / OVERLAP_FILENAME).write_text(
        json.dumps(overlap, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
    manifest = FDAEnforcementManifest(
        exercised_at=timestamp,
        inventory_export_date=inventory.export_date,
        inventory_total_records=inventory.total_records,
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
        current_notice_snapshot_acquired=any(
            item.surface_id == "recall-notices-current-xlsx"
            and item.status == "succeeded"
            for item in results
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
