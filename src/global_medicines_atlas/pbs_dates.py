"""Opt-in candidate PBS calendar dates with lossless native evidence."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import date
from typing import Any

import pyarrow as pa

from .adapters.au_pbs import DCTERMS_NAMESPACE, PBS_V3_NAMESPACE
from .pbs_entities import iter_pbs_entity_batches
from .receipts import SourceReceipt

CANDIDATE_PROFILE = "pbs-iso-date-candidate-v1"
MAX_BATCH_BYTES = 8 * 1024 * 1024
_PBS = f"{{{PBS_V3_NAMESPACE}}}"
_DCT = f"{{{DCTERMS_NAMESPACE}}}"
_GRAMMAR = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


def _contract(row: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    record_id = row["native_fields"][0]["record_id"]
    names = tuple(
        part.replace("~1", "/").replace("~0", "~")
        for part in record_id.split("/")[1::2]
    )
    role, suffix = "unmapped", ""
    if names in {(_PBS + "root",), (_PBS + "schedule",)}:
        role, suffix = "schedule_effective_date", "/attributes/effective-date"
    elif names == (_PBS + "root", _PBS + "info", _DCT + "valid"):
        role, suffix = "schedule_dct_valid", "/text"
    elif (
        row["mapping_target"] == "restrictions"
        and row["native_name"] == _PBS + "restriction"
    ):
        role, suffix = (
            "restriction_effective_date",
            "/attributes/effective-date",
        )
    field = next(
        (
            field
            for field in row["native_fields"]
            if field["path"] == record_id + suffix
        ),
        None,
    )
    return role, field


def _convert(
    value: str | None, state: str, profile: str | None
) -> tuple[date | None, str]:
    if value is None:
        return None, state
    if not value.strip():
        return None, "empty_value" if not value else "blank_value"
    if profile is None:
        return None, "profile_not_selected"
    if not _GRAMMAR.fullmatch(value):
        return None, "unsupported_format"
    try:
        return date.fromisoformat(value), "converted"
    except ValueError:
        return None, "invalid_date"


def _date_row(row: dict[str, Any], profile: str | None) -> dict[str, Any]:
    role, field = _contract(row)
    state = field["state"] if field is not None else "missing_field"
    value = field["value"] if field is not None else None
    index = int(row["native_fields"][0]["record_id"].rsplit("/", 1)[1])
    if role == "unmapped":
        state = "not_applicable"
        typed, status = None, "unmapped"
        occurrence_state = "not_applicable"
    else:
        typed, status = _convert(value, state, profile)
        occurrence_state = (
            "first_occurrence" if index == 1 else "repeated_occurrence"
        )
    return {
        **row,
        "date_role": role,
        "date_native_value": value,
        "date_native_state": state,
        "date_source_field_id": field["source_field_id"]
        if field is not None
        else None,
        "date_value": typed,
        "date_conversion_status": status,
        "date_occurrence_index": index if role != "unmapped" else None,
        "date_occurrence_state": occurrence_state,
    }


def _schema(native: pa.Schema, profile: str | None) -> pa.Schema:
    fields: list[pa.Field[pa.DataType]] = list(native)
    fields.extend(
        pa.field(name, pa.string(), nullable=nullable)
        for name, nullable in (
            ("date_role", False),
            ("date_native_value", True),
            ("date_native_state", False),
            ("date_source_field_id", True),
            ("date_conversion_status", False),
            ("date_occurrence_state", False),
        )
    )
    fields.extend((
        pa.field("date_value", pa.date32()),
        pa.field("date_occurrence_index", pa.int64()),
    ))
    metadata = dict(native.metadata or {})
    metadata.update({
        b"schema_name": b"global-medicines-atlas.pbs-silver.dates",
        b"date_profile": (profile or "not-selected").encode(),
        b"source_date_era_qualification": b"not-established",
        b"date_grammar": b"candidate-ascii-YYYY-MM-DD-calendar-only",
        b"temporal_status_inference": b"none",
        b"conversion": b"candidate-date32" if profile is not None else b"none",
        b"dimension": b"source_temporal_structure",
    })
    return pa.schema(fields).with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]


def iter_pbs_date_batches(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    date_profile: str | None = None,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Annotate supported source date slots without selecting source truth.

    Default behavior preserves native values without date conversion. The
    opt-in candidate profile accepts only ASCII YYYY-MM-DD calendar dates;
    it does not establish a source-era grammar or real-corpus qualification.
    Repeated source elements remain separate; first_occurrence is positional,
    not a uniqueness or precedence assertion. Missing elements are not invented.
    No intervals, timezone semantics, current status or entitlement are inferred.
    Existing parser/entity bounds apply, with an additional 8 MiB encoded JSON
    output budget (dates encoded as ISO strings), not a resident-memory cap.
    Discard partial outputs after an iterator error.
    """
    if date_profile is not None and date_profile != CANDIDATE_PROFILE:
        raise ValueError("unsupported PBS candidate date profile")
    rows: list[dict[str, Any]] = []
    size = 0
    schema: pa.Schema | None = None
    for batch in iter_pbs_entity_batches(
        payload, receipt, rows_per_batch=rows_per_batch
    ):
        if schema is None:
            schema = _schema(batch.schema, date_profile)
        for entity in batch.to_pylist():
            row = _date_row(entity, date_profile)
            row_size = len(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=date.isoformat,
                ).encode()
            )
            if row_size > MAX_BATCH_BYTES:
                raise ValueError("PBS date row exceeds batch byte limit")
            if rows and (
                len(rows) >= rows_per_batch or size + row_size > MAX_BATCH_BYTES
            ):
                yield pa.RecordBatch.from_pylist(rows, schema=schema)
                rows, size = [], 0
            rows.append(row)
            size += row_size
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=schema)
