"""Source-faithful Parquet landing beside immutable payloads.

The immutable source payload and its content-addressed receipt are
evidentiary truth; source-faithful Parquet is the portable analytical
representation; table/catalogue layers are rebuildable metadata over those
artefacts. Parquet is not raw-as-landed and is not bronze evidentiary truth.
"""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import orjson
import pyarrow as pa
import pyarrow.parquet as pq

from .iceberg_ready import IcebergReadyTableSpec, table_identifier_for
from .openlineage_projection import project_openlineage_event
from .receipts import (
    AcquisitionEvent,
    SourceReceipt,
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


@dataclass(frozen=True, slots=True)
class BronzeLanding:
    """One landed payload plus its analytical Parquet projection."""

    payload_path: Path
    parquet_path: Path
    receipt_path: Path
    lineage_path: Path
    table: IcebergReadyTableSpec
    receipt: SourceReceipt


def _payload_extension(media_hint: str | None) -> str:
    mapping = {
        "json": ".json",
        "xml": ".xml",
        "csv": ".csv",
        "zip": ".zip",
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
) -> IcebergReadyTableSpec:
    """Stable Iceberg-ready identity over source-faithful Parquet."""

    source_id = receipt.source.source_id
    jurisdiction = receipt.source.jurisdiction
    temporal = require_temporal(receipt.temporal)
    return IcebergReadyTableSpec(
        identifier=table_identifier_for(
            jurisdiction=jurisdiction,
            source_id=source_id,
        ),
        location=str(parquet_path.parent),
        partition_fields=("jurisdiction", "source_id", "rights_state"),
        format_version=2,
        schema_fields=(
            ("source_id", "string"),
            ("jurisdiction", "string"),
            ("rights_state", "string"),
            ("payload_sha256", "string"),
            ("content_id", "string"),
            ("receipt_digest", "string"),
            ("acquisition_id", "string"),
            ("retrieved_at", "timestamptz"),
            ("source_published_at", "timestamptz"),
            ("source_effective_at", "timestamptz"),
            ("valid_from", "timestamptz"),
            ("valid_to", "timestamptz"),
            ("reuse_disposition", "string"),
            ("native_record", "string"),
        ),
        last_column_id=14,
        acquisition_id=temporal.acquisition_id,
        content_id=receipt.payload.sha256,
        parquet_digest=receipt.transformation.output_sha256,
    )


def _analytical_table(receipt: SourceReceipt, payload: bytes) -> pa.Table:
    temporal = require_temporal(receipt.temporal)
    native = payload.decode("utf-8", errors="replace")
    reuse_gate = receipt.reuse
    if reuse_gate is None:
        raise ValueError("analytical parquet requires a reuse gate decision")
    reuse = reuse_gate.disposition.value
    return pa.table({
        "source_id": [receipt.source.source_id],
        "jurisdiction": [receipt.source.jurisdiction],
        "rights_state": [receipt.rights_state.value],
        "payload_sha256": [receipt.payload.sha256],
        "content_id": [temporal.content_id or receipt.payload.sha256],
        "receipt_digest": [receipt.digest()],
        "acquisition_id": [temporal.acquisition_id],
        "retrieved_at": [temporal.retrieved_at],
        "source_published_at": [temporal.source_published_at],
        "source_effective_at": [temporal.source_effective_at],
        "valid_from": [temporal.valid_from],
        "valid_to": [temporal.valid_to],
        "reuse_disposition": [reuse],
        "native_record": [native],
    })


def _write_append_only(path: Path, payload: bytes) -> None:
    if path.exists() and path.read_bytes() != payload:
        raise ValueError("append-only acquisition history cannot be rewritten")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def _content_payload_path(
    bronze_root: Path,
    content_id: str,
    suffix: str,
) -> Path:
    content_dir = bronze_root / PAYLOAD_DIR / "by_content" / content_id
    existing = sorted(content_dir.glob("payload.*"))
    if existing:
        return existing[0]
    content_dir.mkdir(parents=True, exist_ok=True)
    return content_dir / f"payload{suffix}"


def _acquisition_event_for(receipt: SourceReceipt) -> AcquisitionEvent:
    temporal = require_temporal(receipt.temporal)
    content_id = temporal.content_id or receipt.payload.sha256
    return AcquisitionEvent(
        acquisition_id=temporal.acquisition_id,
        content_id=content_id,
        source_id=receipt.source.source_id,
        source_version=temporal.source_version,
        retrieved_at=temporal.retrieved_at,
        source_published_at=temporal.source_published_at,
        source_effective_at=temporal.source_effective_at,
        valid_from=temporal.valid_from,
        valid_to=temporal.valid_to,
        payload_sha256=receipt.payload.sha256,
    )


def _store_payload_bytes(path: Path, payload: bytes) -> None:
    if path.exists() and path.read_bytes() != payload:
        raise ValueError("content store conflict; payload bytes are immutable")
    if not path.exists():
        path.write_bytes(payload)


def _write_analytical_outputs(
    bound: SourceReceipt,
    payload: bytes,
    *,
    payload_path: Path,
    parquet_path: Path,
    lineage_path: Path,
) -> IcebergReadyTableSpec:
    table = _analytical_table(bound, payload)
    pq.write_table(table, parquet_path)
    spec = bronze_table_spec(bound, parquet_path)
    event_lineage = project_openlineage_event(
        bound,
        payload_uri=payload_path.as_uri(),
        parquet_uri=parquet_path.as_uri(),
        table=spec,
    )
    lineage_path.write_bytes(
        orjson.dumps(event_lineage, option=orjson.OPT_SORT_KEYS) + b"\n"
    )
    return spec


def land_bronze_payload(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    bronze_root: Path,
    media_hint: str | None = None,
    reuse: ReuseGateDecision | None = None,
) -> BronzeLanding:
    """Persist payload bytes, receipt, analytical Parquet, and lineage."""

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
    payload_path = _content_payload_path(
        bronze_root,
        content_id,
        _payload_extension(media_hint),
    )
    _store_payload_bytes(payload_path, payload)
    for folder in (PARQUET_DIR, RECEIPT_DIR, LINEAGE_DIR, ACQUISITION_DIR):
        (bronze_root / folder / source_id).mkdir(parents=True, exist_ok=True)
    event_path = (
        bronze_root
        / ACQUISITION_DIR
        / source_id
        / f"{temporal.acquisition_id}.json"
    )
    _write_append_only(
        event_path,
        _acquisition_event_for(bound).canonical_json() + b"\n",
    )
    receipt_path = (
        bronze_root
        / RECEIPT_DIR
        / source_id
        / f"{temporal.acquisition_id}.json"
    )
    _write_append_only(receipt_path, bound.canonical_json() + b"\n")
    parquet_path = (
        bronze_root
        / PARQUET_DIR
        / source_id
        / f"{temporal.acquisition_id}.parquet"
    )
    lineage_path = (
        bronze_root
        / LINEAGE_DIR
        / source_id
        / f"{temporal.acquisition_id}.openlineage.json"
    )
    spec = _write_analytical_outputs(
        bound,
        payload,
        payload_path=payload_path,
        parquet_path=parquet_path,
        lineage_path=lineage_path,
    )
    return BronzeLanding(
        payload_path=payload_path,
        parquet_path=parquet_path,
        receipt_path=receipt_path,
        lineage_path=lineage_path,
        table=spec,
        receipt=bound,
    )


def regenerate_parquet(landing: BronzeLanding) -> Path:
    """Rebuild analytical Parquet from the immutable payload and receipt."""

    payload = landing.payload_path.read_bytes()
    table = _analytical_table(landing.receipt, payload)
    pq.write_table(table, landing.parquet_path)
    return landing.parquet_path
