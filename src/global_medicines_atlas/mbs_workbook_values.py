"""Loss-aware domain values alongside every native legacy workbook cell."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pyarrow as pa

from .australian_source_contracts import MbsFieldContract, mbs_field_contracts
from .mbs_typed_values import (
    CONVERSION_VERSION,
    DATE_FORMATS,
    convert_mbs_value,
)
from .mbs_workbook_domain import iter_workbook_domain_batches
from .receipts import SourceReceipt

_FIELDS = {field.native_name: field for field in mbs_field_contracts()}
_NUMERIC_TYPES = frozenset({"aud_decimal", "decimal", "percentage"})
_TEXT_STORAGE = frozenset({"s", "str", "inlineStr", "d"})
_DECIMAL = pa.decimal128(38, 9)
_ADDITIONS = (
    pa.field("domain_value_type", pa.string()),
    pa.field("domain_value_state", pa.string(), nullable=False),
    pa.field("domain_status", pa.string(), nullable=False),
    pa.field("domain_currency", pa.string()),
    pa.field("domain_text", pa.string()),
    pa.field("domain_date", pa.date32()),
    pa.field("domain_decimal", _DECIMAL),
)


def _values(row: dict[str, Any], date_format: str | None) -> dict[str, Any]:
    value = row["display_value"]
    state = (
        "value"
        if value is not None
        else "null"
        if "display_value" in row["present_properties"]
        else "missing_value"
    )
    result: dict[str, Any] = {
        "domain_value_type": None,
        "domain_value_state": state,
        "domain_status": "unmapped",
        "domain_currency": None,
        "domain_text": None,
        "domain_date": None,
        "domain_decimal": None,
    }
    if row["row_kind"] == "header":
        return {**result, "domain_status": "header"}
    if row["mapping_field"] is None:
        return result
    field = _FIELDS.get(row["mapping_field"])
    result["domain_value_type"] = (
        field.value_type if field else "legacy_annotation"
    )
    result["domain_currency"] = (
        "AUD" if field and field.value_type == "aud_decimal" else None
    )
    if value is None:
        return {**result, "domain_status": state}
    if row["cell_type"] == "e":
        return {**result, "domain_status": "source_error"}
    if field is None:
        return {**result, "domain_text": value, "domain_status": "preserved"}
    return _convert_field(row, field, date_format, result)


def _convert_field(
    row: dict[str, Any],
    field: MbsFieldContract,
    date_format: str | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    numeric_storage = row["cell_type"] in {None, "n"}
    if not numeric_storage and row["cell_type"] not in _TEXT_STORAGE:
        return {**result, "domain_status": "unsupported_storage_type"}
    if numeric_storage and field.value_type == "source_date":
        return {**result, "domain_status": "unsupported_serial_date"}
    if numeric_storage and field.value_type in _NUMERIC_TYPES:
        # OOXML numeric cells admit exponent notation; reuse their bounded
        # exact conversion, without changing the stricter XML text grammar.
        return {
            **result,
            "domain_decimal": row["decimal_value"],
            "domain_status": row["conversion_status"],
        }
    converted = convert_mbs_value(
        field.native_name,
        row["display_value"],
        "value",
        date_format=date_format,
    )
    typed = converted.typed_value
    result["domain_status"] = converted.status
    if isinstance(typed, Decimal):
        try:
            pa.scalar(typed, type=_DECIMAL)
        except pa.ArrowInvalid:
            result["domain_status"] = "unrepresentable"
        else:
            result["domain_decimal"] = typed
    elif isinstance(typed, date):
        result["domain_date"] = typed
    elif isinstance(typed, str):
        result["domain_text"] = typed
    return result


def iter_workbook_value_batches(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    date_format: str | None = None,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Type known fields without discarding native cells or cache provenance.

    Dates require an explicit text profile. Numeric Excel serials are never
    converted to dates. Legacy annotations remain literal strings, not flags
    or clinical/status conclusions. Decimal overflow/scale loss is explicit.
    """
    if date_format is not None and date_format not in DATE_FORMATS:
        raise ValueError("unsupported date format profile")
    for batch in iter_workbook_domain_batches(
        payload, receipt, rows_per_batch=rows_per_batch
    ):
        metadata = dict(batch.schema.metadata or {})
        metadata.update({
            b"schema_name": b"global-medicines-atlas.mbs-workbook-values.cells",
            b"schema_version": b"1.0",
            b"conversion_version": CONVERSION_VERSION.encode(),
            b"date_profile": (date_format or "unselected").encode(),
            b"date_interpretation": b"explicit_text_profile_only_no_serial_dates",
            b"currency_interpretation": b"per_domain_field",
            b"decimal_type": b"decimal128(38,9)",
        })
        schema = batch.schema
        for field in _ADDITIONS:
            schema = schema.append(field)  # pyright: ignore[reportUnknownMemberType]
        schema = schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]
        yield pa.RecordBatch.from_pylist(
            [{**row, **_values(row, date_format)} for row in batch.to_pylist()],
            schema=schema,
        )


def profile_workbook_values(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    date_format: str | None = None,
) -> dict[str, Any]:
    """Report conversion denominators without promoting semantic validity."""
    statuses: Counter[str] = Counter()
    by_field: defaultdict[str, Counter[str]] = defaultdict(Counter)
    source_errors = 0
    date_encodings: Counter[str] = Counter()
    date_fields: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for batch in iter_workbook_value_batches(
        payload, receipt, date_format=date_format
    ):
        for row in batch.to_pylist():
            status = row["domain_status"]
            statuses[status] += 1
            by_field[row["mapping_field"] or "(unmapped)"][status] += 1
            source_errors += row["error_code"] is not None
            field = _FIELDS.get(row["mapping_field"])
            if field is not None and field.value_type == "source_date":
                encoding = _date_encoding(row)
                date_encodings[encoding] += 1
                date_fields[field.native_name][encoding] += 1
    return {
        "schema_version": 1,
        "conversion_version": CONVERSION_VERSION,
        "date_profile": date_format,
        "source_sha256": receipt.payload.sha256,
        "cells": sum(statuses.values()),
        "statuses": dict(sorted(statuses.items())),
        "by_field": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_field.items())
        },
        "source_error_cells": source_errors,
        "date_encoding_profile_version": 1,
        "date_encoding_interpretation": "lexical_shape_only_not_calendar_or_order",
        "date_encoding_counts": dict(sorted(date_encodings.items())),
        "date_encodings_by_field": {
            key: dict(sorted(value.items()))
            for key, value in sorted(date_fields.items())
        },
        "semantic_promotion": False,
    }


def _date_encoding(row: dict[str, Any]) -> str:
    """Observe native storage/text shapes without choosing a date convention."""
    if row["row_kind"] == "header":
        return "header"
    if row["cell_type"] == "e":
        return "source_error"
    value = row["display_value"]
    if value is None:
        return row["domain_value_state"]
    if row["cell_type"] in {None, "n"}:
        return "numeric_storage_uninterpreted"
    if row["cell_type"] not in _TEXT_STORAGE:
        return "unsupported_storage"
    return _text_date_shape(value)


def _text_date_shape(value: str) -> str:
    if not value:
        return "empty_text"
    for pattern, label in (
        (r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", "two_two_four_dot"),
        (r"[0-9]{2}/[0-9]{2}/[0-9]{4}", "two_two_four_slash"),
        (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "four_two_two_hyphen"),
    ):
        if re.fullmatch(pattern, value):
            return label
    return "other_text"
