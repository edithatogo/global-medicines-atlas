"""Fail-closed Bronze acquisition for the EU Union Register JSON dataset."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import pyarrow as pa
from pydantic import AnyHttpUrl, Field, model_validator

if TYPE_CHECKING:
    import httpx

from .acquisition import AcquisitionPolicy, acquire_source
from .bronze_admission import BronzeAdmissionState
from .bronze_landing import SourceRecordBatch, land_bronze_payload
from .bronze_recovery import reconstruct_bronze
from .models import FrozenModel
from .receipts import EvidenceClass, FailureReceipt, RightsState, SourceReceipt
from .reuse_gate import evaluate_reuse_gate
from .rights_policy import (
    AccessRestriction,
    AcquisitionRightsPolicy,
    Permission,
    ReviewStatus,
)
from .source_catalog import AccessMode, MedicineDataSource, load_source_catalog
from .us_live_bronze import (
    copy_evidentiary_truth,
    write_private_corpus_archive,
)

SOURCE_ID = "eu-union-register"
DATASET_URL = (
    "https://ec.europa.eu/health/documents/community-register/ods/"
    "ods_products.json"
)
LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"
ARCHIVE_FILENAME = "union-register-live.private.tar"
MANIFEST_FILENAME = "union-register-live.manifest.json"
CHECKSUM_FILENAME = "SHA256SUMS"


class UnionRegisterAuthorization(FrozenModel):
    """Maintainer-controlled authority for one exact internal-only source."""

    schema_id: Literal[
        "global-medicines-atlas.union-register-live-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date
    decision_basis: str = Field(min_length=1)
    dataset_url: AnyHttpUrl
    licence_url: AnyHttpUrl
    source_release_date: date
    acquisition_authorized: bool
    internal_retention_authorized: bool
    maintainer_licence_approved: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    coverage_complete: bool
    max_bytes: int = Field(ge=1, le=128 * 1024 * 1024)

    @model_validator(mode="after")
    def exact_fail_closed_scope(self) -> UnionRegisterAuthorization:
        if str(self.dataset_url) != DATASET_URL:
            raise ValueError("authorization must bind the official JSON URL")
        if str(self.licence_url) != LICENCE_URL:
            raise ValueError("authorization must bind CC BY 4.0")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("authorization must remain internal-only")
        if self.coverage_complete:
            raise ValueError("authorization cannot claim completed coverage")
        approvals = (
            self.acquisition_authorized,
            self.internal_retention_authorized,
            self.maintainer_licence_approved,
        )
        if len(set(approvals)) != 1:
            raise ValueError(
                "acquisition, retention, and licence approval must agree"
            )
        return self


class UnionRegisterManifest(FrozenModel):
    """Private archive receipt for one Union Register exercise."""

    schema_id: Literal["global-medicines-atlas.union-register-live-corpus"] = (
        "global-medicines-atlas.union-register-live-corpus"
    )
    schema_version: Literal[1] = 1
    exercised_at: datetime
    evidence_class: Literal["live_bounded_internal"] = "live_bounded_internal"
    external_publication_performed: Literal[False] = False
    coverage_complete: Literal[False] = False
    acquisition_id: str
    payload_sha256: str
    payload_byte_count: int
    admission_state: str
    source_record_rows: int
    recovered_count: int
    recovered_source_record_projection_count: int
    archive_filename: Literal["union-register-live.private.tar"] = (
        ARCHIVE_FILENAME
    )
    archive_sha256: str
    archive_byte_count: int


def union_register_source_record_batch(
    source_id: str, payload: bytes, media_hint: str
) -> SourceRecordBatch | None:
    """Project the source-native JSON rows without semantic normalization."""
    if source_id != SOURCE_ID or media_hint != "json":
        return None
    document = cast("object", json.loads(payload))
    if not isinstance(document, dict):
        raise TypeError("Union Register JSON must contain only a data array")
    typed_document = cast("dict[str, object]", document)
    if set(typed_document) != {"data"}:
        raise ValueError("Union Register JSON must contain only a data array")
    records = typed_document["data"]
    if not isinstance(records, list) or not records:
        raise ValueError("Union Register data must be a non-empty array")
    untyped_records = cast("list[object]", records)
    if not all(isinstance(record, dict) for record in untyped_records):
        raise ValueError("Union Register records must be JSON objects")
    typed_records = cast("list[dict[str, object]]", records)
    identifiers = tuple(record.get("URI") for record in typed_records)
    if any(not isinstance(value, str) or not value for value in identifiers):
        raise ValueError("every Union Register record requires a URI")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Union Register record URIs must be unique")
    return SourceRecordBatch(
        table=pa.Table.from_pylist(typed_records),
        parser_identity="eu-union-register-json-v1",
        record_id_column="URI",
    )


def _endpoint_source(
    catalog: tuple[MedicineDataSource, ...],
) -> MedicineDataSource:
    source = next(item for item in catalog if item.source_id == SOURCE_ID)
    return MedicineDataSource.model_validate(
        source.model_dump(mode="python")
        | {
            "access_mode": AccessMode.DOWNLOAD,
            "api_url": None,
            "download_url": DATASET_URL,
            "formats": ("json",),
        }
    )


def _bind_rights(
    receipt: SourceReceipt,
    authorization: UnionRegisterAuthorization,
    observed_at: datetime,
) -> SourceReceipt:
    if receipt.temporal is None:
        raise ValueError(
            "Union Register acquisition requires temporal identity"
        )
    policy = AcquisitionRightsPolicy(
        acquisition_id=receipt.temporal.acquisition_id,
        source_id=SOURCE_ID,
        licence_evidence_uri=authorization.licence_url,
        licence_expression="CC BY 4.0; internal retention and transformation only.",
        retain_evidence=Permission.PERMITTED,
        publish_bytes=Permission.PROHIBITED,
        redistribute=Permission.PROHIBITED,
        transform=Permission.PERMITTED,
        attribution_requirement=(
            "Credit the European Commission, identify the Union Register "
            "dataset, link CC BY 4.0, and record retrieval and release dates."
        ),
        access_restriction=AccessRestriction.NONE,
        review_status=ReviewStatus.REVIEWED,
        observed_at=observed_at,
        reviewed_at=observed_at,
        maintainer_licence_approved=True,
        maintainer_publication_approved=False,
    )
    return SourceReceipt.model_validate(
        receipt.model_dump(mode="python")
        | {
            "rights_state": RightsState.PERMITTED,
            "rights_reference": str(authorization.licence_url),
            "rights_policy": policy,
        }
    )


def exercise_union_register(  # ruff: ignore[too-many-locals]
    *,
    repository_root: Path,
    output_dir: Path,
    authorization_path: Path,
    catalog: tuple[MedicineDataSource, ...] | None = None,
    transport: httpx.BaseTransport | None = None,
    observed_at: datetime | None = None,
) -> UnionRegisterManifest:
    """Acquire, project, recover, and privately archive the official JSON."""
    authorization = UnionRegisterAuthorization.model_validate_json(
        authorization_path.read_bytes()
    )
    if not authorization.acquisition_authorized:
        raise PermissionError("maintainer licence approval is required")
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
    source = _endpoint_source(sources)
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("acquisition time must be timezone-aware")
    decision = evaluate_reuse_gate(
        SOURCE_ID, repository_root=repository_root, catalog=sources
    )
    destination = downloads / "ods_products.json"
    receipt = acquire_source(
        SOURCE_ID,
        destination,
        repository_root=output_dir,
        catalog=(source,),
        policy=AcquisitionPolicy(
            timeout_seconds=120,
            max_bytes=authorization.max_bytes,
            max_redirects=5,
            allowed_content_types=("application/json", "text/json"),
        ),
        transport=transport,
        evidence_class=EvidenceClass.LIVE,
        clock=lambda: timestamp,
        reuse_decision=decision,
    )
    if isinstance(receipt, FailureReceipt):
        raise TypeError(
            f"Union Register acquisition failed: {receipt.failure_code}"
        )
    payload = destination.read_bytes()
    batch = union_register_source_record_batch(SOURCE_ID, payload, "json")
    if batch is None:
        raise ValueError("Union Register source-record projection is required")
    bound = _bind_rights(receipt, authorization, timestamp)
    temporal = bound.temporal
    if temporal is None:
        raise ValueError(
            "Union Register acquisition requires temporal identity"
        )
    landing = land_bronze_payload(
        payload,
        bound,
        bronze_root=bronze,
        media_hint="json",
        reuse=decision,
        admission_decided_at=timestamp,
        transformation_completed_at=timestamp,
        source_records=batch,
    )
    clean_room = corpus / "clean-room"
    copy_evidentiary_truth(bronze, clean_room)
    recovery = reconstruct_bronze(
        clean_room,
        source_record_factory=union_register_source_record_batch,
    )
    archive_digest, archive_size = write_private_corpus_archive(
        corpus, output_dir / ARCHIVE_FILENAME
    )
    manifest = UnionRegisterManifest(
        exercised_at=timestamp,
        acquisition_id=temporal.acquisition_id,
        payload_sha256=bound.payload.sha256,
        payload_byte_count=bound.payload.byte_count,
        admission_state=landing.admission.state.value,
        source_record_rows=batch.table.num_rows,
        recovered_count=len(recovery.landings),
        recovered_source_record_projection_count=sum(
            1 for _ in (clean_room / "parquet").rglob("source_records.parquet")
        ),
        archive_sha256=archive_digest,
        archive_byte_count=archive_size,
    )
    if manifest.admission_state != BronzeAdmissionState.ACCEPTED.value:
        raise ValueError("Union Register payload was not admitted")
    (output_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / CHECKSUM_FILENAME).write_text(
        f"{archive_digest}  {ARCHIVE_FILENAME}\n", encoding="utf-8"
    )
    return manifest
