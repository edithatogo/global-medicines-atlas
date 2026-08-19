"""Source-faithful Parquet landing beside immutable payloads.

The immutable source payload and its content-addressed receipt are
evidentiary truth; source-faithful Parquet is the portable analytical
representation; table/catalogue layers are rebuildable metadata over those
artefacts. Parquet is not raw-as-landed and is not bronze evidentiary truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import orjson
import pyarrow as pa
import pyarrow.parquet as pq

from .iceberg_ready import IcebergReadyTableSpec, table_identifier_for
from .openlineage_projection import project_openlineage_event
from .receipts import SourceReceipt
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
    )


def _analytical_table(receipt: SourceReceipt, payload: bytes) -> pa.Table:
    temporal = receipt.temporal
    native = payload.decode("utf-8", errors="replace")
    reuse = receipt.reuse.disposition.value if receipt.reuse is not None else ""
    return pa.table({
        "source_id": [receipt.source.source_id],
        "jurisdiction": [receipt.source.jurisdiction],
        "rights_state": [receipt.rights_state.value],
        "payload_sha256": [receipt.payload.sha256],
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

    acquisition_id = bound.temporal.acquisition_id
    source_id = bound.source.source_id
    payload_dir = bronze_root / PAYLOAD_DIR / source_id / acquisition_id
    parquet_dir = bronze_root / PARQUET_DIR / source_id
    receipt_dir = bronze_root / RECEIPT_DIR / source_id
    lineage_dir = bronze_root / LINEAGE_DIR / source_id
    payload_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    lineage_dir.mkdir(parents=True, exist_ok=True)

    suffix = _payload_extension(media_hint)
    payload_path = payload_dir / f"payload{suffix}"
    payload_path.write_bytes(payload)
    receipt_path = receipt_dir / f"{acquisition_id}.json"
    receipt_path.write_bytes(bound.canonical_json() + b"\n")

    parquet_path = parquet_dir / f"{acquisition_id}.parquet"
    table = _analytical_table(bound, payload)
    pq.write_table(table, parquet_path)
    spec = bronze_table_spec(bound, parquet_path)
    event = project_openlineage_event(
        bound,
        payload_uri=payload_path.as_uri(),
        parquet_uri=parquet_path.as_uri(),
        table=spec,
    )
    lineage_path = lineage_dir / f"{acquisition_id}.openlineage.json"
    lineage_path.write_bytes(
        orjson.dumps(event, option=orjson.OPT_SORT_KEYS) + b"\n"
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
