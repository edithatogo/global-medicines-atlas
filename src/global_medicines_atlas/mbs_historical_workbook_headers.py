"""Digest-bound candidate header profiles for frozen historical MBS workbooks.

Only native string rows from the first bounded worksheet rows are emitted.
Exact ordered demographic and group headers bind supported labels; unmatched
header candidates and all non-header cells remain unresolved.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast
from zipfile import ZipFile

from .adapters.au_mbs_workbook import decode_workbook_cell
from .archive_safety import inspect_zip
from .mbs_demographic_extraction import (
    ARCHIVE_POLICY,
    MAX_MEMBER_BYTES,
    WORKSHEET_POLICY,
    read_bounded_workbook_member,
    read_workbook_shared_strings,
    workbook_cell_position,
    workbook_sheet_targets,
)
from .mbs_historical_csv_package import FrozenMbsMember
from .parser_safety import iter_xml_events

MAX_HEADER_SCAN_ROWS = 20
MIN_CANDIDATE_LABELS = 2
MAX_CANDIDATE_LABELS = 64
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
HEADER_CONTRACTS = {
    (
        "Year",
        "Month",
        "Item_Number",
        "State",
        "Age_Range",
        "Gender",
        "Services",
        "Benefits ($)",
    ): (
        "mbs-demographic-workbook-v1",
        (
            "calendar_year_label",
            "processing_month_label",
            "schedule_item_identifier",
            "state_label",
            "age_range_label",
            "gender_label",
            "service_count_label",
            "benefit_amount_label_currency_unresolved",
        ),
    ),
    (
        "Year",
        "Month",
        "Group",
        "Sub_Group",
        "Item_Number",
        "State",
        "Services",
        "Benefits ($)",
    ): (
        "mbs-group-workbook-v1",
        (
            "calendar_year_label",
            "processing_month_label",
            "schedule_group_identifier",
            "schedule_subgroup_identifier",
            "schedule_item_identifier",
            "state_label",
            "service_count_label",
            "benefit_amount_label_currency_unresolved",
        ),
    ),
}


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_profile(  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- one streaming worksheet state machine
    payload: bytes, shared_strings: tuple[str, ...]
) -> tuple[str | None, list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    root_tag: str | None = None
    dimension: str | None = None
    for event, element, parent in iter_xml_events(
        payload, policy=WORKSHEET_POLICY
    ):
        if event == "start" and parent is None:
            root_tag = element.tag
        if event == "end" and element.tag == f"{{{MAIN}}}dimension":
            dimension = element.attrib.get("ref")
        if event != "end" or element.tag != f"{{{MAIN}}}row":
            continue
        index_text = element.attrib.get("r", "")
        if not index_text.isascii() or not index_text.isdecimal():
            raise ValueError("historical worksheet row index differs")
        row_index = int(index_text)
        if row_index > MAX_HEADER_SCAN_ROWS:
            break
        if parent is None or parent.tag != f"{{{MAIN}}}sheetData":
            raise ValueError("historical worksheet row parent differs")
        labels: list[dict[str, str]] = []
        seen: set[str] = set()
        invalid = False
        for cell in element.findall(f"{{{MAIN}}}c"):
            decoded = decode_workbook_cell(cell, shared_strings)
            if decoded.formula is not None:
                invalid = True
                break
            if decoded.cell_type not in {"s", "inlineStr"}:
                if decoded.display_value not in {None, ""}:
                    invalid = True
                    break
                continue
            value = decoded.display_value
            if value is None or not value.strip() or value in seen:
                invalid = True
                break
            _, column = workbook_cell_position(decoded.coordinate)
            labels.append({"column": _column_name(column), "text": value})
            seen.add(value)
            if len(labels) > MAX_CANDIDATE_LABELS:
                invalid = True
                break
        if not invalid and len(labels) >= MIN_CANDIDATE_LABELS:
            header_text = tuple(label["text"] for label in labels)
            contract = HEADER_CONTRACTS.get(header_text)
            if contract is not None and tuple(
                label["column"] for label in labels
            ) != tuple(
                _column_name(index) for index in range(1, len(labels) + 1)
            ):
                contract = None
            candidate: dict[str, object] = {
                "row_index": row_index,
                "labels": labels,
                "disposition": (
                    "exact_contract_match"
                    if contract
                    else "unresolved_candidate"
                ),
            }
            if contract is not None:
                contract_id, targets = contract
                candidate["contract_id"] = contract_id
                candidate["column_bindings"] = [
                    {
                        "column": label["column"],
                        "native_header": label["text"],
                        "field": field,
                        "status": "interpreted",
                    }
                    for label, field in zip(labels, targets, strict=True)
                ]
            rows.append(candidate)
        element.clear()
    if root_tag != f"{{{MAIN}}}worksheet":
        raise ValueError("historical worksheet root differs")
    return dimension, rows


def profile_workbook_headers(
    path: Path, member: FrozenMbsMember, native_path: str
) -> dict[str, Any]:
    """Verify exact member bytes and return sheet/header candidates only."""
    if (
        member.suffix != ".xlsx"
        or type(member.byte_count) is not int
        or not 0 < member.byte_count <= ARCHIVE_POLICY.max_archive_bytes
        or hashlib.sha256(native_path.encode()).hexdigest()
        != member.path_sha256
    ):
        raise ValueError("historical workbook identity or bound differs")
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size != member.byte_count
    ):
        raise ValueError("historical workbook identity or bound differs")
    payload = path.read_bytes()
    if (
        len(payload) != member.byte_count
        or hashlib.sha256(payload).hexdigest() != member.sha256
    ):
        raise ValueError("historical workbook member digest differs")
    inspect_zip(payload, policy=ARCHIVE_POLICY)
    with ZipFile(path) as archive:
        shared_strings, _ = read_workbook_shared_strings(archive)
        sheets: list[dict[str, object]] = []
        for ordinal, (name, sheet_path, relationship) in enumerate(
            workbook_sheet_targets(archive)
        ):
            sheet_payload = read_bounded_workbook_member(
                archive, sheet_path, MAX_MEMBER_BYTES
            )
            dimension, candidate_rows = _sheet_profile(
                sheet_payload, shared_strings
            )
            sheets.append({
                "ordinal": ordinal,
                "name": name,
                "part_sha256": hashlib.sha256(sheet_payload).hexdigest(),
                "dimension": dimension,
                "relationship_id": relationship,
                "candidate_rows": candidate_rows,
            })
    profile = {
        "sheets": [
            {
                "ordinal": sheet["ordinal"],
                "name": sheet["name"],
                "dimension": sheet["dimension"],
                "candidate_rows": sheet["candidate_rows"],
            }
            for sheet in sheets
        ]
    }
    canonical = json.dumps(
        profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        "member_sha256": member.sha256,
        "member_bytes": member.byte_count,
        "member_path_sha256": member.path_sha256,
        "source_sha256": member.source.source_sha256,
        "source_revision": member.source.revision,
        "sheets": sheets,
        "canonical_profile": canonical,
        "header_profile_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "candidate_only": True,
        "supported_header_mappings_present": any(
            row["disposition"] == "exact_contract_match"
            for sheet in sheets
            for row in cast("list[dict[str, object]]", sheet["candidate_rows"])
        ),
        "whole_workbook_semantics_complete": False,
        "unmatched_header_cells": "unresolved",
        "non_header_cells": "native_unresolved",
    }
