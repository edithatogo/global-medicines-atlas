"""Authorized internal acquisition of the complete current FDA NDC family."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import AnyHttpUrl, Field, model_validator

if TYPE_CHECKING:
    import httpx

from .acquisition import AcquisitionPolicy, acquire_source
from .bronze_admission import BronzeAdmissionState
from .bronze_landing import BronzeLanding, land_bronze_payload
from .bronze_recovery import reconstruct_bronze
from .models import FrozenModel
from .receipts import EvidenceClass, FailureReceipt
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

ARCHIVE_FILENAME = "ndc-directory-live.private.tar"
MANIFEST_FILENAME = "ndc-directory-live.manifest.json"
CHECKSUM_FILENAME = "SHA256SUMS"
_EXPECTED_RELEASES = {
    "finished-text": (
        "us-fda-ndc-directory",
        "https://www.accessdata.fda.gov/cder/ndctext.zip",
    ),
    "unfinished": (
        "us-fda-ndc-directory",
        "https://www.accessdata.fda.gov/cder/ndc_unfinished.zip",
    ),
    "compounders": (
        "us-fda-ndc-directory",
        "https://www.accessdata.fda.gov/cder/compounders_ndc_directory.zip",
    ),
    "excluded": (
        "us-fda-ndc-directory",
        "https://www.accessdata.fda.gov/cder/ndc_excluded.zip",
    ),
    "openfda-bulk": (
        "us-openfda-ndc",
        "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip",
    ),
}


class NDCDirectoryRelease(FrozenModel):
    """One exact current official NDC bulk surface."""

    release_id: str = Field(min_length=1)
    source_id: Literal["us-fda-ndc-directory", "us-openfda-ndc"]
    url: AnyHttpUrl
    rights_profile: Literal[
        "scoped_cc0_metadata_only",
        "government_public_domain_policy_review",
    ]
    max_bytes: int = Field(ge=1, le=512 * 1024 * 1024)


class NDCDirectoryAuthorization(FrozenModel):
    """Exact internal-only authority derived from the approved U.S. cohort."""

    schema_id: Literal[
        "global-medicines-atlas.ndc-directory-live-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date
    decision_basis: str = Field(min_length=1)
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    coverage_complete: bool
    max_total_bytes: int = Field(ge=1, le=2 * 1024 * 1024 * 1024)
    releases: tuple[NDCDirectoryRelease, ...]

    @model_validator(mode="after")
    def exact_internal_scope(self) -> NDCDirectoryAuthorization:
        if not self.internal_retention_authorized:
            raise ValueError("internal retention must be authorized")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("authorization must remain internal-only")
        if self.coverage_complete:
            raise ValueError("authorization cannot claim completed coverage")
        observed = {
            release.release_id: (release.source_id, str(release.url))
            for release in self.releases
        }
        if observed != _EXPECTED_RELEASES:
            raise ValueError(
                "authorization must match the five official NDC surfaces"
            )
        return self


class NDCDirectoryItem(FrozenModel):
    """Redacted release outcome containing no source payload fields."""

    release_id: str
    source_id: str
    url: AnyHttpUrl
    status: Literal["succeeded", "failed"]
    acquisition_id: str | None = None
    payload_sha256: str | None = None
    payload_byte_count: int | None = None
    admission_state: str | None = None
    source_records_projected: bool = False
    source_record_count: int | None = Field(default=None, ge=0)
    failure_code: str | None = None


class NDCDirectoryManifest(FrozenModel):
    """Private archive receipt for the current NDC family exercise."""

    schema_id: Literal["global-medicines-atlas.ndc-directory-live-corpus"] = (
        "global-medicines-atlas.ndc-directory-live-corpus"
    )
    schema_version: Literal[1] = 1
    exercised_at: datetime
    evidence_class: Literal["live_bounded_internal"] = "live_bounded_internal"
    external_publication_performed: Literal[False] = False
    coverage_complete: Literal[False] = False
    release_count: int
    succeeded_count: int
    failed_count: int
    accepted_count: int
    quarantined_count: int
    recovered_count: int
    source_record_projection_count: int
    source_record_rows: int
    recovered_source_record_projection_count: int
    items: tuple[NDCDirectoryItem, ...]
    archive_filename: Literal["ndc-directory-live.private.tar"] = (
        ARCHIVE_FILENAME
    )
    archive_sha256: str
    archive_byte_count: int


def _catalog_source(
    source_id: str, catalog: tuple[MedicineDataSource, ...]
) -> MedicineDataSource:
    return next(source for source in catalog if source.source_id == source_id)


def exercise_ndc_directory(  # ruff: ignore[too-many-locals]
    *,
    repository_root: Path,
    output_dir: Path,
    authorization_path: Path,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    observed_at: datetime | None = None,
) -> NDCDirectoryManifest:
    """Acquire, land, recover, and privately archive all current NDC surfaces."""
    authorization = NDCDirectoryAuthorization.model_validate_json(
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
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("acquisition time must be timezone-aware")
    decisions = {
        source_id: evaluate_reuse_gate(
            source_id, repository_root=repository_root, catalog=sources
        )
        for source_id in {
            release.source_id for release in authorization.releases
        }
    }
    results: list[NDCDirectoryItem] = []
    total_bytes = 0
    for release in authorization.releases:
        remaining = authorization.max_total_bytes - total_bytes
        if remaining <= 0:
            raise ValueError("NDC acquisition exceeded total byte budget")
        item = AuthorizedUSSource(
            source_id=release.source_id,
            endpoint=release.url,
            media_hint="zip",
            rights_profile=release.rights_profile,
            max_bytes=min(release.max_bytes, remaining),
        )
        source = endpoint_source(
            item, (_catalog_source(item.source_id, sources),)
        )
        destination = downloads / f"{release.release_id}.zip"
        receipt = acquire_source(
            item.source_id,
            destination,
            repository_root=output_dir,
            catalog=(source,),
            policy=AcquisitionPolicy(
                timeout_seconds=90,
                max_bytes=item.max_bytes,
                max_redirects=5,
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
            reuse_decision=decisions[release.source_id],
        )
        if isinstance(receipt, FailureReceipt):
            results.append(
                NDCDirectoryItem(
                    release_id=release.release_id,
                    source_id=release.source_id,
                    url=release.url,
                    status="failed",
                    failure_code=receipt.failure_code,
                )
            )
            continue
        payload = destination.read_bytes()
        total_bytes += len(payload)
        bound = bind_us_acquisition_rights(item, receipt, timestamp)
        source_records = recoverable_us_source_record_batch(
            item.source_id, payload, "zip"
        )
        landing = land_bronze_payload(
            payload,
            bound,
            bronze_root=bronze,
            media_hint="zip",
            reuse=decisions[release.source_id],
            admission_decided_at=timestamp,
            transformation_completed_at=timestamp,
            source_records=source_records,
        )
        if bound.temporal is None:
            raise ValueError("NDC acquisition requires temporal identity")
        results.append(
            NDCDirectoryItem(
                release_id=release.release_id,
                source_id=release.source_id,
                url=release.url,
                status="succeeded",
                acquisition_id=bound.temporal.acquisition_id,
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
    archive_digest, archive_size = write_private_corpus_archive(
        corpus, output_dir / ARCHIVE_FILENAME
    )
    succeeded = tuple(item for item in results if item.status == "succeeded")
    manifest = NDCDirectoryManifest(
        exercised_at=timestamp,
        release_count=len(results),
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
