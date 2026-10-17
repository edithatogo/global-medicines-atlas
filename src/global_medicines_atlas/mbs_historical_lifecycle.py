"""Reconstruct source-faithful B1/B2 records for existing MBS raw objects.

This module consumes only an existing harvest sidecar and an independently
verified anonymous digest/size readback. It never accepts source payload
bytes, claims a new acquisition, changes rights, or records processing
acceptance.
"""

# ruff: file-ignore[too-many-locals] -- the lifecycle builder keeps every source, rights, chronology, and anonymous-readback binding visible in one auditable construction

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from operator import itemgetter
from typing import Any, cast
from urllib.parse import urlparse

from pydantic import AnyUrl

from .bronze_admission import (
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from .bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    build_raw_evidence_reference_from_acquisition,
)
from .receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    DataSensitivity,
    EvidenceClass,
    HttpRetrievalEvidence,
    PayloadEvidence,
    PersonalDataState,
    PublicationDisposition,
    RetrievalEvidence,
    RightsState,
    SensitivityClassification,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
    acquisition_event_from_receipt,
    require_temporal,
    temporal_identity_from_source,
)

MBS_DATASET = "edithatogo/australian-mbs-source-archive"
MBS_SOURCE_ID = "au-mbs"
MBS_PERIOD = "Downloads-20260701"
MBS_EFFECTIVE_DATE = "2026-07-01"
TRANSFORMATION_ID = "raw-acquisition-v1"
TRANSFORMATION_SHA256 = hashlib.sha256(TRANSFORMATION_ID.encode()).hexdigest()
AUTHORIZATION_PATH = "quality/qualifications/australian-mbs-harvest-publication-authorization.json"

_CATEGORY_PATHS = {
    "basic_service_description": "raw/mbs/bsd/",
    "monthly_schedule_xml": "raw/mbs/releases/",
    "relative_value_guide": "raw/mbs/rvg/",
}
_CATEGORY_TITLES = {
    "basic_service_description": "Medicare Benefits Schedule Basic Service Description",
    "monthly_schedule_xml": "Medicare Benefits Schedule XML releases",
    "relative_value_guide": "Medicare Benefits Schedule Relative Value Guide",
}
GIT_SHA_LENGTH = 40
SHA256_LENGTH = 64


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"harvest sidecar {field} is required")
    return value


def _validate_authority(
    authorization: dict[str, Any], *, category: str, source_url: str
) -> None:
    parsed = urlparse(source_url)
    allowed_domains = authorization.get("allowed_domains")
    permission_granted = (
        authorization.get("external_publication_authorized") is True
        and authorization.get("maintainer_asserted_redistribution_permission")
        is True
    )
    scope_matches = (
        authorization.get("dataset") == MBS_DATASET
        and MBS_SOURCE_ID in authorization.get("allowed_sources", [])
        and category in authorization.get("categories", [])
    )
    if not permission_granted or not scope_matches:
        raise ValueError("MBS authorization does not cover this sidecar")
    if (
        not isinstance(allowed_domains, list)
        or parsed.scheme != "https"
        or parsed.hostname not in allowed_domains
    ):
        raise ValueError("MBS authorization does not cover this sidecar")


def build_historical_mbs_lifecycle(
    sidecar: dict[str, Any],
    *,
    authorization: dict[str, Any],
    authorization_commit: str,
    archive_revision: str,
    observed_sha256: str,
    observed_byte_count: int,
    decided_at: datetime,
) -> dict[str, bytes]:
    """Build one historical receipt, acquisition, B2 reference and landed row.

    ``observed_sha256`` and ``observed_byte_count`` must come from an
    anonymous readback at ``archive_revision``. No payload is passed here.
    The B1 receipt is historical because its transport detail is reconstructed
    from the archived harvest sidecar; this function does not claim a new
    live acquisition.
    """
    if (
        len(authorization_commit) != GIT_SHA_LENGTH
        or any(char not in "0123456789abcdef" for char in authorization_commit)
        or len(archive_revision) != GIT_SHA_LENGTH
        or any(char not in "0123456789abcdef" for char in archive_revision)
    ):
        raise ValueError("authorization and archive revisions must be pinned")
    source_id = _string(sidecar.get("source_id"), "source_id")
    category = _string(sidecar.get("category"), "category")
    path = _string(sidecar.get("archive_path"), "archive_path")
    period = _string(sidecar.get("period_label"), "period_label")
    source_url = _string(sidecar.get("source_url"), "source_url")
    final_url = _string(sidecar.get("final_url"), "final_url")
    retrieved_at_text = _string(sidecar.get("retrieved_at"), "retrieved_at")
    digest = _string(sidecar.get("sha256"), "sha256")
    byte_count = sidecar.get("byte_count")
    schema_matches = (
        sidecar.get("schema_id")
        == "global-medicines-atlas.australian-harvest-receipt"
        and sidecar.get("schema_version") == 1
    )
    source_matches = source_id == MBS_SOURCE_ID and period == MBS_PERIOD
    category_matches = category in _CATEGORY_PATHS and path.startswith(
        f"{_CATEGORY_PATHS.get(category, '')}{MBS_PERIOD}/"
    )
    payload_identity_matches = (
        isinstance(byte_count, int)
        and not isinstance(byte_count, bool)
        and byte_count > 0
        and len(digest) == SHA256_LENGTH
        and all(char in "0123456789abcdef" for char in digest)
        and digest == observed_sha256
        and byte_count == observed_byte_count
    )
    source_parsed = urlparse(source_url)
    final_parsed = urlparse(final_url)
    urls_match = (
        final_parsed.scheme == "https"
        and final_parsed.hostname == source_parsed.hostname
    )
    if not (schema_matches and source_matches and category_matches):
        raise ValueError("sidecar source or category differs")
    if not payload_identity_matches:
        raise ValueError("sidecar and anonymous payload identity differ")
    verified_byte_count = cast("int", byte_count)
    if not urls_match:
        raise ValueError("sidecar, authorization category or readback differs")
    _validate_authority(authorization, category=category, source_url=source_url)
    retrieved_at = datetime.fromisoformat(retrieved_at_text)
    if retrieved_at.tzinfo is None or decided_at.tzinfo is None:
        raise ValueError("historical and decision timestamps must be aware")
    if decided_at.astimezone(UTC) < retrieved_at.astimezone(UTC):
        raise ValueError("landed readback cannot precede historical retrieval")

    source = SourceIdentity(
        catalog_id=MBS_SOURCE_ID,
        source_id=MBS_SOURCE_ID,
        jurisdiction="AUS",
        authority="Australian Government Department of Health",
        dataset_title=_CATEGORY_TITLES[category],
        catalog_version=MBS_EFFECTIVE_DATE,
    )
    retrieval = RetrievalEvidence(
        uri=AnyUrl(source_url),
        retrieved_at=retrieved_at,
        acquisition_method=AcquisitionMethod.DOWNLOAD,
        status=AcquisitionStatus.SUCCEEDED,
        http=HttpRetrievalEvidence(
            original_uri=AnyUrl(source_url),
            final_uri=AnyUrl(final_url),
            observed_byte_length=verified_byte_count,
        ),
    )
    temporal = temporal_identity_from_source(
        retrieved_at=retrieved_at,
        source_id=MBS_SOURCE_ID,
        payload_sha256=digest,
        source_version=MBS_EFFECTIVE_DATE,
        original_uri=source_url,
    )
    auth_url = (
        "https://github.com/edithatogo/global-medicines-atlas/blob/"
        f"{authorization_commit}/{AUTHORIZATION_PATH}"
    )
    receipt = SourceReceipt(
        receipt_id=f"historical-mbs-harvest:{digest}:{retrieved_at.isoformat()}",
        source=source,
        retrieval=retrieval,
        payload=PayloadEvidence(sha256=digest, byte_count=verified_byte_count),
        temporal=temporal,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(auth_url),
        evidence_class=EvidenceClass.HISTORICAL,
        transformation=TransformationEvidence(
            transformation_id=TRANSFORMATION_ID,
            transformation_sha256=TRANSFORMATION_SHA256,
            output_sha256=digest,
            output_byte_count=verified_byte_count,
        ),
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.UNKNOWN,
            personal_data=PersonalDataState.UNKNOWN,
            publication=PublicationDisposition.REVIEW_REQUIRED,
            reason_codes=("historical_source_bytes_not_reinspected",),
        ),
    )
    temporal = require_temporal(receipt.temporal)
    event = acquisition_event_from_receipt(receipt)
    raw_reference = (
        f"https://huggingface.co/datasets/{MBS_DATASET}/resolve/"
        f"{archive_revision}/{path}"
    )
    b2 = build_raw_evidence_reference_from_acquisition(
        event,
        external_reference=raw_reference,
        kind=RawEvidenceKind.PAYLOAD,
    )
    landed = create_admission_decision(
        acquisition_id=temporal.acquisition_id,
        content_id=digest,
        state=BronzeAdmissionState.LANDED,
        reason_codes=("m112_existing_raw_object_anonymously_verified",),
        validation_results=(
            ValidationResult(
                check_id="anonymous-raw-sha256",
                passed=True,
                message=f"revision:{archive_revision};sha256:{digest}",
            ),
            ValidationResult(
                check_id="anonymous-raw-byte-count",
                passed=True,
                message=f"revision:{archive_revision};bytes:{verified_byte_count}",
            ),
        ),
        actor="global-medicines-atlas:m112-july-metadata-reconciliation",
        decided_at=decided_at,
    )
    base = f"bronze/receipts/au-mbs/{temporal.acquisition_id}"
    admission_base = f"bronze/admissions/au-mbs/{temporal.acquisition_id}"
    return dict(
        sorted(
            {
                f"{base}.json": receipt.canonical_json() + b"\n",
                f"bronze/acquisitions/au-mbs/{temporal.acquisition_id}.json": (
                    event.canonical_json() + b"\n"
                ),
                f"bronze/raw-evidence/au-mbs/{temporal.acquisition_id}/manifest.json": (
                    RawEvidenceManifest.from_rows((b2,)).canonical_json()
                ),
                f"{admission_base}/{landed.decision_id}.json": (
                    landed.model_dump_json(exclude_none=False).encode() + b"\n"
                ),
            }.items()
        )
    )


def append_manifest_rows(
    manifest: dict[str, Any],
    additions: dict[str, bytes],
    *,
    generated_at: datetime,
) -> bytes:
    """Append new lifecycle rows while preserving every existing manifest row."""
    files = manifest.get("files")
    if (
        manifest.get("schema_id") != "global-medicines-atlas.harvest-manifest"
        or manifest.get("schema_version") != 1
        or not isinstance(files, list)
    ):
        raise ValueError("unsupported MBS root manifest")
    rows: dict[str, dict[str, Any]] = {}
    file_rows = cast("list[Any]", files)
    if manifest.get("file_count") != len(file_rows):
        raise ValueError("unsupported MBS root manifest")
    for value in file_rows:
        if not isinstance(value, dict):
            raise TypeError("invalid MBS root manifest row")
        row = cast("dict[str, Any]", value)
        if not isinstance(row.get("path"), str):
            raise TypeError("invalid MBS root manifest row")
        if row["path"] in rows:
            raise ValueError("duplicate MBS root manifest path")
        rows[row["path"]] = row
    if set(rows).intersection(additions):
        raise ValueError("append would rewrite existing manifest rows")
    for path, payload in additions.items():
        kind = (
            "b1_receipt"
            if path.startswith("bronze/receipts/")
            else "b1_acquisition_event"
            if path.startswith("bronze/acquisitions/")
            else "b1_landed_admission"
            if path.startswith("bronze/admissions/")
            else "b2_raw_reference"
        )
        rows[path] = {
            "bytes": len(payload),
            "kind": kind,
            "path": path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "source_id": MBS_SOURCE_ID,
        }
    updated = {
        **manifest,
        "file_count": len(rows),
        "files": sorted(rows.values(), key=itemgetter("path")),
        "generated_at": (
            generated_at
            .astimezone(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        ),
    }
    return (json.dumps(updated, indent=2, sort_keys=True) + "\n").encode()
