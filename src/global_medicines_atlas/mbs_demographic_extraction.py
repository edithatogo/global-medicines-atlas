"""Receipt-bound demographic extraction with complete worksheet-cell coverage.

The iterator emits primary records plus ancillary cells and package/sheet
inventories. Callers must exhaust it successfully before committing outputs.
Neither extraction nor a cached formula result qualifies a field's meaning.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Literal
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import] -- bounded parser preflight
    ElementTree as ET,
)
from zipfile import ZipFile

if TYPE_CHECKING:
    from pydantic import JsonValue

from .adapters.au_mbs_workbook import (
    decode_workbook_cell,
    worksheet_relationship_path,
)
from .archive_safety import ArchivePolicy, inspect_zip
from .mbs_demographic_silver import (
    MAX_CELL_CHARS,
    WIDTH,
    DemographicCell,
    DemographicRow,
    DemographicSource,
)
from .parser_safety import ParserPolicy, iter_xml_events, parse_xml

MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 450_000_000
MAX_SHARED_BYTES = 50_000_000
MAX_METADATA_BYTES = 5_000_000
MAX_CSV_RECORDS = 10_000_000
MAX_ROW = 1_048_576
MAX_COLUMN = 16_384
HEADER_ROW = 3
MAX_SHEETS = 32
_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_COORDINATE = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})\Z")
ARCHIVE_POLICY = ArchivePolicy(
    max_archive_bytes=MAX_SOURCE_BYTES,
    max_entries=256,
    max_entry_uncompressed_bytes=MAX_MEMBER_BYTES,
    max_total_uncompressed_bytes=500_000_000,
    max_decompression_ratio=250,
    max_path_depth=8,
)
METADATA_POLICY = ParserPolicy(
    max_bytes=MAX_METADATA_BYTES,
    max_xml_depth=32,
    max_xml_elements=100_000,
    max_xml_text_bytes=MAX_METADATA_BYTES,
)
WORKSHEET_POLICY = ParserPolicy(
    max_bytes=MAX_MEMBER_BYTES,
    max_xml_depth=32,
    max_xml_elements=16_000_000,
    max_xml_text_bytes=200_000_000,
)
SHARED_POLICY = ParserPolicy(
    max_bytes=MAX_SHARED_BYTES,
    max_xml_depth=32,
    max_xml_elements=2_000_000,
    max_xml_text_bytes=MAX_SHARED_BYTES,
)


@dataclass(frozen=True)
class AncillaryCell:
    """A source cell outside the eight-column primary record body."""

    part_path: str
    sheet_name: str | None
    row_index: int
    column_index: int
    coordinate: str
    cell: DemographicCell


@dataclass(frozen=True)
class WorkbookMember:
    """Fingerprint of a fully read and CRC-checked regular ZIP member."""

    path: str
    sha256: str
    byte_count: int


@dataclass(frozen=True)
class WorkbookSheet:
    """Native worksheet identity, dimensions and observed row/cell counts."""

    path: str
    name: str
    relationship_id: str
    dimension: str | None
    native_row_count: int
    native_cell_count: int
    row_inventory_sha256: str


Record = DemographicRow | AncillaryCell | WorkbookMember | WorkbookSheet


def _member(archive: ZipFile, path: str, limit: int) -> bytes:
    try:
        info = archive.getinfo(path)
        if info.file_size > limit:
            raise ValueError("workbook member exceeds parser bound")
        with archive.open(info) as source:
            payload = source.read(limit + 1)
    except KeyError as error:
        raise ValueError("required workbook member is unavailable") from error
    if len(payload) != info.file_size or len(payload) > limit:
        raise ValueError("workbook member length differs")
    return payload


def _structure(element: ET.Element) -> dict[str, JsonValue]:
    attributes: dict[str, JsonValue] = dict(element.attrib)
    children: list[JsonValue] = [
        {"element": _structure(child), "tail": child.tail} for child in element
    ]
    return {
        "tag": element.tag,
        "attributes": attributes,
        "text": element.text,
        "children": children,
    }


def _shared(
    archive: ZipFile,
) -> tuple[tuple[str, ...], tuple[dict[str, JsonValue], ...]]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return (), ()
    values: list[str] = []
    structures: list[dict[str, JsonValue]] = []
    payload = _member(archive, "xl/sharedStrings.xml", MAX_SHARED_BYTES)
    for event, element, parent in iter_xml_events(
        payload, policy=SHARED_POLICY
    ):
        if event == "end" and element.tag == f"{{{_MAIN}}}si":
            texts: list[str] = []
            for child in element:
                if child.tag == f"{{{_MAIN}}}t":
                    texts.append(child.text or "")
                elif child.tag == f"{{{_MAIN}}}r":
                    texts.extend(
                        part.text or ""
                        for part in child.findall(f"{{{_MAIN}}}t")
                    )
            values.append("".join(texts))
            structures.append(_structure(element))
            if parent is not None:
                parent.remove(element)
            element.clear()
    return tuple(values), tuple(structures)


def _targets(archive: ZipFile) -> tuple[tuple[str, str, str], ...]:
    root = parse_xml(
        _member(archive, "xl/workbook.xml", MAX_METADATA_BYTES),
        policy=METADATA_POLICY,
    )
    relationships = parse_xml(
        _member(archive, "xl/_rels/workbook.xml.rels", MAX_METADATA_BYTES),
        policy=METADATA_POLICY,
    )
    ids: set[str] = set()
    targets: dict[str, str] = {}
    for relation in relationships.findall(f"{{{_PKG}}}Relationship"):
        identifier = relation.attrib.get("Id", "")
        if not identifier or identifier in ids:
            raise ValueError(
                "workbook relationship identity is missing or duplicated"
            )
        ids.add(identifier)
        if not relation.attrib.get("Type", "").endswith("/worksheet"):
            continue
        if relation.attrib.get("TargetMode") == "External":
            raise ValueError("external worksheet relationship is unsupported")
        target = relation.attrib.get("Target", "")
        if target.startswith("/"):
            if not target.startswith("/xl/worksheets/"):
                raise ValueError(
                    "workbook relationship escapes worksheet package"
                )
            target = target[1:]
        targets[identifier] = worksheet_relationship_path(target)
    sheets: list[tuple[str, str, str]] = []
    names: set[str] = set()
    paths: set[str] = set()
    for sheet in root.findall(f"{{{_MAIN}}}sheets/{{{_MAIN}}}sheet"):
        identifier = sheet.attrib.get(f"{{{_REL}}}id", "")
        name = sheet.attrib.get("name", "")
        path = targets.get(identifier)
        if not name or path is None or name in names or path in paths:
            raise ValueError(
                "workbook worksheet identity is incomplete or ambiguous"
            )
        names.add(name)
        paths.add(path)
        sheets.append((name, path, identifier))
    if not sheets or len(sheets) > MAX_SHEETS:
        raise ValueError("workbook worksheet count is unsupported")
    return tuple(sheets)


def _position(coordinate: str) -> tuple[int, int]:
    match = _COORDINATE.fullmatch(coordinate)
    if match is None:
        raise ValueError("workbook cell coordinate is invalid")
    column = 0
    for letter in match[1]:
        column = column * 26 + ord(letter) - ord("A") + 1
    row = int(match[2])
    if column > MAX_COLUMN or row > MAX_ROW:
        raise ValueError("workbook cell coordinate exceeds native bounds")
    return row, column


def _cell(
    element: ET.Element,
    *,
    name: str,
    shared: tuple[str, ...],
    structures: tuple[dict[str, JsonValue], ...],
    row_attributes: dict[str, str],
) -> DemographicCell:
    decoded = decode_workbook_cell(element, shared)
    if (
        decoded.display_value is not None
        and len(decoded.display_value) > MAX_CELL_CHARS
    ):
        raise ValueError("workbook cell value exceeds native field bound")
    formula = element.find(f"{{{_MAIN}}}f")
    properties: dict[str, JsonValue] = {
        "cell_type": decoded.cell_type,
        "raw_value": decoded.raw_value,
        "formula_present": formula is not None,
        "formula": decoded.formula,
        "formula_attributes": dict(formula.attrib)
        if formula is not None
        else None,
        "cell_structure": _structure(element),
        "row_attributes": dict(row_attributes),
    }
    if decoded.cell_type == "s" and decoded.raw_value is not None:
        properties["shared_string_structure"] = structures[
            int(decoded.raw_value)
        ]
    state: Literal["null", "source_error", "value"] = (
        "null"
        if decoded.display_value is None
        else "source_error"
        if decoded.cell_type == "e"
        else "value"
    )
    if decoded.cell_type == "e" and decoded.display_value is None:
        raise ValueError("workbook error cell has no source error code")
    return DemographicCell(
        name=name,
        state=state,
        value=decoded.display_value,
        native_properties=properties,
    )


def _worksheet(  # ruff: ignore[too-many-branches, too-many-locals] -- one bounded streaming row state machine
    archive: ZipFile,
    source: DemographicSource,
    descriptor: tuple[str, str, str],
    shared: tuple[str, ...],
    structures: tuple[dict[str, JsonValue], ...],
    *,
    primary: bool,
) -> Iterator[Record]:
    name, path, relationship = descriptor
    payload = _member(archive, path, MAX_MEMBER_BYTES)
    dimension: str | None = None
    previous = rows = cells = 0
    header_seen = False
    inventory = sha256()
    for event, element, parent in iter_xml_events(
        payload, policy=WORKSHEET_POLICY
    ):
        if event != "end":
            continue
        if element.tag == f"{{{_MAIN}}}dimension":
            dimension = element.attrib.get("ref")
        if element.tag != f"{{{_MAIN}}}row":
            continue
        index_text = element.attrib.get("r", "")
        if not index_text.isascii() or not index_text.isdecimal():
            raise ValueError("worksheet row index is missing or invalid")
        index = int(index_text)
        if not previous < index <= MAX_ROW:
            raise ValueError("worksheet row order or bounds differ")
        previous = index
        rows += 1
        inventory.update(f"{index}:".encode())
        inventory.update(
            json.dumps(
                dict(element.attrib), sort_keys=True, separators=(",", ":")
            ).encode()
        )
        decoded: dict[int, DemographicCell] = {}
        coordinates: dict[int, str] = {}
        for native in element.findall(f"{{{_MAIN}}}c"):
            coordinate = native.attrib.get("r", "")
            cell_row, column = _position(coordinate)
            if cell_row != index or column in decoded:
                raise ValueError("worksheet cell/row identity is inconsistent")
            field_name = (
                source.headers[column - 1]
                if primary and index > HEADER_ROW and column <= WIDTH
                else coordinate
            )
            decoded[column] = _cell(
                native,
                name=field_name,
                shared=shared,
                structures=structures,
                row_attributes=dict(element.attrib),
            )
            coordinates[column] = coordinate
            cells += 1
        if primary and index == HEADER_ROW:
            observed = tuple(
                decoded[column].value if column in decoded else None
                for column in range(1, WIDTH + 1)
            )
            if observed != source.headers or any(
                decoded[column].state != "value"
                for column in range(1, WIDTH + 1)
            ):
                raise ValueError(
                    "workbook primary header differs from reviewed shape"
                )
            header_seen = True
        if primary and index > HEADER_ROW:
            if not header_seen:
                raise ValueError("workbook primary header is unavailable")
            yield DemographicRow(
                row_index=index,
                cells=tuple(
                    decoded.get(column)
                    or DemographicCell(
                        name=source.headers[column - 1],
                        state="absent",
                        value=None,
                        native_properties={
                            "row_attributes": dict(element.attrib)
                        },
                    )
                    for column in range(1, WIDTH + 1)
                ),
            )
        for column, value in decoded.items():
            if not primary or index <= HEADER_ROW or column > WIDTH:
                coordinate = coordinates[column]
                yield AncillaryCell(
                    path, name, index, column, coordinate, value
                )
        if parent is not None:
            parent.remove(element)
        element.clear()
    if primary and not header_seen:
        raise ValueError("workbook primary header is unavailable")
    yield WorkbookSheet(
        path, name, relationship, dimension, rows, cells, inventory.hexdigest()
    )


def _workbook(payload: bytes, source: DemographicSource) -> Iterator[Record]:
    inspect_zip(payload, policy=ARCHIVE_POLICY)
    with ZipFile(io.BytesIO(payload)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            digest, size = sha256(), 0
            with archive.open(info) as stream:
                while block := stream.read(ARCHIVE_POLICY.chunk_bytes):
                    digest.update(block)
                    size += len(block)
            if size != info.file_size:
                raise ValueError("workbook member size differs from directory")
            yield WorkbookMember(info.filename, digest.hexdigest(), size)
        descriptors = _targets(archive)
        shared, structures = _shared(archive)
        for index, descriptor in enumerate(descriptors):
            yield from _worksheet(
                archive,
                source,
                descriptor,
                shared,
                structures,
                primary=index == 0,
            )


def _csv_records(payload: bytes, source: DemographicSource) -> Iterator[Record]:
    with io.TextIOWrapper(
        io.BytesIO(payload), encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, None)
        if header is None or tuple(header) != source.headers:
            raise ValueError("CSV header differs from reviewed shape")
        for column, value in enumerate(header, 1):
            yield AncillaryCell(
                source.source_path,
                None,
                1,
                column,
                f"field:{column}",
                DemographicCell(
                    name=value,
                    state="value",
                    value=value,
                    native_properties={"csv_record": 1, "column": column},
                ),
            )
        for index, values in enumerate(reader, 2):
            if index > MAX_CSV_RECORDS or len(values) != WIDTH:
                raise ValueError("CSV record shape or bound differs")
            if any(len(value) > MAX_CELL_CHARS for value in values):
                raise ValueError("CSV value exceeds native field bound")
            yield DemographicRow(
                row_index=index,
                cells=tuple(
                    DemographicCell(
                        name=name,
                        state="value",
                        value=value,
                        native_properties={
                            "csv_record": index,
                            "column": column,
                            "physical_line_end": reader.line_num,
                        },
                    )
                    for column, (name, value) in enumerate(
                        zip(source.headers, values, strict=True), 1
                    )
                ),
            )


def _csv(payload: bytes, source: DemographicSource) -> Iterator[Record]:
    try:
        yield from _csv_records(payload, source)
    except (UnicodeError, csv.Error) as error:
        raise ValueError(
            "CSV cannot be decoded using the reviewed grammar"
        ) from error


def iter_demographic_records(
    payload: bytes, source: DemographicSource
) -> Iterator[Record]:
    """Verify immutable identity before emitting any primary or ancillary data."""
    source = DemographicSource.model_validate(source.model_dump())
    if (
        not isinstance(payload, bytes)  # pyright: ignore[reportUnnecessaryIsInstance] -- runtime public boundary
        or not 0 < len(payload) <= MAX_SOURCE_BYTES
        or sha256(payload).hexdigest() != source.source_sha256
    ):
        raise ValueError(
            "demographic payload identity or resource bound differs"
        )
    if source.source_format == "csv":
        yield from _csv(payload, source)
    else:
        yield from _workbook(payload, source)
