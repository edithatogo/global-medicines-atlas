"""Bounded source-native projection of the legacy Australian MBS workbook."""

from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from typing import Literal
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)
from zipfile import BadZipFile, ZipFile

from pydantic import Field, model_validator

from ..archive_safety import ArchivePolicy, inspect_zip
from ..models import FrozenModel, Provenance
from ..parser_safety import ParserPolicy, parse_xml
from ..receipts import SourceReceipt
from ._receipt import provenance_from_receipt

SOURCE_ID = "au-mbs-p7-legacy-workbook"
LEGACY_P7_BYTES = 87_727
LEGACY_P7_SHA256 = (
    "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
)
LEGACY_P7_SHEETS = (
    ("Sheet1", "A1:AV161"),
    ("Sheet2", "A1:B161"),
    ("Sheet1 (2)", "A1:AV183"),
    ("Sheet3", "A1:A21"),
)
_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
_PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_ARCHIVE_POLICY = ArchivePolicy(
    max_archive_bytes=1_000_000,
    max_entries=256,
    max_total_uncompressed_bytes=20_000_000,
    max_decompression_ratio=250,
    max_path_depth=8,
)
_XML_POLICY = ParserPolicy(
    max_bytes=5_000_000,
    max_xml_depth=16,
    max_xml_elements=100_000,
    max_xml_text_bytes=5_000_000,
)


class MbsWorkbookCell(FrozenModel):
    """One XLSX cell retaining formula, type, style and source value."""

    coordinate: str = Field(min_length=1)
    cell_type: str | None = None
    style_index: int | None = Field(default=None, ge=0)
    formula: str | None = None
    raw_value: str | None = None
    display_value: str | None = None


class MbsWorkbookSheet(FrozenModel):
    """One workbook sheet in workbook order."""

    name: str = Field(min_length=1)
    relationship_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    dimension: str | None = None
    cells: tuple[MbsWorkbookCell, ...]

    @model_validator(mode="after")
    def coordinates_are_unique(self) -> MbsWorkbookSheet:
        coordinates = tuple(cell.coordinate for cell in self.cells)
        if len(coordinates) != len(set(coordinates)):
            raise ValueError(
                "workbook sheet contains duplicate cell coordinates"
            )
        return self


class MbsWorkbookBatch(FrozenModel):
    """Source-native workbook projection with receipt-bound provenance."""

    source_id: Literal["au-mbs-p7-legacy-workbook"] = SOURCE_ID
    schema_era: str = Field(min_length=1)
    sheets: tuple[MbsWorkbookSheet, ...] = Field(min_length=1)
    provenance: Provenance

    @property
    def sheet_count(self) -> int:
        """Return the workbook sheet denominator."""
        return len(self.sheets)


def _member(archive: ZipFile, name: str) -> bytes:
    try:
        return archive.read(name)
    except (BadZipFile, KeyError) as error:
        raise ValueError(
            f"workbook is missing required member {name!r}"
        ) from error


def _relationship_path(target: str) -> str:
    if not target or "\\" in target:
        raise ValueError("workbook relationship target is invalid")
    target_path = PurePosixPath(target)
    if target_path.is_absolute() or ".." in target_path.parts:
        raise ValueError("workbook relationship target escapes the archive")
    path = (
        target_path
        if target_path.parts[:1] == ("xl",)
        else PurePosixPath("xl") / target_path
    )
    if path.parts[:2] != ("xl", "worksheets"):
        raise ValueError("workbook relationship target is not a worksheet")
    return path.as_posix()


def _shared_strings(archive: ZipFile) -> tuple[str, ...]:
    try:
        payload = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return ()
    root = parse_xml(payload, policy=_XML_POLICY)
    return tuple(
        "".join(node.text or "" for node in item.iter(f"{{{_MAIN}}}t"))
        for item in root.findall(f"{{{_MAIN}}}si")
    )


def _cell(
    element: ET.Element,
    shared_strings: tuple[str, ...],
) -> MbsWorkbookCell:
    # ElementTree nodes are converted immediately into frozen scalar models.
    cell = element
    coordinate = cell.attrib.get("r", "")
    if not coordinate:
        raise ValueError("workbook cell is missing its coordinate")
    cell_type = cell.attrib.get("t")
    style_text = cell.attrib.get("s")
    try:
        style_index = int(style_text) if style_text is not None else None
    except ValueError as error:
        raise ValueError("workbook cell style index is invalid") from error
    formula_node = cell.find(f"{{{_MAIN}}}f")
    value_node = cell.find(f"{{{_MAIN}}}v")
    raw_value = value_node.text if value_node is not None else None
    display_value = raw_value
    if cell_type == "s" and raw_value is not None:
        try:
            display_value = shared_strings[int(raw_value)]
        except (IndexError, ValueError) as error:
            raise ValueError(
                "workbook shared-string index is invalid"
            ) from error
    elif cell_type == "inlineStr":
        display_value = "".join(
            node.text or "" for node in cell.iter(f"{{{_MAIN}}}t")
        )
    return MbsWorkbookCell(
        coordinate=coordinate,
        cell_type=cell_type,
        style_index=style_index,
        formula=formula_node.text if formula_node is not None else None,
        raw_value=raw_value,
        display_value=display_value,
    )


def _sheet(
    archive: ZipFile,
    *,
    name: str,
    relationship_id: str,
    path: str,
    shared_strings: tuple[str, ...],
) -> MbsWorkbookSheet:
    root = parse_xml(_member(archive, path), policy=_XML_POLICY)
    dimension_node = root.find(f"{{{_MAIN}}}dimension")
    cells = tuple(
        _cell(element, shared_strings)
        for element in root.findall(f".//{{{_MAIN}}}c")
    )
    return MbsWorkbookSheet(
        name=name,
        relationship_id=relationship_id,
        path=path,
        dimension=(
            dimension_node.attrib.get("ref")
            if dimension_node is not None
            else None
        ),
        cells=cells,
    )


def parse_mbs_workbook(
    payload: bytes,
    receipt: SourceReceipt,
) -> MbsWorkbookBatch:
    """Project XLSX cells without interpreting formulas, dates or amounts."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=SOURCE_ID,
        jurisdiction="AUS",
        transformation="au-mbs-p7-xlsx-v1",
    )
    inspect_zip(payload, _ARCHIVE_POLICY)
    with ZipFile(BytesIO(payload)) as archive:
        workbook = parse_xml(
            _member(archive, "xl/workbook.xml"),
            policy=_XML_POLICY,
        )
        relationships = parse_xml(
            _member(archive, "xl/_rels/workbook.xml.rels"),
            policy=_XML_POLICY,
        )
        targets = {
            relationship.attrib.get("Id", ""): _relationship_path(
                relationship.attrib.get("Target", "")
            )
            for relationship in relationships.findall(
                f"{{{_PACKAGE_REL}}}Relationship"
            )
            if relationship.attrib.get("Type", "").endswith("/worksheet")
            or relationship.attrib.get("Type") == "worksheet"
        }
        shared_strings = _shared_strings(archive)
        sheets: list[MbsWorkbookSheet] = []
        for sheet in workbook.findall(f".//{{{_MAIN}}}sheet"):
            name = sheet.attrib.get("name", "")
            relationship_id = sheet.attrib.get(f"{{{_OFFICE_REL}}}id", "")
            if not name or relationship_id not in targets:
                raise ValueError("workbook sheet relationship is incomplete")
            sheets.append(
                _sheet(
                    archive,
                    name=name,
                    relationship_id=relationship_id,
                    path=targets[relationship_id],
                    shared_strings=shared_strings,
                )
            )
    if not sheets:
        raise ValueError("workbook contains no sheets")
    return MbsWorkbookBatch(
        schema_era=receipt.source.catalog_version,
        sheets=tuple(sheets),
        provenance=provenance,
    )


def qualify_legacy_p7_workbook(
    payload: bytes,
    receipt: SourceReceipt,
) -> MbsWorkbookBatch:
    """Qualify the exact July 2024 donor workbook and its four sheets."""
    if len(payload) != LEGACY_P7_BYTES or not receipt.payload.matches(payload):
        raise ValueError("payload is not the exact July 2024 P7 workbook")
    if receipt.payload.sha256 != LEGACY_P7_SHA256:
        raise ValueError("payload is not the exact July 2024 P7 workbook")
    batch = parse_mbs_workbook(payload, receipt)
    observed = tuple((sheet.name, sheet.dimension) for sheet in batch.sheets)
    if observed != LEGACY_P7_SHEETS:
        raise ValueError("July 2024 P7 workbook sheet denominator differs")
    return batch
