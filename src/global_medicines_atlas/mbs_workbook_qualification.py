"""Bounded storage qualification, not semantic promotion, of workbook cells."""

from __future__ import annotations

import hashlib
import os
from collections import Counter
from io import BytesIO
from typing import TYPE_CHECKING, Any
from zipfile import ZipFile

import pyarrow as pa
import pyarrow.parquet as pq

from .adapters.au_mbs_workbook import (
    LEGACY_P7_BYTES,
    LEGACY_P7_SHA256,
    parse_mbs_workbook,
)
from .mbs_workbook_silver import iter_workbook_silver_batches
from .parser_safety import ParserPolicy, parse_xml
from .receipts import SourceReceipt

if TYPE_CHECKING:
    import httpx

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_POLICY = ParserPolicy(max_bytes=5_000_000)
_HEADER_MAX_ROW = 2
PUBLIC_WORKBOOK_URI = (
    "https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/"
    "resolve/4d1dae488ac43522f20e8320a8b2a56bf9138341/"
    "raw/mbs/legacy/2024-07/MBS-2024.07-Group-P7-Genetics.xlsx"
)


def acquire_hosted_workbook(client: httpx.Client) -> bytes:
    """Read only the pinned public workbook, anonymously in Actions."""
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY")
        == "edithatogo/global-medicines-atlas"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
    ):
        raise ValueError("live workbook qualification requires main Actions")
    payload = bytearray()
    with client.stream("GET", PUBLIC_WORKBOOK_URI) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(chunk_size=16_384):
            payload.extend(chunk)
            if len(payload) > LEGACY_P7_BYTES:
                raise ValueError("public workbook exceeds exact size")
    if (
        len(payload) != LEGACY_P7_BYTES
        or hashlib.sha256(payload).hexdigest() != LEGACY_P7_SHA256
    ):
        raise ValueError("public workbook does not match exact identity")
    return bytes(payload)


def _format_evidence(payload: bytes) -> dict[str, Any]:
    # Called only after the native parser has checked the entire ZIP envelope.
    with ZipFile(BytesIO(payload)) as archive:
        root = parse_xml(archive.read("xl/workbook.xml"), policy=_POLICY)
        properties = root.find(f"{{{_MAIN}}}workbookPr")
        result: dict[str, Any] = {
            "workbook_properties": dict(properties.attrib)
            if properties is not None
            else None,
            "styles_present": "xl/styles.xml" in archive.namelist(),
            "number_formats": [],
            "cell_formats": [],
            "interpretation": "native_attributes_only",
        }
        if result["styles_present"]:
            styles = parse_xml(archive.read("xl/styles.xml"), policy=_POLICY)
            result["number_formats"] = [
                dict(node.attrib)
                for node in styles.findall(
                    f"{{{_MAIN}}}numFmts/{{{_MAIN}}}numFmt"
                )
            ]
            result["cell_formats"] = [
                {"style_index": index, "attributes": dict(node.attrib)}
                for index, node in enumerate(
                    styles.findall(f"{{{_MAIN}}}cellXfs/{{{_MAIN}}}xf")
                )
            ]
        return result


def qualify_workbook_cells(
    payload: bytes, receipt: SourceReceipt
) -> dict[str, Any]:
    """Verify all native cells survive typed and Parquet projections.

    Header candidates are the first two native row coordinates, not inferred
    labels. Date epochs and format attributes are reported, never interpreted.
    No source acquisition, publication or promotion occurs in this function.
    """
    workbook = parse_mbs_workbook(payload, receipt)
    sheets: dict[str, dict[str, Any]] = {}
    for sheet in workbook.sheets:
        sheets[sheet.path] = {
            "name": sheet.name,
            "path": sheet.path,
            "dimension": sheet.dimension,
            "cells": 0,
            "formula_cells": 0,
            "error_cells": 0,
            "conversion_statuses": Counter(),
            "storage_types": Counter(),
            "header_candidates": [],
        }
    for batch in iter_workbook_silver_batches(payload, receipt):
        table = pa.Table.from_batches([batch])
        output = BytesIO()
        pq.write_table(table, output)  # pyright: ignore[reportUnknownMemberType]
        restored = pq.read_table(BytesIO(output.getvalue()))  # pyright: ignore[reportUnknownMemberType]
        if not table.equals(restored, check_metadata=True):
            raise ValueError("workbook Parquet roundtrip changed cells")
        for row in batch.to_pylist():
            sheet = sheets[row["sheet_path"]]
            sheet["cells"] += 1
            sheet["formula_cells"] += row["formula_state"] != "missing_field"
            sheet["error_cells"] += row["value_kind"] == "error"
            sheet["conversion_statuses"][row["conversion_status"]] += 1
            sheet["storage_types"][row["cell_type"] or "implicit_numeric"] += 1
            if row["row_index"] <= _HEADER_MAX_ROW:
                sheet["header_candidates"].append({
                    key: row[key]
                    for key in (
                        "coordinate",
                        "raw_value",
                        "display_value",
                        "style_index",
                        "formula_state",
                        "present_properties",
                    )
                })
    for native in workbook.sheets:
        if sheets[native.path]["cells"] != len(native.cells):
            raise ValueError("workbook cell denominator changed")
    return {
        "schema_version": 1,
        "qualification": "storage_candidate_only",
        "source_sha256": receipt.payload.sha256,
        "source_receipt_sha256": receipt.digest(),
        "bytes": len(payload),
        "sheet_count": len(sheets),
        "cells": sum(sheet["cells"] for sheet in sheets.values()),
        "sheets": list(sheets.values()),
        "format_evidence": _format_evidence(payload),
        "parquet_roundtrip_verified": True,
        "domain_mapping_qualified": False,
        "publication_performed": False,
    }
