"""Exact frozen workbook cells and physical row metadata without domain claims.

Source-specific headers, eras, numeric units and dates remain unqualified.
Native values stay in the private extraction stream; public reports must contain
only bounded counts and digests. Exhaustion is required before accepting output.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .archive_safety import inspect_zip
from .mbs_demographic_extraction import (
    ARCHIVE_POLICY,
    MAX_MEMBER_BYTES,
    MAX_ROW,
    WORKSHEET_POLICY,
    decode_native_workbook_cell,
    read_bounded_workbook_member,
    read_workbook_shared_strings,
    workbook_cell_position,
    workbook_sheet_targets,
)
from .mbs_historical_csv_package import FrozenMbsMember
from .parser_safety import iter_xml_events

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
MAX_RECORD_BYTES = 8 * 1024 * 1024
MAX_PATH_BYTES = 1024 * 1024


def _payload(path: Path, member: FrozenMbsMember, native: str) -> bytes:
    if (
        member.suffix != ".xlsx"
        or type(member.byte_count) is not int
        or not 0 < member.byte_count <= ARCHIVE_POLICY.max_archive_bytes
    ):
        raise ValueError("historical workbook format or byte bound differs")
    if (
        len(native.encode()) > MAX_PATH_BYTES
        or sha256(native.encode()).hexdigest() != member.path_sha256
    ):
        raise ValueError("historical workbook path identity differs")
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size != member.byte_count
    ):
        raise ValueError(
            "historical workbook format, path or byte bound differs"
        )
    payload = path.read_bytes()
    if (
        len(payload) != member.byte_count
        or sha256(payload).hexdigest() != member.sha256
    ):
        raise ValueError("historical workbook member identity differs")
    inspect_zip(payload, policy=ARCHIVE_POLICY)
    return payload


def _bounded(record: dict[str, Any]) -> dict[str, Any]:
    if (
        len(
            json.dumps(
                record, ensure_ascii=False, separators=(",", ":")
            ).encode()
        )
        > MAX_RECORD_BYTES
    ):
        raise ValueError("historical workbook native record byte bound differs")
    return record


def iter_workbook_records(  # ruff: ignore[too-many-branches, too-many-locals] -- one bounded worksheet event state machine
    path: Path, member: FrozenMbsMember, native_path: str
) -> Iterator[dict[str, Any]]:
    """Yield all physical cells, rows, sheet counts and package fingerprints.

    Bind the member to its original archive occurrence without inventing a
    stand-alone acquisition receipt. Reuse finite ZIP/XML/string/cell limits.
    Empty rows and empty sheets remain visible; no missing cells are invented.
    Formula attributes, cached/raw/display values and rich-string structures
    are retained by the existing shared decoder. Nothing executes formulas.
    """
    payload = _payload(Path(path), member, native_path)
    with ZipFile(io.BytesIO(payload)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            digest = sha256()
            count = 0
            with archive.open(info) as stream:
                while block := stream.read(ARCHIVE_POLICY.chunk_bytes):
                    digest.update(block)
                    count += len(block)
            if count != info.file_size:
                raise ValueError(
                    "historical workbook package member length differs"
                )
            yield _bounded({
                "kind": "member",
                "path": info.filename,
                "sha256": digest.hexdigest(),
                "byte_count": count,
            })
        shared, structures = read_workbook_shared_strings(archive)
        for name, sheet_path, relationship in workbook_sheet_targets(archive):
            sheet = read_bounded_workbook_member(
                archive, sheet_path, MAX_MEMBER_BYTES
            )
            previous = rows = cells = 0
            dimension = None
            common = {
                "sheet_name": name,
                "sheet_path": sheet_path,
                "sheet_relationship_id": relationship,
            }
            for event, element, parent in iter_xml_events(
                sheet, policy=WORKSHEET_POLICY
            ):
                if (
                    event == "start"
                    and parent is None
                    and element.tag != f"{{{MAIN}}}worksheet"
                ):
                    raise ValueError(
                        "historical workbook worksheet root differs"
                    )
                if event != "end":
                    continue
                if element.tag == f"{{{MAIN}}}dimension":
                    dimension = element.attrib.get("ref")
                if element.tag != f"{{{MAIN}}}row":
                    continue
                if parent is None or parent.tag != f"{{{MAIN}}}sheetData":
                    raise ValueError("historical workbook row parent differs")
                index = element.attrib.get("r", "")
                if (
                    not index.isascii()
                    or not index.isdecimal()
                    or not previous < int(index) <= MAX_ROW
                ):
                    raise ValueError("historical workbook row identity differs")
                previous = int(index)
                rows += 1
                positions: set[int] = set()
                for cell in element.findall(f"{{{MAIN}}}c"):
                    coordinate = cell.attrib.get("r", "")
                    row, column = workbook_cell_position(coordinate)
                    if row != previous or column in positions:
                        raise ValueError(
                            "historical workbook cell identity differs"
                        )
                    positions.add(column)
                    decoded = decode_native_workbook_cell(
                        cell,
                        name=coordinate,
                        shared=shared,
                        structures=structures,
                        row_attributes=dict(element.attrib),
                    )
                    cells += 1
                    yield _bounded({
                        "kind": "cell",
                        **common,
                        "row_index": row,
                        "column_index": column,
                        "coordinate": coordinate,
                        "cell": decoded.model_dump(mode="json"),
                    })
                yield _bounded({
                    "kind": "row",
                    **common,
                    "row_index": previous,
                    "attributes": dict(element.attrib),
                    "cell_count": len(positions),
                })
                parent.remove(element)
                element.clear()
            yield {
                "kind": "sheet",
                **common,
                "dimension": dimension,
                "native_row_count": rows,
                "native_cell_count": cells,
                "semantics_qualified": False,
            }
    yield {"kind": "binding", "member_binding": asdict(member)}
