"""Classify vocabulary-marker context in two pinned PBS expenditure workbooks.

The screen reads the exact already-approved objects directly into memory,
checks their pinned identities, and emits aggregate cell counts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS

ROOT = Path(__file__).resolve().parents[1]
REVISION = "9f1d53cd50eea251b326da42a96f3ac72ebce97a"
DATASET = "edithatogo/australian-pbs-utilisation-archive"
OUTPUT = Path(
    "quality/qualifications/"
    "australian-pbs-expenditure-marker-context-screen-20261021.json"
)
NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
MARKER = re.compile(
    r"(?i)\b(?:AMT|SNOMED(?:\s+CT)?|RxNorm|RxCUI|ATC)\b|\bC\d{7}\b"
)
ATC_CODE = re.compile(r"(?i)\b[A-Z]\d{2}[A-Z]{2}\d{2}\b")
OBJECTS = (
    {
        "path": (
            "raw/pbs/expenditure/"
            "Expenditure-prescriptions-report-tables-2023-24.XLSX"
        ),
        "sha256": "32ea64558d43531fed4bb395787bbc9279fdf45a2ddc6481ce8234aac676306b",
        "byte_count": 372149,
    },
    {
        "path": (
            "raw/pbs/expenditure/"
            "Expenditure-prescriptions-report-tables-2024-25.XLSX"
        ),
        "sha256": "147f4c5392e256d85beb3e47dfd8445085e5a8f0ecbbd330b535774d81aadf99",
        "byte_count": 468764,
    },
)


def _workbook_text_cells(payload: bytes) -> list[tuple[str, list[str]]]:
    """Return sheet titles and text cells from an in-memory XLSX payload."""
    with zipfile.ZipFile(BytesIO(payload)) as workbook:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            shared_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(text.text or "" for text in item.findall(".//a:t", NS))
                for item in shared_root.findall("a:si", NS)
            ]

        book = ET.fromstring(workbook.read("xl/workbook.xml"))
        relationships = ET.fromstring(
            workbook.read("xl/_rels/workbook.xml.rels")
        )
        targets = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships.findall("rel:Relationship", NS)
        }
        results: list[tuple[str, list[str]]] = []
        for sheet in book.findall("a:sheets/a:sheet", NS):
            relationship_id = sheet.attrib[f"{{{NS['r']}}}id"]
            target = targets[relationship_id]
            member = (
                target.lstrip("/")
                if target.startswith("/")
                else posixpath.normpath(posixpath.join("xl", target))
            )
            root = ET.fromstring(workbook.read(member))
            cells: list[str] = []
            for cell in root.findall(".//a:c", NS):
                kind = cell.attrib.get("t")
                if kind == "s":
                    value = cell.find("a:v", NS)
                    if value is not None and value.text is not None:
                        cells.append(shared_strings[int(value.text)])
                elif kind == "inlineStr":
                    cells.append(
                        "".join(text.text or "" for text in cell.findall(".//a:t", NS))
                    )
                elif kind == "str":
                    value = cell.find("a:v", NS)
                    if value is not None and value.text is not None:
                        cells.append(value.text)
            results.append((sheet.attrib["name"], cells))
        return results


def _screen_object(payload: bytes, expected: dict[str, Any]) -> dict[str, Any]:
    actual_digest = hashlib.sha256(payload).hexdigest()
    if len(payload) != expected["byte_count"] or actual_digest != expected["sha256"]:
        raise ValueError(f"pinned identity mismatch for {expected['path']}")

    sheets: list[dict[str, Any]] = []
    for title, cells in _workbook_text_cells(payload):
        marker_counts: Counter[str] = Counter()
        marker_cells = 0
        context_cells = 0
        marker_only_cells = 0
        atc_code_cells = 0
        for text in cells:
            if ATC_CODE.search(text):
                atc_code_cells += 1
            matches = [match.group(0).upper() for match in MARKER.finditer(text)]
            if not matches:
                continue
            marker_cells += 1
            marker_counts.update(matches)
            if MARKER.fullmatch(text.strip()):
                marker_only_cells += 1
            else:
                context_cells += 1
        if marker_cells or atc_code_cells:
            sheets.append(
                {
                    "sheet": title,
                    "marker_cells": marker_cells,
                    "marker_counts": dict(sorted(marker_counts.items())),
                    "marker_only_cells": marker_only_cells,
                    "context_text_cells": context_cells,
                    "atc_code_shape_cells": atc_code_cells,
                }
            )
    return {
        **expected,
        "sheets_with_markers": sheets,
        "marker_cell_count": sum(sheet["marker_cells"] for sheet in sheets),
        "marker_only_cell_count": sum(
            sheet["marker_only_cells"] for sheet in sheets
        ),
        "context_text_cell_count": sum(
            sheet["context_text_cells"] for sheet in sheets
        ),
        "atc_code_shape_cell_count": sum(
            sheet["atc_code_shape_cells"] for sheet in sheets
        ),
    }


def qualify(*, root: Path = ROOT) -> dict[str, Any]:
    """Fetch and screen the two exact hosted objects without local persistence."""
    policy = AcquisitionPolicy(
        allowed_hosts=tuple(sorted(set(HOSTS) | {"huggingface.co"})),
        max_bytes=500_000,
        timeout_seconds=30,
        max_attempts=1,
        max_redirects=3,
    )
    results = []
    with httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        follow_redirects=True,
        timeout=30,
        trust_env=False,
    ) as client:
        for expected in OBJECTS:
            url = (
                f"https://huggingface.co/datasets/{DATASET}/resolve/"
                f"{REVISION}/{expected['path']}"
            )
            response = client.get(url)
            response.raise_for_status()
            results.append(_screen_object(response.content, expected))

    return {
        "schema_id": "global-medicines-atlas.pbs-expenditure-marker-context-screen",
        "schema_version": 1,
        "dataset": DATASET,
        "revision": REVISION,
        "scope": {
            "object_count": len(OBJECTS),
            "marker_pattern": (
                "AMT, SNOMED CT, RxNorm, RxCUI, ATC, and UMLS CUI text forms"
            ),
        },
        "method": {
            "format": (
                "XLSX shared-string, inline-string, and string cells parsed "
                "from memory"
            ),
            "identity_verified_before_screen": True,
            "marker_only_means_exact_textual_marker_not_identifier_membership": True,
            "source_values_emitted": False,
            "source_bytes_persisted_locally": False,
        },
        "objects": results,
        "interpretation": (
            "The detected ATC mentions occur in text cells classified as labels "
            "or context; an ATC-shaped identifier scan is reported separately. "
            "This does not resolve "
            "vocabulary rights, all workbook content, admission, or release."
        ),
        "boundaries": {
            "new_sources_added": False,
            "source_bytes_persisted_locally": False,
            "source_values_emitted": False,
            "admission_performed": False,
            "consumer_canary_performed": False,
            "public_dataset_mutated": False,
            "rights_or_release_conclusion_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = qualify(root=args.root.resolve())
    output = args.root / args.output
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != serialized:
            raise SystemExit("PBS expenditure marker-context report is stale")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "passed",
                "objects": len(result["objects"]),
                "report": args.output.as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
