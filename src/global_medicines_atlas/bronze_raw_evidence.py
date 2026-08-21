"""B2 raw evidence and non-authoritative document/archive projections.

Raw evidence is the immutable source-native byte object, addressed by its
content digest.  The B1 acquisition manifest references this object but never
contains its contents.  Archive-member and document manifests describe the
object without promoting extracted text or interpreted fields to raw truth.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Literal

import orjson
from pydantic import Field, model_validator

from .archive_safety import inspect_tar, inspect_zip
from .models import FrozenModel
from .receipts import SHA256_PATTERN, SourceReceipt, require_temporal

RAW_EVIDENCE_SCHEMA_ID = "global-medicines-atlas.b2-raw-evidence"
RAW_EVIDENCE_MANIFEST_SCHEMA_ID = (
    "global-medicines-atlas.b2-raw-evidence-manifest"
)


class RawEvidenceState(StrEnum):
    """Whether B2 retains bytes or records a bounded absence."""

    RETAINED = "retained"
    EXTERNAL_REFERENCE_ONLY = "external_reference_only"
    BLOCKED = "blocked"


class RawEvidenceKind(StrEnum):
    """The source-native object represented by a B2 row."""

    PAYLOAD = "source_payload"
    ARCHIVE = "source_archive"
    DOCUMENT = "source_document"


class RawEvidenceRecord(FrozenModel):
    """One B2 object/reference linked to one immutable acquisition."""

    schema_id: Literal["global-medicines-atlas.b2-raw-evidence"] = (
        RAW_EVIDENCE_SCHEMA_ID
    )
    schema_version: Literal[1] = 1
    stratum: Literal["B2"] = "B2"
    source_id: str = Field(min_length=1)
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    content_id: str = Field(pattern=SHA256_PATTERN)
    kind: RawEvidenceKind = RawEvidenceKind.PAYLOAD
    state: RawEvidenceState
    raw_object_locator: str | None = None
    external_reference: str | None = None
    blocked_reason: str | None = None
    payload_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    byte_count: int | None = Field(default=None, ge=0)
    media_type: str | None = None
    payload_contents_in_metadata: Literal[False] = False
    source_native_bytes_immutable: Literal[True] = True

    @model_validator(mode="after")
    def validate_state_boundary(self) -> RawEvidenceRecord:
        if self.state is RawEvidenceState.RETAINED:
            if (
                self.raw_object_locator is None
                or self.payload_sha256 is None
                or self.byte_count is None
            ):
                raise ValueError(
                    "retained B2 evidence requires object and digest"
                )
            if (
                self.external_reference is not None
                or self.blocked_reason is not None
            ):
                raise ValueError(
                    "retained B2 evidence cannot carry blocked/reference state"
                )
        elif self.state is RawEvidenceState.EXTERNAL_REFERENCE_ONLY:
            if (
                self.external_reference is None
                or self.raw_object_locator is not None
            ):
                raise ValueError(
                    "reference-only B2 evidence requires only its external reference"
                )
            if self.payload_sha256 is not None or self.byte_count is not None:
                raise ValueError(
                    "reference-only B2 evidence cannot claim retained bytes"
                )
        else:
            if (
                self.blocked_reason is None
                or self.raw_object_locator is not None
            ):
                raise ValueError(
                    "blocked B2 evidence requires a reason and no object"
                )
            if self.payload_sha256 is not None or self.byte_count is not None:
                raise ValueError(
                    "blocked B2 evidence cannot claim retained bytes"
                )
        return self

    def canonical_json(self) -> bytes:
        return orjson.dumps(
            self.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS
        )


class RawEvidenceManifest(FrozenModel):
    """Deterministic, rebuildable inventory of B2 rows."""

    schema_id: Literal["global-medicines-atlas.b2-raw-evidence-manifest"] = (
        RAW_EVIDENCE_MANIFEST_SCHEMA_ID
    )
    schema_version: Literal[1] = 1
    authoritative: Literal[True] = True
    row_count: int = Field(ge=1)
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    rows: tuple[RawEvidenceRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest(self) -> RawEvidenceManifest:
        if self.row_count != len(self.rows):
            raise ValueError("raw evidence manifest row count mismatch")
        if self.manifest_sha256 != _rows_digest(self.rows):
            raise ValueError("raw evidence manifest digest mismatch")
        return self

    @classmethod
    def from_rows(
        cls, rows: tuple[RawEvidenceRecord, ...]
    ) -> RawEvidenceManifest:
        ordered = tuple(sorted(rows, key=lambda row: row.acquisition_id))
        digest = _rows_digest(ordered)
        return cls(
            row_count=len(ordered),
            manifest_sha256=digest,
            rows=ordered,
        )

    def canonical_json(self) -> bytes:
        return (
            orjson.dumps(
                self.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS
            )
            + b"\n"
        )


def _rows_digest(rows: tuple[RawEvidenceRecord, ...]) -> str:
    encoded = orjson.dumps(
        [row.model_dump(mode="json") for row in rows],
        option=orjson.OPT_SORT_KEYS,
    )
    return sha256(encoded).hexdigest()


def build_raw_evidence_record(
    receipt: SourceReceipt,
    *,
    raw_locator: str,
    state: RawEvidenceState,
    retain_bytes: bool = True,
    kind: RawEvidenceKind = RawEvidenceKind.PAYLOAD,
    media_type: str | None = None,
    blocked_reason: str | None = None,
) -> RawEvidenceRecord:
    """Bind B2 state to existing receipt identities without changing them."""

    temporal = require_temporal(receipt.temporal)
    if not raw_locator.strip():
        raise ValueError("raw evidence locator is required")
    if state is RawEvidenceState.RETAINED:
        if not retain_bytes:
            raise ValueError("retained B2 evidence requires retained bytes")
        return RawEvidenceRecord(
            source_id=receipt.source.source_id,
            acquisition_id=temporal.acquisition_id,
            content_id=temporal.content_id or receipt.payload.sha256,
            kind=kind,
            state=state,
            raw_object_locator=raw_locator,
            payload_sha256=receipt.payload.sha256,
            byte_count=receipt.payload.byte_count,
            media_type=media_type,
        )
    if retain_bytes:
        raise ValueError(
            "reference-only or blocked B2 evidence cannot retain bytes"
        )
    return RawEvidenceRecord(
        source_id=receipt.source.source_id,
        acquisition_id=temporal.acquisition_id,
        content_id=temporal.content_id or receipt.payload.sha256,
        kind=kind,
        state=state,
        external_reference=(
            raw_locator
            if state is RawEvidenceState.EXTERNAL_REFERENCE_ONLY
            else None
        ),
        blocked_reason=(
            blocked_reason if state is RawEvidenceState.BLOCKED else None
        ),
        media_type=media_type,
    )


def write_raw_evidence_manifest(
    path: Path,
    rows: tuple[RawEvidenceRecord, ...],
) -> RawEvidenceManifest:
    """Write a deterministic manifest and refuse historical rewrites."""

    manifest = RawEvidenceManifest.from_rows(rows)
    payload = manifest.canonical_json()
    if path.exists() and path.read_bytes() != payload:
        raise ValueError(
            "append-only raw evidence manifest cannot be rewritten"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(payload)
    return manifest


def read_raw_evidence_manifest(path: Path) -> RawEvidenceManifest:
    """Read and validate a B2 manifest without touching payload bytes."""

    return RawEvidenceManifest.model_validate_json(path.read_bytes())


@dataclass(frozen=True, slots=True)
class ArchiveMember:
    """Byte-level identity for one archive member."""

    member_name: str
    byte_count: int
    sha256: str
    is_directory: bool = False
    text_decoding: str | None = None


@dataclass(frozen=True, slots=True)
class ArchiveMemberManifest:
    """Rebuildable member inventory; the archive remains the B2 object."""

    archive_sha256: str
    archive_byte_count: int
    archive_format: str
    members: tuple[ArchiveMember, ...]


def build_archive_member_manifest(
    payload: bytes,
    *,
    media_hint: str,
) -> ArchiveMemberManifest:
    """List archive members by bytes only; never decode member contents."""

    digest = sha256(payload).hexdigest()
    normalized = media_hint.casefold().lstrip(".")
    members: list[ArchiveMember] = []
    if normalized in {"zip", "application/zip"} or payload[:2] == b"PK":
        inspect_zip(payload)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for info in archive.infolist():
                data = b"" if info.is_dir() else archive.read(info)
                members.append(
                    ArchiveMember(
                        member_name=info.filename,
                        byte_count=len(data),
                        sha256=sha256(data).hexdigest(),
                        is_directory=info.is_dir(),
                    )
                )
        archive_format = "zip"
    elif normalized in {"tar", "tgz", "tar.gz", "application/x-tar"}:
        inspect_tar(payload)
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
            for info in archive.getmembers():
                if info.isfile():
                    extracted_file = archive.extractfile(info)
                    if extracted_file is None:
                        raise ValueError(  # pragma: no cover - tarfile invariant
                            f"tar member cannot be read: {info.name}"
                        )
                    extracted = extracted_file.read()
                else:
                    extracted = b""
                members.append(
                    ArchiveMember(
                        member_name=info.name,
                        byte_count=len(extracted),
                        sha256=sha256(extracted).hexdigest(),
                        is_directory=info.isdir(),
                    )
                )
        archive_format = "tar"
    else:
        raise ValueError("payload is not a supported ZIP or tar archive")
    return ArchiveMemberManifest(
        archive_sha256=digest,
        archive_byte_count=len(payload),
        archive_format=archive_format,
        members=tuple(sorted(members, key=lambda item: item.member_name)),
    )


class DocumentManifest(FrozenModel):
    """Byte-level document identity; extraction is explicitly derived."""

    schema_id: Literal["global-medicines-atlas.b2-document-manifest"] = (
        "global-medicines-atlas.b2-document-manifest"
    )
    schema_version: Literal[1] = 1
    media_hint: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    byte_count: int = Field(ge=0)
    extraction_state: Literal["derived_not_raw"] = "derived_not_raw"
    text_extraction_performed: Literal[False] = False


def build_document_manifest(
    payload: bytes, *, media_hint: str
) -> DocumentManifest:
    """Create a document identity without decoding or interpreting it."""

    return DocumentManifest(
        media_hint=media_hint,
        payload_sha256=sha256(payload).hexdigest(),
        byte_count=len(payload),
    )
