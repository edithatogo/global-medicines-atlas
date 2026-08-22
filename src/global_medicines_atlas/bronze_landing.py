"""Source-faithful Parquet landing beside immutable payloads.

The immutable source payload and its content-addressed receipt are
evidentiary truth; source-faithful Parquet is the portable analytical
representation; table/catalogue layers are rebuildable metadata over those
artefacts. Parquet is not raw-as-landed and is not bronze evidentiary truth.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal, cast

import orjson
import pyarrow as pa
import pyarrow.parquet as pq

from .bronze_acquisition_metadata import (
    B1NativeEvidence,
    acquisition_metadata_table,
    standard_projection_links,
)
from .bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
    evaluate_bronze_payload,
    latest_admission_decision,
    latest_admission_for_receipt,
    persist_admission_decision,
    require_admitted_for_processing,
)
from .bronze_integrity import inspect_untrusted_payload
from .bronze_raw_evidence import (
    RawEvidenceManifest,
    RawEvidenceState,
    build_raw_evidence_record,
    read_raw_evidence_manifest,
    write_raw_evidence_manifest,
)
from .bronze_storage import (
    LocalFilesystemPayloadStore,
    PayloadStorageReceipt,
    PayloadStore,
    write_payload_storage_receipt,
)
from .bronze_transformation import (
    MANIFEST_PARSER_IDENTITY,
    MANIFEST_SCHEMA_VERSION,
    MANIFEST_TRANSFORMATION_IDENTITY,
    SOURCE_RECORDS_SCHEMA_VERSION,
    SOURCE_RECORDS_TRANSFORMATION_IDENTITY,
    TransformationRunReceipt,
    receipt_for_parquet,
    write_transformation_run_receipt,
)
from .iceberg_ready import (
    IcebergPartitionPolicy,
    IcebergReadyTableSpec,
    plan_iceberg_partitions,
    table_identifier_for,
)
from .openlineage_projection import project_openlineage_events
from .receipts import (
    SensitivityClassification,
    SourceReceipt,
    acquisition_event_from_receipt,
    require_temporal,
)
from .reuse_gate import ReuseGateDecision

EVIDENTIARY_TRUTH_SENTENCE = (
    "The immutable source payload and its content-addressed receipt are "
    "evidentiary truth; source-faithful Parquet is the portable "
    "analytical representation; table/catalogue layers are rebuildable "
    "metadata over those artefacts."
)
PAYLOAD_DIR = "payloads"
PARQUET_DIR = "parquet"
RECEIPT_DIR = "receipts"
LINEAGE_DIR = "lineage"
ACQUISITION_DIR = "acquisitions"
ADMISSION_DIR = "admissions"
RAW_EVIDENCE_DIR = "raw_evidence"
ACQUISITION_MANIFEST_PRODUCT = "acquisition_manifest"
SOURCE_RECORDS_PRODUCT = "source_records"
_RECORD_LINK_COLUMNS = (
    "gma_source_record_id",
    "gma_acquisition_id",
    "gma_content_id",
    "gma_acquired_at",
    "gma_schema_fingerprint",
)


@dataclass(frozen=True, slots=True)
class BronzeAcquisition:
    """Persisted acquisition evidence plus its admission outcome."""

    payload_path: Path
    receipt_path: Path
    acquisition_receipt_path: Path
    storage_receipt_path: Path
    storage_receipt: PayloadStorageReceipt
    receipt: SourceReceipt
    landed_admission: BronzeAdmissionRecord
    admission: BronzeAdmissionRecord

    @property
    def raw_evidence_manifest_path(self) -> Path:
        """The B2 inventory path; raw bytes remain in the content store."""

        bronze_root = self.receipt_path.parents[2]
        source_id = self.receipt.source.source_id
        acquisition_id = require_temporal(self.receipt.temporal).acquisition_id
        return (
            bronze_root
            / RAW_EVIDENCE_DIR
            / source_id
            / acquisition_id
            / "manifest.json"
        )

    @property
    def raw_evidence_manifest(self) -> RawEvidenceManifest:
        """Validate the persisted B2 row without reading derived products."""

        return read_raw_evidence_manifest(self.raw_evidence_manifest_path)


@dataclass(frozen=True, slots=True)
class SourceRecordBatch:
    """Adapter-produced source-native records and durable parser identity.

    This is an optional rebuildable projection over B2 bytes.  It is not an
    acquisition manifest and cannot carry Silver harmonisation.
    """

    table: pa.Table
    parser_identity: str
    record_id_column: str
    partition_policy: IcebergPartitionPolicy | None = None
    projection_kind: Literal["source_native"] = "source_native"
    preserves_native_columns: bool = True


@dataclass(frozen=True, slots=True)
class BronzeLanding(BronzeAcquisition):
    """An accepted acquisition plus distinct Bronze Parquet products."""

    acquisition_manifest_path: Path
    acquisition_manifest_lineage_path: Path
    acquisition_manifest_transformation_receipt_path: Path
    acquisition_manifest_table: IcebergReadyTableSpec
    acquisition_manifest_transformation_run: TransformationRunReceipt
    source_records_path: Path | None = None
    source_records_lineage_path: Path | None = None
    source_records_transformation_receipt_path: Path | None = None
    source_records_table: IcebergReadyTableSpec | None = None
    source_records_transformation_run: TransformationRunReceipt | None = None

    @property
    def parquet_path(self) -> Path:
        """Compatibility alias for the mandatory acquisition manifest."""

        return self.acquisition_manifest_path

    @property
    def lineage_path(self) -> Path:
        """Compatibility alias for acquisition-manifest lineage."""

        return self.acquisition_manifest_lineage_path

    @property
    def transformation_receipt_path(self) -> Path:
        """Compatibility alias for the manifest transformation receipt."""

        return self.acquisition_manifest_transformation_receipt_path

    @property
    def table(self) -> IcebergReadyTableSpec:
        """Compatibility alias for the manifest Iceberg-ready table."""

        return self.acquisition_manifest_table

    @property
    def transformation_run(self) -> TransformationRunReceipt:
        """Compatibility alias for the manifest transformation run."""

        return self.acquisition_manifest_transformation_run


def _payload_extension(media_hint: str | None) -> str:
    mapping = {
        "json": ".json",
        "xml": ".xml",
        "csv": ".csv",
        "zip": ".zip",
        "xlsx": ".xlsx",
        "doc": ".doc",
        "pdf": ".pdf",
        "tsv": ".tsv",
    }
    if media_hint is None:
        return ".bin"
    lowered = media_hint.lower().rsplit(".", 1)[-1]
    return mapping.get(lowered, ".bin")


def bronze_table_spec(
    receipt: SourceReceipt,
    parquet_path: Path,
    *,
    product: str = ACQUISITION_MANIFEST_PRODUCT,
    schema_fields: tuple[tuple[str, str], ...] | None = None,
    row_count: int = 1,
    partition_policy: IcebergPartitionPolicy | None = None,
) -> IcebergReadyTableSpec:
    """Stable Iceberg-ready identity for one explicit Bronze product."""

    source_id = receipt.source.source_id
    jurisdiction = receipt.source.jurisdiction
    temporal = require_temporal(receipt.temporal)
    manifest_fields = (
        ("source_id", "string"),
        ("jurisdiction", "string"),
        ("acquisition_id", "string"),
        ("content_id", "string"),
        ("retrieved_at", "timestamptz"),
        ("source_published_at", "timestamptz"),
        ("source_effective_at", "timestamptz"),
        ("valid_from", "timestamptz"),
        ("valid_to", "timestamptz"),
        ("rights_state", "string"),
        ("data_sensitivity", "string"),
        ("personal_data_state", "string"),
        ("publication_disposition", "string"),
        ("admission_state", "string"),
        ("source_uri", "string"),
        ("media_type", "string"),
        ("payload_location", "string"),
        ("payload_sha256", "string"),
        ("payload_byte_count", "long"),
        ("receipt_digest", "string"),
        ("parser_available", "boolean"),
        ("source_parser_identity", "string"),
        ("reuse_disposition", "string"),
    )
    fields = schema_fields or manifest_fields
    identifier = table_identifier_for(
        jurisdiction=jurisdiction,
        source_id=source_id,
    )
    identifier = f"{identifier}_{product}"
    partitions = plan_iceberg_partitions(
        fields,
        row_count=row_count,
        policy=partition_policy,
    )
    return IcebergReadyTableSpec(
        identifier=identifier,
        location=str(parquet_path.parent),
        partition_fields=partitions,
        format_version=2,
        schema_fields=fields,
        last_column_id=len(fields),
        acquisition_id=temporal.acquisition_id,
        content_id=temporal.content_id or receipt.payload.sha256,
        parquet_digest=sha256(parquet_path.read_bytes()).hexdigest(),
    )


def _media_type(receipt: SourceReceipt, payload_path: Path) -> str:
    http = receipt.retrieval.http
    if http is not None and http.content_type is not None:
        return http.content_type
    return {
        ".json": "application/json",
        ".xml": "application/xml",
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".zip": "application/zip",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pdf": "application/pdf",
    }.get(payload_path.suffix.lower(), "application/octet-stream")


def _acquisition_manifest_table(
    receipt: SourceReceipt,
    *,
    payload_path: Path,
    admission: BronzeAdmissionRecord,
    source_records: SourceRecordBatch | None,
    payload_uri: str | None = None,
    bronze_root: Path | None = None,
) -> pa.Table:
    """Build the B1 query projection from the persisted native evidence."""

    temporal = require_temporal(receipt.temporal)
    if receipt.reuse is None:
        raise ValueError("acquisition manifest requires a reuse gate decision")
    source_id = receipt.source.source_id
    event_id = temporal.acquisition_id
    root = bronze_root or payload_path.parents[3]
    admission_dir = root / ADMISSION_DIR / source_id / event_id
    admission_paths = tuple(sorted(admission_dir.glob("*.json")))
    admissions = tuple(
        BronzeAdmissionRecord.model_validate_json(path.read_bytes())
        for path in admission_paths
    )
    if not admissions:
        admissions = (admission,)
        admission_locators = (
            f"bronze://admissions/{source_id}/{event_id}/{admission.decision_id}.json",
        )
    else:
        admission_locators = tuple(
            f"bronze://admissions/{source_id}/{event_id}/{path.name}"
            for path in admission_paths
        )
    return acquisition_metadata_table(
        B1NativeEvidence(
            event=acquisition_event_from_receipt(receipt),
            receipt=receipt,
            admissions=admissions,
            raw_evidence_locator=payload_uri or payload_path.as_uri(),
            source_receipt_locator=(
                f"bronze://receipts/{source_id}/{event_id}.json"
            ),
            acquisition_event_locator=(
                f"bronze://acquisitions/{source_id}/{event_id}.json"
            ),
            admission_record_locators=admission_locators,
            media_type=_media_type(receipt, payload_path),
            source_parser_identity=(
                None
                if source_records is None
                else source_records.parser_identity
            ),
            projection_links=standard_projection_links(
                source_id=source_id,
                jurisdiction=receipt.source.jurisdiction,
                acquisition_id=event_id,
                include_source_records=source_records is not None,
            ),
        )
    )


def _iceberg_type(field: pa.Field[pa.DataType]) -> str:
    if pa.types.is_boolean(field.type):
        return "boolean"
    if pa.types.is_integer(field.type):
        return "long"
    if pa.types.is_floating(field.type):
        return "double"
    if pa.types.is_date(field.type):
        return "date"
    if pa.types.is_timestamp(field.type):
        return "timestamptz" if field.type.tz is not None else "timestamp"
    return "string"


def _iceberg_schema_fields(
    schema: pa.Schema,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            typed.name,
            _iceberg_type(typed),
        )
        for raw in schema
        for typed in (cast("pa.Field[pa.DataType]", raw),)
    )


def project_source_records_table(
    receipt: SourceReceipt,
    batch: SourceRecordBatch,
) -> tuple[pa.Table, str]:
    if not batch.parser_identity:
        raise ValueError("source-record parser identity is required")
    if batch.projection_kind != "source_native":
        raise ValueError("Bronze source records must be source-native")
    if not batch.preserves_native_columns:
        raise ValueError(
            "Bronze source records cannot harmonise native columns"
        )
    if batch.record_id_column not in batch.table.column_names:
        raise ValueError("source record identifier column is absent")
    collisions = set(batch.table.column_names).intersection(
        _RECORD_LINK_COLUMNS
    )
    if collisions:
        raise ValueError("source records use reserved GMA linkage columns")
    silver_columns = {
        "canonical_medicine",
        "normalized_product",
        "standardized_ingredient",
        "matched_medicine_id",
    }
    if silver_columns.intersection(batch.table.column_names):
        raise ValueError("Bronze source records cannot contain Silver columns")
    identifier = batch.table.column(batch.record_id_column)
    if identifier.null_count:
        raise ValueError("source record identifier column contains nulls")
    temporal = require_temporal(receipt.temporal)
    fingerprint = sha256(
        batch.table.schema.serialize().to_pybytes()
    ).hexdigest()
    count = batch.table.num_rows
    linked = batch.table
    linked = linked.append_column(
        "gma_source_record_id",
        pa.array([str(value.as_py()) for value in identifier]),
    )
    for name, value in (
        ("gma_acquisition_id", temporal.acquisition_id),
        ("gma_content_id", temporal.content_id or receipt.payload.sha256),
        ("gma_schema_fingerprint", fingerprint),
    ):
        linked = linked.append_column(name, pa.array([value] * count))
    linked = linked.append_column(
        "gma_acquired_at",
        pa.array(
            [temporal.retrieved_at] * count,
            type=pa.timestamp("us", tz="UTC"),
        ),
    )
    return linked, fingerprint


def _write_append_only(path: Path, payload: bytes) -> None:
    if path.exists() and path.read_bytes() != payload:
        raise ValueError("append-only acquisition history cannot be rewritten")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def _existing_admission_pair(
    *,
    admission_history: Path,
    receipt_path: Path,
    receipt: SourceReceipt,
) -> tuple[BronzeAdmissionRecord, BronzeAdmissionRecord] | None:
    """Resolve existing landed/current decisions for idempotent re-landing."""

    admission_paths = tuple(sorted(admission_history.glob("*.json")))
    if not admission_paths:
        return None
    admission = latest_admission_for_receipt(
        receipt_path=receipt_path,
        receipt=receipt,
    )
    history = tuple(
        BronzeAdmissionRecord.model_validate_json(path.read_bytes()).model_copy(
            update={"path": path}
        )
        for path in admission_paths
    )
    landed = tuple(
        record
        for record in history
        if record.state is BronzeAdmissionState.LANDED
    )
    if not landed:
        raise ValueError("admission history lacks its landed event")
    initial_landed = min(
        landed,
        key=lambda record: (record.decided_at, record.decision_id),
    )
    return initial_landed, admission


def _resolve_or_create_admission_pair(
    *,
    admission_history: Path,
    receipt_path: Path,
    receipt: SourceReceipt,
    payload_path: Path,
    actor: str,
    decided_at: datetime,
) -> tuple[BronzeAdmissionRecord, BronzeAdmissionRecord]:
    """Reuse an acquisition admission ledger or create its initial pair."""

    existing = _existing_admission_pair(
        admission_history=admission_history,
        receipt_path=receipt_path,
        receipt=receipt,
    )
    if existing is not None:
        return existing
    temporal = require_temporal(receipt.temporal)
    content_id = temporal.content_id or receipt.payload.sha256
    landed = persist_admission_decision(
        create_admission_decision(
            acquisition_id=temporal.acquisition_id,
            content_id=content_id,
            state=BronzeAdmissionState.LANDED,
            reason_codes=("awaiting_admission_inspection",),
            validation_results=(
                ValidationResult(
                    check_id="payload-staged",
                    passed=True,
                    message="payload and acquisition receipt are persisted",
                ),
            ),
            actor=actor,
            decided_at=decided_at,
        ),
        receipt_path=receipt_path,
        receipt=receipt,
    )
    evaluated = evaluate_bronze_payload(payload_path, receipt)
    admission = persist_admission_decision(
        create_admission_decision(
            acquisition_id=evaluated.acquisition_id,
            content_id=evaluated.content_id,
            state=evaluated.state,
            reason_codes=evaluated.reason_codes,
            validation_results=evaluated.validation_results,
            reviewer_status=evaluated.reviewer_status,
            actor=actor,
            decided_at=decided_at,
            supersedes_decision_id=landed.decision_id,
        ),
        receipt_path=receipt_path,
        receipt=receipt,
    )
    return landed, admission


@dataclass(frozen=True, slots=True)
class _ProductOutput:
    path: Path
    lineage_path: Path
    transformation_run: TransformationRunReceipt
    table: IcebergReadyTableSpec


def _write_parquet_product(
    receipt: SourceReceipt,
    table: pa.Table,
    *,
    product: Literal["acquisition_manifest", "source_records"],
    parquet_path: Path,
    lineage_path: Path,
    payload_uri: str,
    bronze_root: Path,
    admission: BronzeAdmissionRecord,
    parser_identity: str,
    transformation_identity: str,
    schema_version: str,
    partition_policy: IcebergPartitionPolicy | None,
    completed_at: datetime | None,
) -> _ProductOutput:
    pq.write_table(table, parquet_path)
    temporal = require_temporal(receipt.temporal)
    transformation_run = receipt_for_parquet(
        parquet_path,
        acquisition_id=temporal.acquisition_id,
        input_content_id=temporal.content_id or receipt.payload.sha256,
        completed_at=completed_at,
        parser_identity=parser_identity,
        transformation_identity=transformation_identity,
        output_schema_version=schema_version,
    )
    transformation_run = write_transformation_run_receipt(
        transformation_run,
        bronze_root=bronze_root,
        source_id=receipt.source.source_id,
    )
    schema_fields = _iceberg_schema_fields(table.schema)
    spec = bronze_table_spec(
        receipt,
        parquet_path,
        product=product,
        schema_fields=schema_fields,
        row_count=table.num_rows,
        partition_policy=partition_policy,
    )
    if spec.parquet_digest != transformation_run.output.sha256:
        raise ValueError("Parquet identity diverged after transformation")
    event_lineage = project_openlineage_events(
        receipt,
        payload_uri=payload_uri,
        parquet_uri=parquet_path.as_uri(),
        transformation_run=transformation_run,
        admission=admission,
        table=spec,
        parquet_product=product,
    )
    acquisition_lineage_path = (
        lineage_path.parent / "acquisition.openlineage.json"
    )
    _write_append_only(
        acquisition_lineage_path,
        orjson.dumps(
            event_lineage.acquisition,
            option=orjson.OPT_SORT_KEYS,
        )
        + b"\n",
    )
    lineage_path.write_bytes(
        orjson.dumps(
            event_lineage.transformation,
            option=orjson.OPT_SORT_KEYS,
        )
        + b"\n"
    )
    return _ProductOutput(
        path=parquet_path,
        lineage_path=lineage_path,
        transformation_run=transformation_run,
        table=spec,
    )


def _write_analytical_outputs(
    bound: SourceReceipt,
    *,
    payload_path: Path,
    payload_uri: str,
    manifest_path: Path,
    manifest_lineage_path: Path,
    bronze_root: Path,
    admission: BronzeAdmissionRecord,
    source_records: SourceRecordBatch | None,
    source_records_path: Path | None,
    source_records_lineage_path: Path | None,
    completed_at: datetime | None = None,
) -> tuple[_ProductOutput, _ProductOutput | None]:
    manifest_table = _acquisition_manifest_table(
        bound,
        payload_path=payload_path,
        payload_uri=payload_uri,
        admission=admission,
        source_records=source_records,
        bronze_root=bronze_root,
    )
    manifest = _write_parquet_product(
        bound,
        manifest_table,
        product=ACQUISITION_MANIFEST_PRODUCT,
        parquet_path=manifest_path,
        lineage_path=manifest_lineage_path,
        payload_uri=payload_uri,
        bronze_root=bronze_root,
        admission=admission,
        parser_identity=MANIFEST_PARSER_IDENTITY,
        transformation_identity=MANIFEST_TRANSFORMATION_IDENTITY,
        schema_version=MANIFEST_SCHEMA_VERSION,
        partition_policy=None,
        completed_at=completed_at,
    )
    if source_records is None:
        return manifest, None
    if source_records_path is None or source_records_lineage_path is None:
        raise ValueError("source-record output paths are required")
    projected_records = project_source_records_table(bound, source_records)[0]
    records = _write_parquet_product(
        bound,
        projected_records,
        product=SOURCE_RECORDS_PRODUCT,
        parquet_path=source_records_path,
        lineage_path=source_records_lineage_path,
        payload_uri=payload_uri,
        bronze_root=bronze_root,
        admission=admission,
        parser_identity=source_records.parser_identity,
        transformation_identity=SOURCE_RECORDS_TRANSFORMATION_IDENTITY,
        schema_version=SOURCE_RECORDS_SCHEMA_VERSION,
        partition_policy=source_records.partition_policy,
        completed_at=completed_at,
    )
    return manifest, records


def land_bronze_payload(  # ruff: ignore[too-many-locals,too-many-statements]
    payload: bytes,
    receipt: SourceReceipt,
    *,
    bronze_root: Path,
    media_hint: str | None = None,
    reuse: ReuseGateDecision | None = None,
    admission_actor: str = "global-medicines-atlas:automated-admission-v2",
    admission_decided_at: datetime | None = None,
    transformation_completed_at: datetime | None = None,
    source_records: SourceRecordBatch | None = None,
    payload_store: PayloadStore | None = None,
) -> BronzeAcquisition | BronzeLanding:
    """Stage, admit, and project a payload only after acceptance."""

    bound = (
        receipt
        if reuse is None
        else receipt.model_copy(update={"reuse": reuse})
    )
    if bound.reuse is None:
        raise ValueError("bronze landing requires a reuse gate decision")
    if not bound.payload.matches(payload):
        raise ValueError("payload digest does not match receipt")

    temporal = require_temporal(bound.temporal)
    source_id = bound.source.source_id
    content_id = temporal.content_id or bound.payload.sha256
    suffix = _payload_extension(media_hint)
    selected_store = payload_store or LocalFilesystemPayloadStore(bronze_root)
    candidate_path = (
        bronze_root
        / PAYLOAD_DIR
        / "by_content"
        / content_id
        / f"payload{suffix}"
    )
    http = getattr(bound.retrieval, "http", None)
    raw_length = None if http is None else getattr(http, "content_length", None)
    declared_length = raw_length if isinstance(raw_length, int) else None
    inspect_untrusted_payload(
        payload,
        declared_media=candidate_path.suffix,
        declared_filename=candidate_path.name,
        expected_sha256=bound.payload.sha256,
        declared_length=declared_length,
        acquisition_id=temporal.acquisition_id,
    )
    stored = selected_store.store(
        payload,
        acquisition_id=temporal.acquisition_id,
        content_id=content_id,
        suffix=suffix,
    )
    payload_path = stored.materialized_path
    payload_uri = stored.receipt.primary.uri
    for folder in (RECEIPT_DIR, ACQUISITION_DIR):
        (bronze_root / folder / source_id).mkdir(parents=True, exist_ok=True)
    event_path = (
        bronze_root
        / ACQUISITION_DIR
        / source_id
        / f"{temporal.acquisition_id}.json"
    )
    receipt_path = (
        bronze_root
        / RECEIPT_DIR
        / source_id
        / f"{temporal.acquisition_id}.json"
    )
    if bound.sensitivity is None:
        existing_sensitivity: SensitivityClassification | None = None
        if receipt_path.exists():
            existing = SourceReceipt.model_validate_json(
                receipt_path.read_bytes()
            )
            existing_sensitivity = existing.sensitivity
        else:
            existing_sensitivity = SensitivityClassification(
                reason_codes=("not_assessed",)
            )
        if existing_sensitivity is not None:
            bound = bound.model_copy(
                update={"sensitivity": existing_sensitivity}
            )
    _write_append_only(
        event_path,
        acquisition_event_from_receipt(bound).canonical_json() + b"\n",
    )
    _write_append_only(receipt_path, bound.canonical_json() + b"\n")
    storage_receipt_path = write_payload_storage_receipt(
        stored.receipt,
        bronze_root=bronze_root,
        source_id=source_id,
    )
    write_raw_evidence_manifest(
        bronze_root
        / RAW_EVIDENCE_DIR
        / source_id
        / temporal.acquisition_id
        / "manifest.json",
        (
            build_raw_evidence_record(
                bound,
                raw_locator=payload_uri,
                state=RawEvidenceState.RETAINED,
                media_type=_media_type(bound, payload_path),
            ),
        ),
    )
    staged_at = (
        admission_decided_at or transformation_completed_at or datetime.now(UTC)
    )
    admission_history = (
        bronze_root / ADMISSION_DIR / source_id / temporal.acquisition_id
    )
    landed_admission, admission = _resolve_or_create_admission_pair(
        admission_history=admission_history,
        receipt_path=receipt_path,
        receipt=bound,
        payload_path=payload_path,
        actor=admission_actor,
        decided_at=staged_at,
    )
    acquisition = BronzeAcquisition(
        payload_path=payload_path,
        receipt_path=receipt_path,
        acquisition_receipt_path=event_path,
        storage_receipt_path=storage_receipt_path,
        storage_receipt=stored.receipt,
        receipt=bound,
        landed_admission=landed_admission,
        admission=admission,
    )
    if admission.state is not BronzeAdmissionState.ACCEPTED:
        return acquisition
    require_admitted_for_processing(admission)
    if (
        transformation_completed_at is not None
        and transformation_completed_at < admission.decided_at
    ):
        raise ValueError("transformation cannot complete before admission")
    product_dir = (
        bronze_root / PARQUET_DIR / source_id / temporal.acquisition_id
    )
    lineage_dir = (
        bronze_root / LINEAGE_DIR / source_id / temporal.acquisition_id
    )
    product_dir.mkdir(parents=True, exist_ok=True)
    lineage_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = product_dir / "acquisition_manifest.parquet"
    manifest_lineage_path = (
        lineage_dir / "acquisition_manifest.openlineage.json"
    )
    source_records_path = (
        None
        if source_records is None
        else product_dir / "source_records.parquet"
    )
    source_records_lineage_path = (
        None
        if source_records is None
        else lineage_dir / "source_records.openlineage.json"
    )
    manifest, records = _write_analytical_outputs(
        bound,
        payload_path=payload_path,
        payload_uri=payload_uri,
        manifest_path=manifest_path,
        manifest_lineage_path=manifest_lineage_path,
        bronze_root=bronze_root,
        admission=admission,
        source_records=source_records,
        source_records_path=source_records_path,
        source_records_lineage_path=source_records_lineage_path,
        completed_at=transformation_completed_at,
    )
    manifest_receipt_path = manifest.transformation_run.path
    if manifest_receipt_path is None:
        raise ValueError("transformation run receipt path is required")
    records_receipt_path = (
        None if records is None else records.transformation_run.path
    )
    if records is not None and records_receipt_path is None:
        raise ValueError(
            "source-record transformation receipt path is required"
        )
    return BronzeLanding(
        payload_path=acquisition.payload_path,
        receipt_path=acquisition.receipt_path,
        acquisition_receipt_path=acquisition.acquisition_receipt_path,
        storage_receipt_path=acquisition.storage_receipt_path,
        storage_receipt=acquisition.storage_receipt,
        receipt=acquisition.receipt,
        landed_admission=acquisition.landed_admission,
        admission=acquisition.admission,
        acquisition_manifest_path=manifest.path,
        acquisition_manifest_lineage_path=manifest.lineage_path,
        acquisition_manifest_transformation_receipt_path=manifest_receipt_path,
        acquisition_manifest_table=manifest.table,
        acquisition_manifest_transformation_run=manifest.transformation_run,
        source_records_path=None if records is None else records.path,
        source_records_lineage_path=(
            None if records is None else records.lineage_path
        ),
        source_records_transformation_receipt_path=records_receipt_path,
        source_records_table=None if records is None else records.table,
        source_records_transformation_run=(
            None if records is None else records.transformation_run
        ),
    )


def write_rebuildable_layers(
    receipt: SourceReceipt,
    payload: bytes,
    *,
    payload_path: Path,
    parquet_path: Path,
    lineage_path: Path,
    bronze_root: Path,
    admission: BronzeAdmissionRecord,
    source_records: SourceRecordBatch | None = None,
    source_records_path: Path | None = None,
    source_records_lineage_path: Path | None = None,
    payload_uri: str | None = None,
) -> IcebergReadyTableSpec:
    """Rebuild admitted Bronze products; never rewrite evidentiary bytes."""

    require_admitted_for_processing(admission)
    if not receipt.payload.matches(payload):
        raise ValueError("payload digest does not match receipt")
    temporal = require_temporal(receipt.temporal)
    write_raw_evidence_manifest(
        bronze_root
        / RAW_EVIDENCE_DIR
        / receipt.source.source_id
        / temporal.acquisition_id
        / "manifest.json",
        (
            build_raw_evidence_record(
                receipt,
                raw_locator=payload_uri or payload_path.as_uri(),
                state=RawEvidenceState.RETAINED,
                media_type=_media_type(receipt, payload_path),
            ),
        ),
    )
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    lineage_path.parent.mkdir(parents=True, exist_ok=True)
    manifest, _records = _write_analytical_outputs(
        receipt,
        payload_path=payload_path,
        payload_uri=payload_uri or payload_path.as_uri(),
        manifest_path=parquet_path,
        manifest_lineage_path=lineage_path,
        bronze_root=bronze_root,
        admission=admission,
        source_records=source_records,
        source_records_path=source_records_path,
        source_records_lineage_path=source_records_lineage_path,
    )
    return manifest.table


def regenerate_parquet(
    landing: BronzeLanding,
    *,
    source_records: SourceRecordBatch | None = None,
) -> Path:
    """Rebuild the manifest and any supplied adapter-native record batch."""

    payload = landing.payload_path.read_bytes()
    admission = latest_admission_decision(landing)
    write_rebuildable_layers(
        landing.receipt,
        payload,
        payload_path=landing.payload_path,
        parquet_path=landing.parquet_path,
        lineage_path=landing.lineage_path,
        bronze_root=landing.receipt_path.parents[2],
        admission=admission,
        source_records=source_records,
        source_records_path=landing.source_records_path,
        source_records_lineage_path=landing.source_records_lineage_path,
        payload_uri=landing.storage_receipt.primary.uri,
    )
    return landing.acquisition_manifest_path
