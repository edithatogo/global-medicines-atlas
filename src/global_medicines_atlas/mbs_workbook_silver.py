"""Typed workbook cell candidates preserving every sheet and cached value.

Cell types are storage types, not MBS domain mappings. Numeric serials are
not calendar dates or AUD amounts without an explicit column/style profile.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Any

import pyarrow as pa

from .adapters.au_mbs_workbook import MbsWorkbookCell, parse_mbs_workbook
from .australian_silver_metadata import receipt_projection_metadata
from .receipts import SourceReceipt

_DECIMAL = pa.decimal128(38, 9)
_MAX_DECIMAL_ADJUSTED = 28
_MIN_DECIMAL_ADJUSTED = -9
_NUMBER = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z"
)
_COORDINATE = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})\Z")
MAX_BATCH_ROWS = 4096
MAX_COLUMN = 16384
MAX_ROW = 1048576
WORKBOOK_CELL_SCHEMA = pa.schema(
    [
        pa.field("source_path", pa.string(), nullable=False),
        pa.field("source_sha256", pa.string(), nullable=False),
        pa.field("receipt_sha256", pa.string(), nullable=False),
        pa.field("coordinate", pa.string(), nullable=False),
        pa.field("row_index", pa.int32(), nullable=False),
        pa.field("column_index", pa.int32(), nullable=False),
        pa.field("cell_type", pa.string()),
        pa.field("style_index", pa.int64()),
        pa.field("formula", pa.string()),
        pa.field("raw_value", pa.string()),
        pa.field("display_value", pa.string()),
        pa.field("present_properties", pa.list_(pa.string()), nullable=False),
        pa.field("formula_state", pa.string(), nullable=False),
        pa.field("value_origin", pa.string(), nullable=False),
        pa.field("value_kind", pa.string(), nullable=False),
        pa.field("conversion_status", pa.string(), nullable=False),
        pa.field("decimal_value", _DECIMAL),
        pa.field("boolean_value", pa.bool_()),
        pa.field("text_value", pa.string()),
        pa.field("error_code", pa.string()),
    ],
    metadata={
        "schema_name": "global-medicines-atlas.mbs-workbook-silver.cells",
        "schema_version": "1.0",
        "source_id": "au-mbs-p7-legacy-workbook",
        "subject_kind": "service",
        "dimension": "service_benefit",
        "absence_interpretation": "unknown",
        "qualification": "candidate",
        "date_interpretation": "source_serial_or_text_only",
        "currency_interpretation": "unspecified",
    },
)


def _coordinates(value: str) -> tuple[int, int]:
    match = _COORDINATE.fullmatch(value)
    if match is None:
        raise ValueError("invalid workbook cell coordinate")
    column = 0
    for letter in match[1]:
        column = column * 26 + ord(letter) - ord("A") + 1
    row = int(match[2])
    if column > MAX_COLUMN or row > MAX_ROW:
        raise ValueError("workbook coordinate exceeds worksheet bounds")
    return row, column


def _value(cell: MbsWorkbookCell) -> dict[str, Any]:
    kind = {
        None: "number",
        "n": "number",
        "s": "string",
        "str": "string",
        "inlineStr": "string",
        "b": "boolean",
        "e": "error",
        "d": "date_text",
    }.get(cell.cell_type, "unknown")
    result: dict[str, Any] = {
        "value_kind": kind,
        "conversion_status": "preserved",
        "decimal_value": None,
        "boolean_value": None,
        "text_value": None,
        "error_code": None,
    }
    key = "display_value" if kind in {"string", "date_text"} else "raw_value"
    value = cell.display_value if key == "display_value" else cell.raw_value
    if value is None:
        result["conversion_status"] = (
            "null"
            if key in (cell.present_properties or ())
            else "missing_value"
        )
    elif kind in {"string", "date_text"}:
        result["text_value"] = value
    elif kind == "error":
        result["error_code"] = value
        result["conversion_status"] = "error"
    elif kind == "boolean":
        if value in {"0", "1"}:
            result["boolean_value"] = value == "1"
            result["conversion_status"] = "converted"
        else:
            result["conversion_status"] = "invalid"
    elif kind == "number":
        result.update(_number(value))
    else:
        result["conversion_status"] = "unsupported_type"
    return result


def _number(value: str) -> dict[str, Any]:
    if not value.strip():
        return {"conversion_status": "blank"}
    if not _NUMBER.fullmatch(value):
        return {"conversion_status": "invalid"}
    try:
        decimal = Decimal(value)
    except InvalidOperation:
        return {"conversion_status": "unrepresentable"}
    if not decimal.is_finite() or (
        not decimal.is_zero()
        and not _MIN_DECIMAL_ADJUSTED
        <= decimal.adjusted()
        <= _MAX_DECIMAL_ADJUSTED
    ):
        return {"conversion_status": "unrepresentable"}
    if decimal.is_zero():
        decimal = Decimal(0)
    try:
        pa.scalar(decimal, type=_DECIMAL)
    except pa.ArrowInvalid:
        return {"conversion_status": "unrepresentable"}
    return {"decimal_value": decimal, "conversion_status": "converted"}


def _row(
    cell: MbsWorkbookCell,
    path: str,
    source_sha256: str,
    receipt_sha256: str,
) -> dict[str, Any]:
    if cell.present_properties is None:
        raise ValueError("workbook property presence is unknown")
    row_index, column_index = _coordinates(cell.coordinate)
    formula_present = "formula" in cell.present_properties
    return {
        **cell.model_dump(),
        "source_path": f"{path}#{cell.coordinate}",
        "source_sha256": source_sha256,
        "receipt_sha256": receipt_sha256,
        "row_index": row_index,
        "column_index": column_index,
        "formula_state": "missing_field"
        if not formula_present
        else "null"
        if cell.formula is None
        else "value",
        "value_origin": "formula_cache" if formula_present else "literal",
        **_value(cell),
    }


def iter_workbook_silver_batches(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Yield source-ordered cell batches for every sheet, including empty ones.

    The existing bounded ZIP/XML parser validates source bytes first. No
    formula, number format, currency or Excel date epoch is interpreted.
    """
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("workbook batch size must be between 1 and 4096")
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    workbook = parse_mbs_workbook(payload, receipt)
    receipt_sha256 = receipt.digest()
    for sheet in workbook.sheets:
        metadata = dict(WORKBOOK_CELL_SCHEMA.metadata or {})
        metadata.update(receipt_projection_metadata(receipt))
        metadata.update({
            b"schema_era": workbook.schema_era.encode(),
            b"sheet_name": sheet.name.encode(),
            b"sheet_path": sheet.path.encode(),
            b"sheet_relationship_id": sheet.relationship_id.encode(),
            b"sheet_dimension": json.dumps(sheet.dimension).encode(),
            b"sheet_present_properties": json.dumps(
                sheet.present_properties
            ).encode(),
            b"sheet_count": str(workbook.sheet_count).encode(),
            b"sheet_cell_count": str(len(sheet.cells)).encode(),
        })
        schema = WORKBOOK_CELL_SCHEMA.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]
        rows: list[dict[str, Any]] = []
        for cell in sheet.cells:
            rows.append(
                _row(cell, sheet.path, receipt.payload.sha256, receipt_sha256)
            )
            if len(rows) == rows_per_batch:
                yield pa.RecordBatch.from_pylist(rows, schema=schema)
                rows = []
        if rows or not sheet.cells:
            yield pa.RecordBatch.from_pylist(rows, schema=schema)
