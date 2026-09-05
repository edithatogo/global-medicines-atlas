"""Source-specific legacy header mappings without clinical interpretation."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from string import ascii_uppercase, digits
from typing import Any

import pyarrow as pa

from .adapters.au_mbs_workbook import LEGACY_P7_SHEETS, parse_mbs_workbook
from .australian_source_contracts import mbs_field_contracts
from .mbs_workbook_silver import iter_workbook_silver_batches
from .receipts import SourceReceipt

_WIDE_HEADERS = (
    "ItemNum",
    "SubItemNum",
    "ItemStartDate",
    "ItemEndDate",
    "Category",
    "Group",
    "SubGroup",
    "SubHeading",
    "ItemType",
    "FeeType",
    "ProviderType",
    "NewItem",
    "ItemChange",
    "AnaesChange",
    "DescriptorChange",
    "FeeChange",
    "EMSNChange",
    "EMSNCap",
    "BenefitType",
    "BenefitStartDate",
    "FeeStartDate",
    "ScheduleFee",
    "Benefit100",
    "BasicUnits",
    "EMSNStartDate",
    "EMSNEndDate",
    "EMSNFixedCapAmount",
    "EMSNMaximumCap",
    "EMSNPercentageCap",
    "EMSNDescription",
    "EMSNChangeDate",
    "DescriptionStartDate",
    "Description",
    "QFEStartDate",
    "QFEEndDate",
    "DerivedFeeStartDate",
    "DerivedFee",
    "Benefit75",
    "Benefit85",
    "Anaes",
    "Element",
    "Class",
    "Technology",
    "Disease",
    "Tissue",
    "Exome",
    "Prenatal",
)
_COLUMNS = tuple(ascii_uppercase) + tuple(
    "A" + char for char in ascii_uppercase
)
_WIDE = tuple(zip(_COLUMNS[: len(_WIDE_HEADERS)], _WIDE_HEADERS, strict=True))
LEGACY_SHEET_PROFILES = tuple(
    (name, dimension, headers)
    for (name, dimension), headers in zip(
        LEGACY_P7_SHEETS,
        (
            _WIDE,
            (("A", "ItemNum"), ("B", "Description")),
            _WIDE,
            (("A", "Declining List"),),
        ),
        strict=True,
    )
)
_ANNOTATIONS = {
    "Element": "element",
    "Class": "class",
    "Technology": "technology",
    "Disease": "disease",
    "Tissue": "tissue",
    "Exome": "exome",
    "Prenatal": "prenatal",
}
_FIELDS = {field.native_name: field for field in mbs_field_contracts()}
_ADDITIONS = (
    pa.field("source_row_id", pa.string(), nullable=False),
    pa.field("header_coordinate", pa.string(), nullable=False),
    pa.field("native_header", pa.string()),
    pa.field("row_kind", pa.string(), nullable=False),
    pa.field("mapping_target", pa.string(), nullable=False),
    pa.field("mapping_field", pa.string()),
    pa.field("mapping_status", pa.string(), nullable=False),
)


def workbook_header_mapping(header: str | None) -> tuple[str, str | None]:
    """Return the existing source-native header destination, without inference."""
    if header in _FIELDS:
        return _FIELDS[header].target_table, header
    if header in _ANNOTATIONS:
        return "legacy_annotations", _ANNOTATIONS[header]
    if header == "Declining List":
        return "legacy_annotations", "declining_list_member"
    return "unmapped", None


def iter_workbook_domain_batches(
    payload: bytes, receipt: SourceReceipt, *, rows_per_batch: int = 1024
) -> Iterator[pa.RecordBatch]:
    """Map every cell by observed legacy headers, preserving unmapped cells.

    This binds source column lineage, not current status, clinical meaning,
    boolean flag interpretation or approval of the legacy author's annotations.
    The exact four-sheet header/shape profile must match before any output.
    """
    workbook = parse_mbs_workbook(payload, receipt)
    actual = tuple((sheet.name, sheet.dimension) for sheet in workbook.sheets)
    if actual != LEGACY_P7_SHEETS:
        raise ValueError("legacy workbook sheet profile differs")
    headers_by_path: dict[str, dict[str, str]] = {}
    for sheet, (_, _, headers) in zip(
        workbook.sheets, LEGACY_SHEET_PROFILES, strict=True
    ):
        observed = {
            cell.coordinate[:-1]: cell.display_value
            for cell in sheet.cells
            if re.fullmatch(r"[A-Z]+1", cell.coordinate)
            and cell.display_value is not None
        }
        if observed != dict(headers):
            raise ValueError("legacy workbook header profile differs")
        headers_by_path[sheet.path] = dict(headers)
    for batch in iter_workbook_silver_batches(
        payload, receipt, rows_per_batch=rows_per_batch
    ):
        metadata = dict(batch.schema.metadata or {})
        metadata.update({
            b"schema_name": b"global-medicines-atlas.mbs-workbook-domain.cells",
            b"schema_version": b"1.0",
            b"storage_schema_version": b"1.1",
            b"mapping_profile": b"mbs-p7-2024-07-headers-v1",
            b"claim_scope": b"legacy_source_annotations_only",
            b"profile_evidence": b"https://github.com/edithatogo/global-medicines-atlas/actions/runs/33305281887",
        })
        schema = batch.schema
        for field in _ADDITIONS:
            schema = schema.append(field)  # pyright: ignore[reportUnknownMemberType]
        schema = schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]
        rows: list[dict[str, Any]] = []
        for row in batch.to_pylist():
            column = row["coordinate"].rstrip(digits)
            header = headers_by_path[row["sheet_path"]].get(column)
            target, field = workbook_header_mapping(header)
            is_header = row["row_index"] == 1
            rows.append({
                **row,
                "source_row_id": f"{row['source_sha256']}:{row['sheet_path']}#row={row['row_index']}",
                "header_coordinate": column + "1",
                "native_header": header,
                "row_kind": "header" if is_header else "data_candidate",
                "mapping_target": "source_headers" if is_header else target,
                "mapping_field": field,
                "mapping_status": "header"
                if is_header
                else "unlabelled"
                if header is None
                else "source_explicit_header",
            })
        yield pa.RecordBatch.from_pylist(rows, schema=schema)


def profile_workbook_domain(
    payload: bytes, receipt: SourceReceipt
) -> dict[str, Any]:
    """Count header-bound mappings without asserting semantic promotion."""
    targets: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for batch in iter_workbook_domain_batches(payload, receipt):
        for row in batch.to_pylist():
            targets[row["mapping_target"]] += 1
            statuses[row["mapping_status"]] += 1
    return {
        "mapping_profile": "mbs-p7-2024-07-headers-v1",
        "source_sha256": receipt.payload.sha256,
        "cells": sum(targets.values()),
        "mapping_targets": dict(sorted(targets.items())),
        "mapping_statuses": dict(sorted(statuses.items())),
        "semantic_promotion": False,
    }
