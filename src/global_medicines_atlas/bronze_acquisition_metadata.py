"""Deterministic B1 query projection over native acquisition evidence.

``SourceReceipt``, ``AcquisitionEvent`` and ``BronzeAdmissionRecord`` remain
the append-only authority. This module creates a rebuildable manifest for
queries and interoperability without copying source payload contents.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import orjson
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import AwareDatetime, Field, model_validator

from .bronze_admission import BronzeAdmissionRecord
from .bronze_storage import PayloadStorageReceipt
from .iceberg_ready import table_identifier_for
from .models import FrozenModel
from .receipts import (
    SHA256_PATTERN,
    AcquisitionEvent,
    SourceReceipt,
    acquisition_event_from_receipt,
    require_temporal,
)

B1_SCHEMA_ID = "global-medicines-atlas.b1-acquisition-metadata-manifest"
REDACTED = "REDACTED"
_SENSITIVE_QUERY_MARKERS = (
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
    "key",
    "password",
    "secret",
    "signature",
    "sig",
    "token",
)


class B1ProjectionLink(FrozenModel):
    """One non-authoritative, rebuildable B1/B2 projection location."""

    kind: Literal[
        "acquisition_manifest_parquet",
        "openlineage",
        "source_records_parquet",
        "source_records_openlineage",
        "table_catalogue",
    ]
    locator: str = Field(min_length=1)


class B1AcquisitionMetadataRow(FrozenModel):
    """Query-friendly metadata for exactly one native acquisition event."""

    source_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    content_id: str = Field(pattern=SHA256_PATTERN)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    payload_byte_count: int = Field(ge=0)
    raw_evidence_locator: str = Field(min_length=1)
    payload_location: str = Field(min_length=1)
    receipt_digest: str = Field(pattern=SHA256_PATTERN)
    acquisition_event_digest: str = Field(pattern=SHA256_PATTERN)
    evidence_class: str = Field(min_length=1)
    source_version: str | None = None
    source_published_at: AwareDatetime | None = None
    source_effective_at: AwareDatetime | None = None
    retrieved_at: AwareDatetime
    valid_from: AwareDatetime | None = None
    valid_to: AwareDatetime | None = None
    original_retrieval_location: str = Field(min_length=1)
    final_retrieval_location: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    redirect_chain: tuple[str, ...] = ()
    http_method: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    etag: str | None = None
    last_modified: str | None = None
    media_type: str | None = None
    content_encoding: str | None = None
    declared_byte_length: int | None = Field(default=None, ge=0)
    observed_byte_length: int | None = Field(default=None, ge=0)
    acquisition_method: str = Field(min_length=1)
    acquisition_agent_version: str | None = None
    reuse_disposition: str
    reuse_discovery_snapshot_id: str | None = None
    rights_state: str = Field(min_length=1)
    data_sensitivity: str = Field(min_length=1)
    personal_data_state: str = Field(min_length=1)
    publication_disposition: str = Field(min_length=1)
    rights_reference: str | None = None
    retention_state: str = Field(min_length=1)
    transformation_state: str = Field(min_length=1)
    redistribution_state: str = Field(min_length=1)
    rights_review_state: str = Field(min_length=1)
    rights_compatibility: Literal["policy_bound", "coarse_legacy"]
    admission_state: str = Field(min_length=1)
    admission_reason_codes: tuple[str, ...] = ()
    admission_reviewer_state: str = Field(min_length=1)
    admission_decision_id: str = Field(pattern=SHA256_PATTERN)
    source_receipt_locator: str = Field(min_length=1)
    acquisition_event_locator: str = Field(min_length=1)
    admission_record_locators: tuple[str, ...] = Field(min_length=1)
    parser_available: bool
    source_parser_identity: str | None = None
    projection_links: tuple[B1ProjectionLink, ...] = ()

    @model_validator(mode="after")
    def identities_and_lengths_remain_linked(self) -> B1AcquisitionMetadataRow:
        if self.content_id != self.payload_sha256:
            raise ValueError("content_id must equal payload digest")
        if self.acquisition_id == self.content_id:
            raise ValueError(
                "acquisition_id must remain distinct from content_id"
            )
        return self


class B1AcquisitionMetadataManifest(FrozenModel):
    """Versioned deterministic B1 query manifest over native evidence."""

    schema_id: Literal[
        "global-medicines-atlas.b1-acquisition-metadata-manifest"
    ] = B1_SCHEMA_ID
    schema_version: Literal[1] = 1
    authoritative_native_records: Literal[True] = True
    query_manifest_is_authoritative: Literal[False] = False
    openlineage_is_authoritative: Literal[False] = False
    table_catalogues_are_authoritative: Literal[False] = False
    event_count: int = Field(ge=1)
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    manifest_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    rows: tuple[B1AcquisitionMetadataRow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest_identity(self) -> B1AcquisitionMetadataManifest:
        ids = [row.acquisition_id for row in self.rows]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("B1 rows require sorted unique acquisition IDs")
        if self.event_count != len(self.rows):
            raise ValueError("B1 event_count must match manifest rows")
        digest = _manifest_digest(self.rows)
        if self.manifest_sha256 != digest:
            raise ValueError("B1 manifest digest does not match its rows")
        if self.manifest_id != f"sha256:{digest}":
            raise ValueError("B1 manifest ID must bind the manifest digest")
        return self


@dataclass(frozen=True, slots=True)
class B1NativeEvidence:
    """Existing authoritative records and their immutable locators."""

    event: AcquisitionEvent
    receipt: SourceReceipt
    admissions: tuple[BronzeAdmissionRecord, ...]
    raw_evidence_locator: str
    source_receipt_locator: str
    acquisition_event_locator: str
    admission_record_locators: tuple[str, ...]
    media_type: str | None = None
    source_parser_identity: str | None = None
    projection_links: tuple[B1ProjectionLink, ...] = ()


def redact_retrieval_location(value: str) -> str:
    """Remove userinfo and sensitive query values from a projected URI."""

    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    redacted_query: list[tuple[str, str]] = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        normalized = key.casefold().replace("-", "_")
        sensitive = any(
            marker == normalized or marker in normalized
            for marker in _SENSITIVE_QUERY_MARKERS
        )
        redacted_query.append((key, REDACTED if sensitive else item))
    return urlunsplit((
        parsed.scheme,
        netloc,
        parsed.path,
        urlencode(redacted_query),
        "",
    ))


def _latest_admission(
    records: tuple[BronzeAdmissionRecord, ...],
) -> BronzeAdmissionRecord:
    if not records:
        raise ValueError("authoritative admission history is required")
    superseded = {
        record.supersedes_decision_id
        for record in records
        if record.supersedes_decision_id is not None
    }
    heads = tuple(
        record for record in records if record.decision_id not in superseded
    )
    if len(heads) != 1:
        raise ValueError("admission history requires one unsuperseded decision")
    return heads[0]


def _validate_native_linkage(evidence: B1NativeEvidence) -> None:
    event = evidence.event
    receipt = evidence.receipt
    temporal = require_temporal(receipt.temporal)
    expected = acquisition_event_from_receipt(receipt)
    identity_fields = (
        "acquisition_id",
        "content_id",
        "source_id",
        "source_version",
        "retrieved_at",
        "source_published_at",
        "source_effective_at",
        "valid_from",
        "valid_to",
        "payload_sha256",
        "source",
        "retrieval",
        "reuse",
        "rights_state",
        "rights_reference",
        "rights_policy",
        "evidence_class",
    )
    if any(
        getattr(event, field) != getattr(expected, field)
        for field in identity_fields
    ):
        raise ValueError(
            "authoritative acquisition event diverges from receipt"
        )
    if (
        "sensitivity" in event.model_fields_set
        and event.sensitivity != expected.sensitivity
    ):
        raise ValueError(
            "authoritative acquisition event diverges from receipt"
        )
    if event.acquisition_id != temporal.acquisition_id:
        raise ValueError("acquisition event identity diverges from receipt")
    if len(evidence.admissions) != len(evidence.admission_record_locators):
        raise ValueError("admission records and locators must remain aligned")
    if any(
        record.acquisition_id != event.acquisition_id
        or record.content_id != event.content_id
        for record in evidence.admissions
    ):
        raise ValueError("admission history diverges from acquisition event")


def project_b1_acquisition_metadata(  # ruff: ignore[too-many-locals]
    evidence: B1NativeEvidence,
) -> B1AcquisitionMetadataRow:
    """Project existing B1 native records without reading payload bytes."""

    _validate_native_linkage(evidence)
    event = evidence.event
    receipt = evidence.receipt
    admission = _latest_admission(evidence.admissions)
    retrieval = event.retrieval or receipt.retrieval
    http = retrieval.http
    original = (
        str(http.original_uri) if http is not None else str(retrieval.uri)
    )
    final = (
        str(http.final_uri)
        if http is not None and http.final_uri is not None
        else str(retrieval.uri)
    )
    policy = event.rights_policy or receipt.rights_policy
    if policy is None:
        retention = "unknown"
        transformation = "unknown"
        redistribution = "unknown"
        review = "unreviewed"
        compatibility: Literal["policy_bound", "coarse_legacy"] = (
            "coarse_legacy"
        )
    else:
        retention = policy.retain_evidence.value
        transformation = policy.transform.value
        redistribution = policy.redistribute.value
        review = policy.review_status.value
        compatibility = "policy_bound"
    reuse = event.reuse or receipt.reuse
    evidence_class = event.evidence_class or receipt.evidence_class
    rights_state = event.rights_state or receipt.rights_state
    rights_reference = event.rights_reference or receipt.rights_reference
    sensitivity = event.sensitivity
    links = tuple(
        sorted(
            (
                link.model_copy(
                    update={"locator": redact_retrieval_location(link.locator)}
                )
                for link in evidence.projection_links
            ),
            key=lambda link: (link.kind, link.locator),
        )
    )
    return B1AcquisitionMetadataRow(
        source_id=event.source_id,
        jurisdiction=receipt.source.jurisdiction,
        acquisition_id=event.acquisition_id,
        content_id=event.content_id,
        payload_sha256=event.payload_sha256,
        payload_byte_count=receipt.payload.byte_count,
        raw_evidence_locator=redact_retrieval_location(
            evidence.raw_evidence_locator
        ),
        payload_location=redact_retrieval_location(
            evidence.raw_evidence_locator
        ),
        receipt_digest=receipt.digest(),
        acquisition_event_digest=event.digest(),
        evidence_class=evidence_class.value,
        source_version=event.source_version,
        source_published_at=event.source_published_at,
        source_effective_at=event.source_effective_at,
        retrieved_at=event.retrieved_at,
        valid_from=event.valid_from,
        valid_to=event.valid_to,
        original_retrieval_location=redact_retrieval_location(original),
        final_retrieval_location=redact_retrieval_location(final),
        source_uri=redact_retrieval_location(original),
        redirect_chain=tuple(
            redact_retrieval_location(str(item))
            for item in (() if http is None else http.redirect_history)
        ),
        http_method=None if http is None else http.http_method,
        http_status=None if http is None else http.http_status,
        etag=None if http is None else http.etag,
        last_modified=None if http is None else http.last_modified,
        media_type=(
            evidence.media_type
            if http is None or http.content_type is None
            else http.content_type
        ),
        content_encoding=None if http is None else http.content_encoding,
        declared_byte_length=None if http is None else http.content_length,
        observed_byte_length=(
            receipt.payload.byte_count
            if http is None or http.observed_byte_length is None
            else http.observed_byte_length
        ),
        acquisition_method=retrieval.acquisition_method.value,
        acquisition_agent_version=(
            None if http is None else http.acquisition_agent_version
        ),
        reuse_disposition=(
            "unknown" if reuse is None else reuse.disposition.value
        ),
        reuse_discovery_snapshot_id=(
            None if reuse is None else reuse.catalogue_revision
        ),
        rights_state=rights_state.value,
        data_sensitivity=sensitivity.data_sensitivity.value,
        personal_data_state=sensitivity.personal_data.value,
        publication_disposition=sensitivity.publication.value,
        rights_reference=(
            None
            if rights_reference is None
            else redact_retrieval_location(str(rights_reference))
        ),
        retention_state=retention,
        transformation_state=transformation,
        redistribution_state=redistribution,
        rights_review_state=review,
        rights_compatibility=compatibility,
        admission_state=admission.state.value,
        admission_reason_codes=admission.reason_codes,
        admission_reviewer_state=admission.reviewer_status,
        admission_decision_id=admission.decision_id,
        source_receipt_locator=evidence.source_receipt_locator,
        acquisition_event_locator=evidence.acquisition_event_locator,
        admission_record_locators=evidence.admission_record_locators,
        parser_available=any(
            link.kind == "source_records_parquet" for link in links
        ),
        source_parser_identity=evidence.source_parser_identity,
        projection_links=links,
    )


def _manifest_digest(rows: tuple[B1AcquisitionMetadataRow, ...]) -> str:
    payload = {
        "schema_id": B1_SCHEMA_ID,
        "schema_version": 1,
        "rows": [row.model_dump(mode="json") for row in rows],
    }
    return sha256(
        orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()


def build_b1_acquisition_metadata_manifest(
    evidence: Iterable[B1NativeEvidence],
) -> B1AcquisitionMetadataManifest:
    """Build one deterministic row per authoritative acquisition event."""

    rows = tuple(
        sorted(
            (project_b1_acquisition_metadata(item) for item in evidence),
            key=lambda row: row.acquisition_id,
        )
    )
    if not rows:
        raise ValueError("B1 manifest requires at least one acquisition event")
    digest = _manifest_digest(rows)
    return B1AcquisitionMetadataManifest(
        event_count=len(rows),
        manifest_sha256=digest,
        manifest_id=f"sha256:{digest}",
        rows=rows,
    )


def _manifest_table(manifest: B1AcquisitionMetadataManifest) -> pa.Table:
    rows = [row.model_dump(mode="python") for row in manifest.rows]
    table = pa.Table.from_pylist(rows)
    return table.replace_schema_metadata({
        b"schema_id": manifest.schema_id.encode(),
        b"schema_version": str(manifest.schema_version).encode(),
        b"manifest_sha256": manifest.manifest_sha256.encode(),
        b"authoritative_native_records": b"true",
        b"query_manifest_is_authoritative": b"false",
        b"openlineage_is_authoritative": b"false",
        b"table_catalogues_are_authoritative": b"false",
    })


def acquisition_metadata_parquet_bytes(
    manifest: B1AcquisitionMetadataManifest,
) -> bytes:
    """Render deterministic portable Parquet for the B1 query manifest."""

    sink = pa.BufferOutputStream()
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        _manifest_table(manifest),
        sink,
        compression="zstd",
        compression_level=9,
        data_page_version="2.0",
        use_dictionary=False,
        write_page_index=False,
        write_statistics=True,
        version="2.6",
    )
    return sink.getvalue().to_pybytes()


def acquisition_metadata_json_bytes(
    manifest: B1AcquisitionMetadataManifest,
) -> bytes:
    """Render the deterministic portable JSON form of the B1 manifest."""

    return orjson.dumps(
        manifest.model_dump(mode="json"),
        option=(
            orjson.OPT_INDENT_2
            | orjson.OPT_SORT_KEYS
            | orjson.OPT_APPEND_NEWLINE
        ),
    )


def acquisition_metadata_table(
    evidence: B1NativeEvidence,
) -> pa.Table:
    """Return the existing one-event landing product under the B1 schema."""

    return _manifest_table(build_b1_acquisition_metadata_manifest((evidence,)))


def standard_projection_links(
    *,
    source_id: str,
    jurisdiction: str,
    acquisition_id: str,
    include_source_records: bool,
) -> tuple[B1ProjectionLink, ...]:
    """Return stable logical locators for the rebuildable Bronze products."""

    product_root = f"parquet/{source_id}/{acquisition_id}"
    lineage_root = f"lineage/{source_id}/{acquisition_id}"
    table = table_identifier_for(
        jurisdiction=jurisdiction,
        source_id=source_id,
    )
    links = [
        B1ProjectionLink(
            kind="acquisition_manifest_parquet",
            locator=f"bronze://{product_root}/acquisition_manifest.parquet",
        ),
        B1ProjectionLink(
            kind="openlineage",
            locator=f"bronze://{lineage_root}/acquisition_manifest.openlineage.json",
        ),
        B1ProjectionLink(
            kind="table_catalogue",
            locator=f"iceberg://{table}_acquisition_manifest",
        ),
    ]
    if include_source_records:
        links.extend((
            B1ProjectionLink(
                kind="source_records_parquet",
                locator=f"bronze://{product_root}/source_records.parquet",
            ),
            B1ProjectionLink(
                kind="source_records_openlineage",
                locator=f"bronze://{lineage_root}/source_records.openlineage.json",
            ),
        ))
    return tuple(links)


def reconstruct_b1_acquisition_metadata(
    bronze_root: Path,
) -> B1AcquisitionMetadataManifest:
    """Rebuild B1 query metadata from persisted native evidence only."""

    items: list[B1NativeEvidence] = []
    event_root = bronze_root / "acquisitions"
    for event_path in sorted(event_root.glob("*/*.json")):
        try:
            event = AcquisitionEvent.model_validate_json(
                event_path.read_bytes()
            )
        except ValueError as error:
            raise ValueError(
                "authoritative acquisition event is invalid or rewritten"
            ) from error
        receipt_path = (
            bronze_root
            / "receipts"
            / event.source_id
            / f"{event.acquisition_id}.json"
        )
        storage_path = (
            bronze_root
            / "storage"
            / event.source_id
            / f"{event.acquisition_id}.json"
        )
        try:
            receipt = SourceReceipt.model_validate_json(
                receipt_path.read_bytes()
            )
            storage = PayloadStorageReceipt.model_validate_json(
                storage_path.read_bytes()
            )
        except (OSError, ValueError) as error:
            raise ValueError(
                "authoritative receipt or storage evidence is unavailable"
            ) from error
        if (
            storage.acquisition_id != event.acquisition_id
            or storage.content_id != event.content_id
            or storage.payload_sha256 != event.payload_sha256
        ):
            raise ValueError("storage receipt diverges from acquisition event")
        admission_dir = (
            bronze_root / "admissions" / event.source_id / event.acquisition_id
        )
        admission_paths = tuple(sorted(admission_dir.glob("*.json")))
        try:
            admissions = tuple(
                BronzeAdmissionRecord.model_validate_json(path.read_bytes())
                for path in admission_paths
            )
        except ValueError as error:
            raise ValueError(
                "authoritative admission history is invalid"
            ) from error
        source_records = (
            bronze_root
            / "parquet"
            / event.source_id
            / event.acquisition_id
            / "source_records.parquet"
        ).is_file()
        media_type = {
            ".json": "application/json",
            ".xml": "application/xml",
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
            ".zip": "application/zip",
            ".xlsx": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            ".pdf": "application/pdf",
        }.get(
            Path(storage.primary.key).suffix.casefold(),
            "application/octet-stream",
        )
        items.append(
            B1NativeEvidence(
                event=event,
                receipt=receipt,
                admissions=admissions,
                raw_evidence_locator=storage.primary.uri,
                source_receipt_locator=(
                    f"bronze://receipts/{event.source_id}/{event.acquisition_id}.json"
                ),
                acquisition_event_locator=(
                    f"bronze://acquisitions/{event.source_id}/{event.acquisition_id}.json"
                ),
                admission_record_locators=tuple(
                    f"bronze://admissions/{event.source_id}/{event.acquisition_id}/{path.name}"
                    for path in admission_paths
                ),
                media_type=media_type,
                projection_links=standard_projection_links(
                    source_id=event.source_id,
                    jurisdiction=receipt.source.jurisdiction,
                    acquisition_id=event.acquisition_id,
                    include_source_records=source_records,
                ),
            )
        )
    return build_b1_acquisition_metadata_manifest(items)
