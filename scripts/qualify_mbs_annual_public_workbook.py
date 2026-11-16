"""Profile one public aggregate workbook without emitting observation values."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import] -- bounded parser supplies elements
    ElementTree as ET,
)
from zipfile import ZipFile

from global_medicines_atlas.adapters.au_mbs_workbook import (
    MbsWorkbookCell,
    decode_workbook_cell,
)
from global_medicines_atlas.archive_safety import ArchivePolicy, inspect_zip
from global_medicines_atlas.mbs_demographic_extraction import (
    MAX_MEMBER_BYTES,
    METADATA_POLICY,
    WORKSHEET_POLICY,
    read_bounded_workbook_member,
    read_workbook_shared_strings,  # pyright: ignore[reportUnknownVariableType]
    workbook_cell_position,
    workbook_sheet_targets,
)
from global_medicines_atlas.parser_safety import iter_xml_events, parse_xml

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
DATASET = "edithatogo/australian-mbs-utilisation-archive"
REVISION = "05342df7dd2f92fe6e85e28e8add9bf3f43d0389"
SHA256 = "ace9d6e72dcfca3c9fd779b4c476788ea1d465ceaafd465f97cea712dad44598"
BYTE_COUNT = 1_058_479
SOURCE_URL = (
    "https://www.health.gov.au/sites/default/files/2026-08/"
    "medicare-annual-statistics-state-and-territory-2009-10-to-2024-25.xlsx"
)
FILENAME = (
    "medicare-annual-statistics-state-and-territory-2009-10-to-2024-25.xlsx"
)
RAW_PATH = (
    "raw/mbs/public-backfill/medicare_statistics_collection_attachment/"
    f"{SHA256}/{FILENAME}"
)
RECEIPT_PATH = (
    "bronze/mbs/public-backfill/medicare_statistics_collection_attachment/"
    f"{SHA256}/{FILENAME}.receipt.json"
)
RECEIPT_SHA256 = (
    "4328cf80841e3f766041efc0537ecfd31ef1bfab1e728a629081995cf24f066c"
)
TITLE = "Table 3: Financial Year Patient* Statistics by Broad Type of Service and State"
DEFINITION = (
    "* A patient is defined as a person who claimed at least one MBS service."
)
HEADERS = (
    "Financial Year",
    "State",
    "Column1",
    "Broad Type of Service",
    "Patients",
    "Patients as percent of Population",
    "Services",
    "Services per Patient",
    "Services per capita",
    "Benefits",
    "Benefits per Patient",
    "Benefits per capita",
    "Estimated Resident Population",
)
POLICY = ArchivePolicy(
    max_archive_bytes=2 * 1024 * 1024,
    max_entries=64,
    max_entry_uncompressed_bytes=3 * 1024 * 1024,
    max_total_uncompressed_bytes=8 * 1024 * 1024,
    max_decompression_ratio=100,
    max_path_depth=8,
)
FISCAL_YEAR = re.compile(r"([0-9]{4})-([0-9]{2})\Z")
MAX_ROW = 1_048_576
MAX_RECEIPT_BYTES = 4096
TITLE_ROW = 1
DEFINITION_ROW = 5
HEADER_ROW = 9
Cell = tuple[MbsWorkbookCell, bool]


def _numeric_patient_shape(text: str) -> str:
    try:
        value = Decimal(text)
        if (
            value.is_finite()
            and value >= 0
            and value == value.to_integral_value()
        ):
            return "numeric_nonnegative_integer"
    except InvalidOperation:
        pass
    return "numeric_other_uninterpreted"


def _patient_shape(cell: Cell | None) -> str:
    if cell is None:
        return "missing"
    decoded, formula_present = cell
    if formula_present:
        return "formula_uninterpreted"
    if decoded.cell_type == "e":
        return "source_error"
    if decoded.display_value is None:
        return "missing"
    if decoded.cell_type not in {None, "n"}:
        return "text_uninterpreted"
    return _numeric_patient_shape(decoded.display_value)


def _native_value(cell: Cell | None) -> str | None:
    if cell is None or cell[1]:
        return None
    return cell[0].display_value


def _fiscal_year(value: str | None) -> bool:
    match = FISCAL_YEAR.fullmatch(value or "")
    return bool(match and (int(match[1]) + 1) % 100 == int(match[2]))


@dataclass
class _SheetAccumulator:
    title: str | None = None
    definition: str | None = None
    dimension: str | None = None
    headers: list[str] | None = None
    years: set[str] = field(default_factory=set)
    states: set[str] = field(default_factory=set)
    groups: set[str] = field(default_factory=set)
    keys: Counter[tuple[str, str, str]] = field(default_factory=Counter)
    shapes: Counter[str] = field(default_factory=Counter)
    data_rows: int = 0
    empty_rows: int = 0
    unclassified_rows: int = 0

    def observe_data_row(self, cells: dict[int, Cell]) -> None:
        if all(
            _native_value(cell) is None and not cell[1]
            for cell in cells.values()
        ):
            self.empty_rows += 1
            return
        year = _native_value(cells.get(1))
        state = _native_value(cells.get(2))
        group = _native_value(cells.get(4))
        if year is None or not _fiscal_year(year) or not state or not group:
            self.unclassified_rows += 1
            return
        self.data_rows += 1
        self.years.add(year)
        self.states.add(state)
        self.groups.add(group)
        self.keys[year, state, group] += 1
        self.shapes[_patient_shape(cells.get(5))] += 1

    def observe_row(self, row: int, cells: dict[int, Cell]) -> None:
        if row == TITLE_ROW:
            self.title = _native_value(cells.get(1))
        elif row == DEFINITION_ROW:
            self.definition = _native_value(cells.get(1))
        elif row == HEADER_ROW:
            labels = [
                _native_value(cells.get(column))
                for column in range(1, len(HEADERS) + 1)
            ]
            extras = any(
                column > len(HEADERS)
                and (_native_value(cell) is not None or cell[1])
                for column, cell in cells.items()
            )
            if labels != list(HEADERS) or extras:
                raise ValueError("annual workbook patient headers differ")
            self.headers = list(HEADERS)
        elif row > HEADER_ROW:
            self.observe_data_row(cells)

    def result(self) -> dict[str, Any]:
        if self.title != TITLE:
            raise ValueError("annual workbook patient title differs")
        if self.definition != DEFINITION:
            raise ValueError("annual workbook patient definition differs")
        if self.headers is None:
            raise ValueError("annual workbook patient header is missing")
        return {
            "sheet_name": "Patients",
            "dimension": self.dimension,
            "native_title": self.title,
            "patient_definition": self.definition,
            "native_header_labels": self.headers,
            "data_rows": self.data_rows,
            "empty_rows_after_header": self.empty_rows,
            "unclassified_rows_after_header": self.unclassified_rows,
            "financial_year_labels": sorted(self.years),
            "state_label_count": len(self.states),
            "service_group_label_count": len(self.groups),
            "duplicate_year_state_group_keys": sum(
                count - 1 for count in self.keys.values() if count > 1
            ),
            "patient_value_shape_scope": "classified_rows_only",
            "patient_value_shapes": dict(sorted(self.shapes.items())),
        }


def _row_cells(
    element: ET.Element, row: int, shared: tuple[str, ...]
) -> dict[int, Cell]:
    cells: dict[int, Cell] = {}
    for child in element.findall(f"{{{MAIN}}}c"):
        decoded = decode_workbook_cell(child, shared)
        cell_row, column = workbook_cell_position(decoded.coordinate)
        if cell_row != row or column in cells:
            raise ValueError("annual workbook cell identity differs")
        cells[column] = (decoded, child.find(f"{{{MAIN}}}f") is not None)
    return cells


def _profile_sheet(payload: bytes, shared: tuple[str, ...]) -> dict[str, Any]:
    result = _SheetAccumulator()
    previous = 0
    root_seen = False
    for event, element, parent in iter_xml_events(
        payload, policy=WORKSHEET_POLICY
    ):
        if event == "start" and parent is None:
            root_seen = element.tag == f"{{{MAIN}}}worksheet"
        if event != "end":
            continue
        if element.tag == f"{{{MAIN}}}dimension":
            result.dimension = element.get("ref")
        if element.tag != f"{{{MAIN}}}row":
            continue
        if parent is None or parent.tag != f"{{{MAIN}}}sheetData":
            raise ValueError("annual workbook row parent differs")
        index = element.get("r", "")
        if (
            not index.isascii()
            or not index.isdecimal()
            or not previous < int(index) <= MAX_ROW
        ):
            raise ValueError("annual workbook row identity differs")
        row = int(index)
        previous = row
        result.observe_row(row, _row_cells(element, row, shared))
        parent.remove(element)
        element.clear()
    if not root_seen:
        raise ValueError("annual workbook worksheet root differs")
    return result.result()


def profile_workbook(
    payload: bytes, *, expected_sha256: str, expected_bytes: int
) -> dict[str, Any]:
    """Profile the exact digest-bound workbook with no row values in output."""
    if (
        type(expected_bytes) is not int
        or not 0 < expected_bytes <= POLICY.max_archive_bytes
        or len(payload) != expected_bytes
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or hashlib.sha256(payload).hexdigest() != expected_sha256
    ):
        raise ValueError("annual workbook identity differs")
    member_count = inspect_zip(payload, policy=POLICY)
    with ZipFile(BytesIO(payload)) as archive:
        if archive.testzip() is not None:
            raise ValueError("annual workbook archive integrity differs")
        types = parse_xml(
            read_bounded_workbook_member(
                archive, "[Content_Types].xml", 3 * 1024 * 1024
            ),
            policy=METADATA_POLICY,
        )
        if types.tag != f"{{{TYPES}}}Types":
            raise ValueError("annual workbook content types differ")
        shared = read_workbook_shared_strings(archive)[0]
        descriptors = workbook_sheet_targets(archive)
        patient_sheets = [item for item in descriptors if item[0] == "Patients"]
        if len(patient_sheets) != 1:
            raise ValueError("annual workbook patient sheet differs")
        sheet = read_bounded_workbook_member(
            archive, patient_sheets[0][1], MAX_MEMBER_BYTES
        )
        result = _profile_sheet(sheet, shared)
    result["sheet_names"] = [item[0] for item in descriptors]
    result["patient_sheet_part"] = patient_sheets[0][1]
    result["patient_sheet_sha256"] = hashlib.sha256(sheet).hexdigest()
    result["archive_member_count"] = member_count
    result["archive_crc_check"] = "passed"
    return result


def qualify_archived_workbook(payload: bytes, receipt: bytes) -> dict[str, Any]:
    """Bind a partial structural profile to the exact public B1/B2 objects."""
    if (
        len(receipt) > MAX_RECEIPT_BYTES
        or hashlib.sha256(receipt).hexdigest() != RECEIPT_SHA256
    ):
        raise ValueError("annual workbook source receipt identity differs")
    raw_source: object = json.loads(receipt)
    if not isinstance(raw_source, dict):
        raise TypeError("annual workbook source receipt content differs")
    source = cast("dict[str, Any]", raw_source)
    expected: dict[str, object] = {
        "schema_id": "global-medicines-atlas.australian-harvest-receipt",
        "schema_version": 1,
        "source_id": "au-health-medicare-statistics",
        "category": "medicare_statistics_collection_attachment",
        "source_url": SOURCE_URL,
        "archive_path": RAW_PATH,
        "sha256": SHA256,
        "byte_count": BYTE_COUNT,
    }
    if any(source.get(key) != value for key, value in expected.items()):
        raise ValueError("annual workbook source receipt content differs")
    return {
        "schema_id": "global-medicines-atlas.mbs-annual-public-workbook-qualification",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "source": {
            "dataset": DATASET,
            "revision": REVISION,
            "raw_path": RAW_PATH,
            "source_url": SOURCE_URL,
            "sha256": SHA256,
            "byte_count": BYTE_COUNT,
            "receipt_path": RECEIPT_PATH,
            "receipt_sha256": RECEIPT_SHA256,
            "transport": "previously archived public-copy transport; exact anonymous readback",
        },
        "profile": profile_workbook(
            payload, expected_sha256=SHA256, expected_bytes=BYTE_COUNT
        ),
        "qualification": {
            "status": "bounded_source_native_structure_and_definition_only",
            "patient_definition": "literal source note, not a cross-group deduplication rule",
            "cross_group_deduplication_qualified": False,
            "temporal_completeness_claimed": False,
            "item_level_patient_counts_qualified": False,
            "patient_denominator_admitted": False,
            "time_basis_and_suppression_semantics_qualified": False,
            "rights_or_publication_decision_changed": False,
            "m106_accepted": False,
            "federation_v4_admission_performed": False,
            "patient_observation_values_emitted": False,
            "geography_or_service_group_labels_emitted": False,
            "individual_participant_or_cohort_data_accessed": False,
            "new_dataset_published": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    with args.receipt.open("rb") as source:
        receipt = source.read(MAX_RECEIPT_BYTES + 1)
    payload = sys.stdin.buffer.read(BYTE_COUNT + 1)
    report = qualify_archived_workbook(payload, receipt)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
