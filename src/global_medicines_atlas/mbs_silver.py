"""Bounded typed MBS projections retaining native fields and exact receipts.

These are rebuildable Silver candidates, not public/promotion receipts.
Raw XML remains evidentiary truth. The existing parser bounds each input to
9 MB; output batches add a bounded row buffer, not unbounded source streaming.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pyarrow as pa

from .adapters.au_mbs import MbsSourceRecord, parse_mbs_source_xml
from .australian_source_contracts import (
    MbsFieldContract,
    TargetTable,
    ValueType,
    mbs_field_contracts,
)
from .bronze_acquisition_metadata import redact_retrieval_location
from .mbs_typed_values import convert_mbs_value
from .receipts import SourceReceipt

_TABLES = frozenset(field.target_table for field in mbs_field_contracts())
_DECIMAL_TYPE = pa.decimal128(38, 9)
MAX_BATCH_ROWS = 4096


def _arrow_type(value_type: ValueType) -> pa.DataType:
    if value_type == "source_date":
        return pa.date32()
    if value_type in {"aud_decimal", "decimal", "percentage"}:
        return _DECIMAL_TYPE
    return pa.string()


def mbs_silver_schema(table: TargetTable) -> pa.Schema:
    """Return v1 nested, typed/native columns for one service-benefit table."""
    if table not in _TABLES:
        raise ValueError("unknown MBS Silver table")
    fields: list[pa.Field[pa.DataType]] = [
        pa.field("source_record_id", pa.string(), nullable=False),
        pa.field("source_ordinal", pa.int64(), nullable=False),
        pa.field("source_sha256", pa.string(), nullable=False),
        pa.field("receipt_sha256", pa.string(), nullable=False),
    ]
    for contract in mbs_field_contracts():
        if contract.target_table != table:
            continue
        fields.append(
            pa.field(
                contract.native_name,
                pa.struct([
                    pa.field("native_value", pa.string()),
                    pa.field("native_state", pa.string(), nullable=False),
                    pa.field("conversion_status", pa.string(), nullable=False),
                    pa.field("typed_value", _arrow_type(contract.value_type)),
                ]),
                nullable=False,
                metadata={
                    "source_path": f"/MBS_XML/Data/{contract.native_name}",
                    "native_type": contract.value_type,
                    "currency": "AUD"
                    if contract.value_type == "aud_decimal"
                    else "not_applicable",
                },
            )
        )
    return pa.schema(
        fields,
        metadata={
            "schema_name": f"global-medicines-atlas.mbs-silver.{table}",
            "schema_version": "1.0",
            "source_id": "au-mbs",
            "subject_kind": "service",
            "dimension": "service_benefit",
            "absence_interpretation": "unknown",
            "mapping_status": "source_native",
            "qualification": "candidate",
            "conversion_version": "mbs-scalar-v1",
            "decimal_type": "decimal128(38,9)",
        },
    )


def _field_value(
    contract: MbsFieldContract,
    native: dict[str, str | None],
    date_format: str | None,
) -> dict[str, Any]:
    value = native.get(contract.native_name)
    state = (
        "missing_field"
        if contract.native_name not in native
        else "null"
        if value is None
        else "value"
    )
    converted = convert_mbs_value(
        contract.native_name,
        value,
        state,
        date_format=date_format,
    )
    typed = converted.typed_value
    status: str = converted.status
    if isinstance(typed, Decimal):
        try:
            # Arrow rejects lossy rescaling and precision overflow. The
            # original decimal string remains available in either case.
            pa.scalar(typed, type=_DECIMAL_TYPE)
        except pa.ArrowInvalid:
            typed, status = None, "unrepresentable"
    return {
        "native_value": value,
        "native_state": state,
        "conversion_status": status,
        "typed_value": typed,
    }


def _row(
    record: MbsSourceRecord,
    contracts: tuple[MbsFieldContract, ...],
    receipt_sha256: str,
    date_format: str | None,
) -> dict[str, Any]:
    native = {field.name: field.value for field in record.fields}
    return {
        "source_record_id": record.source_record_id,
        "source_ordinal": record.source_ordinal,
        "source_sha256": record.provenance.source_sha256,
        "receipt_sha256": receipt_sha256,
        **{
            contract.native_name: _field_value(contract, native, date_format)
            for contract in contracts
        },
    }


def iter_mbs_silver_batches(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    table: TargetTable,
    date_format: str | None = None,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Parse receipt-matched XML and yield bounded, source-ordered batches.

    Every batch binds B1 by digest and exposes only selected, redacted
    provenance; its rows bind native identity to receipt/B2 digests.
    Publication and public v4 location
    verification remain separate. A date profile is explicit transformation
    input, not a claim that a real source era uses that format.
    """
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("MBS Silver batch size must be between 1 and 4096")
    if date_format not in {None, "iso"}:
        raise ValueError("unsupported date format profile")
    schema = mbs_silver_schema(table)
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    batch = parse_mbs_source_xml(payload, receipt)
    metadata = dict(schema.metadata or {})
    metadata.update({
        b"source_receipt_sha256": receipt.digest().encode(),
        b"source_receipt_locator": f"sha256:{receipt.digest()}".encode(),
        b"source_uri": redact_retrieval_location(
            str(receipt.retrieval.uri)
        ).encode(),
        b"retrieved_at": receipt.retrieval.retrieved_at.isoformat().encode(),
        b"rights_state": receipt.rights_state.value.encode(),
        b"evidence_class": receipt.evidence_class.value.encode(),
        b"schema_era": batch.schema_era.encode(),
        b"date_format": (date_format or "unspecified").encode(),
        b"source_record_count": str(batch.record_count).encode(),
    })
    schema = schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]
    contracts = tuple(
        field for field in mbs_field_contracts() if field.target_table == table
    )
    receipt_sha256 = receipt.digest()
    rows: list[dict[str, Any]] = []
    for record in batch.records:
        rows.append(_row(record, contracts, receipt_sha256, date_format))
        if len(rows) == rows_per_batch:
            yield pa.RecordBatch.from_pylist(rows, schema=schema)
            rows = []
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=schema)
