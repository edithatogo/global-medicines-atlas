"""Bounded native layout discovery for the existing frozen group workbook.

Header candidates are coordinates, not accepted semantic mappings. Only the
first three rows are exposed; body values contribute to a digest and counts.
"""

from __future__ import annotations

import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from zipfile import ZipFile

if TYPE_CHECKING:
    from pydantic import JsonValue

from .archive_safety import inspect_zip
from .bronze_raw_evidence import RawEvidenceManifest
from .mbs_demographic_csv_cohort import (
    FROZEN,
    FROZEN_SHA256,
    STRUCTURE,
    STRUCTURE_SHA256,
)
from .mbs_demographic_extraction import (
    ARCHIVE_POLICY,
    MAX_MEMBER_BYTES,
    MAX_ROW,
    MAX_SOURCE_BYTES,
    WORKSHEET_POLICY,
)
from .mbs_demographic_extraction import (
    decode_native_workbook_cell as _cell,
)
from .mbs_demographic_extraction import (
    read_bounded_workbook_member as _member,
)
from .mbs_demographic_extraction import (
    read_workbook_shared_strings as _shared,
)
from .mbs_demographic_extraction import (
    workbook_cell_position as _position,
)
from .mbs_demographic_extraction import (
    workbook_sheet_targets as _targets,
)
from .mbs_demographic_silver import DemographicSource
from .parser_safety import iter_xml_events
from .receipts import AcquisitionEvent

SOURCE_PATH = "raw/mbs/utilisation/group/mbs-group-2016hr-july.xlsx"
FAMILY = "au-data-gov-mbs-group"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
MAX_HEADER_CELLS = 256
HEADER_CANDIDATE_ROWS = 3


class _GroupBinding(DemographicSource):
    SOURCE_FAMILY: ClassVar[str] = FAMILY

    @property
    def headers(self) -> tuple[str, ...]:
        raise ValueError(
            "group workbook semantic header mapping is unqualified"
        )


def _bound(root: Path, path: str, digest: str) -> dict[str, Any]:
    payload = (root / path).read_bytes()
    if sha256(payload).hexdigest() != digest:
        raise ValueError("group workbook retained metadata digest differs")
    return json.loads(payload)


def load_reference(root: Path) -> dict[str, Any]:
    """Bind structural receipt, frozen membership, original acquisition and B2."""
    report = _bound(root, STRUCTURE, STRUCTURE_SHA256)
    documents = [
        row["document"]
        for row in report["per_object_receipts"]
        if row["document"]["raw_reference"]["path"] == SOURCE_PATH
    ]
    if len(documents) != 1:
        raise ValueError("group workbook requires one structural receipt")
    document = documents[0]
    reference = document["raw_reference"]
    frozen = _bound(root, FROZEN, FROZEN_SHA256)
    if (
        (reference["dataset"], SOURCE_PATH)
        not in {(row["dataset"], row["path"]) for row in frozen["members"]}
        or document["result"]["status"] != "structure_verified"
        or document["result"].get("anonymous_digest_verified") is not True
        or type(reference["byte_count"]) is not int
        or not 0 < reference["byte_count"] <= MAX_SOURCE_BYTES
    ):
        raise ValueError("group workbook frozen structural identity differs")
    acquisition = document["acquisition_id"]
    b1 = (
        root
        / f"quality/bronze/imported-acquisitions/{FAMILY}/{acquisition}.json"
    ).read_bytes()
    b2 = (
        root
        / f"quality/bronze/raw-evidence/{FAMILY}/{acquisition}/manifest.json"
    ).read_bytes()
    source = _GroupBinding(
        acquisition=AcquisitionEvent.model_validate_json(b1),
        raw_manifest=RawEvidenceManifest.model_validate_json(b2),
        dataset=reference["dataset"],
        source_revision=reference["revision"],
        source_path=SOURCE_PATH,
        source_format="workbook",
    )
    retrieval = source.acquisition.retrieval
    if (
        source.source_sha256 != reference["sha256"]
        or retrieval is None
        or retrieval.http is None
        or retrieval.http.observed_byte_length != reference["byte_count"]
    ):
        raise ValueError("group workbook B1/B2 digest or size differs")
    return {
        "path": SOURCE_PATH,
        "dataset": source.dataset,
        "revision": source.source_revision,
        "sha256": source.source_sha256,
        "bytes": reference["byte_count"],
        "source_id": FAMILY,
        "acquisition_id": acquisition,
        "source_object_id": source.object_id,
        "b1_sha256": sha256(b1).hexdigest(),
        "b2_sha256": sha256(b2).hexdigest(),
        "structural_receipt_sha256": STRUCTURE_SHA256,
    }


def _sheet_layout(  # ruff: ignore[too-many-locals] -- bounded native worksheet state machine
    archive: ZipFile,
    descriptor: tuple[str, str, str],
    shared: tuple[str, ...],
    structures: tuple[dict[str, JsonValue], ...],
) -> dict[str, Any]:
    name, path, relationship = descriptor
    previous = rows = cells = formulas = errors = 0
    candidates: list[dict[str, Any]] = []
    inventory = sha256()
    for event, element, parent in iter_xml_events(
        _member(archive, path, MAX_MEMBER_BYTES),
        policy=WORKSHEET_POLICY,
    ):
        if event != "end" or element.tag != f"{{{NS}}}row":
            continue
        text = element.attrib.get("r", "")
        if (
            not text.isascii()
            or not text.isdecimal()
            or not previous < int(text) <= MAX_ROW
        ):
            raise ValueError("group workbook row coordinate differs")
        index = int(text)
        previous = index
        rows += 1
        columns: set[int] = set()
        inventory.update(
            json.dumps(dict(element.attrib), sort_keys=True).encode()
        )
        for native in element.findall(f"{{{NS}}}c"):
            coordinate = native.attrib.get("r", "")
            row, column = _position(coordinate)
            if row != index or column in columns:
                raise ValueError("group workbook cell coordinate differs")
            columns.add(column)
            cell = _cell(
                native,
                name=coordinate,
                shared=shared,
                structures=structures,
                row_attributes=dict(element.attrib),
            )
            inventory.update(cell.model_dump_json().encode())
            cells += 1
            formulas += cell.native_properties["formula_present"] is True
            errors += cell.state == "source_error"
            if index <= HEADER_CANDIDATE_ROWS:
                if len(candidates) >= MAX_HEADER_CELLS:
                    raise ValueError(
                        "group workbook header candidate bound exceeded"
                    )
                candidates.append({
                    "row": index,
                    "column": column,
                    **cell.model_dump(mode="json"),
                })
        if parent is not None:
            parent.remove(element)
        element.clear()
    return {
        "name": name,
        "path": path,
        "relationship_id": relationship,
        "native_rows": rows,
        "native_cells": cells,
        "formula_cells": formulas,
        "source_error_cells": errors,
        "native_inventory_sha256": inventory.hexdigest(),
        "header_candidates": candidates,
    }


def inspect_layout(payload: bytes, reference: dict[str, Any]) -> dict[str, Any]:
    """Exhaust every worksheet and member before reporting native layout."""
    if (
        not 0 < len(payload) <= MAX_SOURCE_BYTES
        or len(payload) != reference["bytes"]
        or sha256(payload).hexdigest() != reference["sha256"]
    ):
        raise ValueError("group workbook payload identity differs")
    inspect_zip(payload, policy=ARCHIVE_POLICY)
    sheets: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []
    with ZipFile(BytesIO(payload)) as archive:
        for entry in archive.infolist():
            if not entry.is_dir():
                content = _member(archive, entry.filename, MAX_MEMBER_BYTES)
                members.append({
                    "path": entry.filename,
                    "bytes": len(content),
                    "sha256": sha256(content).hexdigest(),
                })
        shared, structures = _shared(archive)
        sheets.extend(
            _sheet_layout(archive, descriptor, shared, structures)
            for descriptor in _targets(archive)
        )
    return {
        "schema_version": 1,
        "qualification": "native_layout_candidate_only",
        "source_sha256": reference["sha256"],
        "sheet_count": len(sheets),
        "sheets": sheets,
        "members": members,
        "semantic_roles_assigned": False,
        "new_admissions": 0,
        "publications": 0,
    }
