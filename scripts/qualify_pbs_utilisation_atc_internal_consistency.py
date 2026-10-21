#!/usr/bin/env python3
"""Compare ATC-shaped fields across two already inventoried PBS objects.

This aggregate-only screen checks internal cross-file consistency. It does
not establish ATC vocabulary membership, rights, source semantics, or release
eligibility. Source payloads stay in memory and only exact pinned objects are
parsed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import urllib.parse
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.parser_safety import ParserPolicy, iter_xml_events

ROOT = Path(__file__).resolve().parents[1]
DATASET = "edithatogo/australian-pbs-utilisation-archive"
REVISION = "9f1d53cd50eea251b326da42a96f3ac72ebce97a"
OUTPUT = Path(
    "quality/qualifications/"
    "australian-pbs-utilisation-atc-internal-consistency-20261021.json"
)
MAX_OBJECT_BYTES = 125_000_000
MAX_SHARED_STRINGS_XML_BYTES = 120_000_000
MAX_WORKSHEET_XML_BYTES = 900_000_000
MAX_XML_ELEMENTS = 30_000_000
MAX_XML_TEXT_BYTES = 750_000_000
ATC_PATTERN = re.compile(r"^[A-Z]\d{2}[A-Z]{2}\d{2}$")
EXPECTED_SUMMARY_SHEETS = (
    "DOS_FY2021_22",
    "DOS_FY2022_23",
    "DOS_FY2023_24",
    "DOS_FY2024_25",
    "DOS_FY2025_26",
)
SUMMARY_HEADER_SHA256 = (
    "20f9f06f6a7ddb3b7b96622cd4c29704ac436e71860946a02dff60152ae524ad"
)
OBJECTS = (
    {
        "path": "raw/pbs/utilisation/reference/pbs-item-drug-map.csv",
        "bytes": 1_063_694,
        "sha256": "51adf3c80df2c2d526bfe88d2d96199e545579ced1b32e7ba3550dfc15f358a8",
    },
    {
        "path": "raw/pbs/utilisation/summary/dos-jul-2021-to-jun-2026.xlsx",
        "bytes": 117_376_499,
        "sha256": "48678536ddb71f9e7e4e6d654a0a90e6b242c22105e6864af1c6ef47318980ca",
    },
)


def _fetch_exact(client: httpx.Client, item: dict[str, Any]) -> bytes:
    path = cast("str", item["path"])
    url = (
        f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
        f"{urllib.parse.quote(path, safe='/')}?download=true"
    )
    chunks: list[bytes] = []
    count = 0
    with client.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            count += len(chunk)
            if count > MAX_OBJECT_BYTES:
                raise ValueError("Pinned PBS object exceeds its byte bound")
            chunks.append(chunk)
    payload = b"".join(chunks)
    if (
        count != item["bytes"]
        or hashlib.sha256(payload).hexdigest() != item["sha256"]
    ):
        raise ValueError("Pinned PBS identity mismatch; parsing stopped")
    return payload


def _normalize_code(value: str) -> str:
    return value.strip().upper()


def _code_set_summary(values: Iterable[str]) -> dict[str, Any]:
    exact: set[str] = set()
    shaped: set[str] = set()
    nonempty_count = 0
    shape_count = 0
    for raw in values:
        value = _normalize_code(raw)
        if not value:
            continue
        nonempty_count += 1
        exact.add(value)
        if ATC_PATTERN.fullmatch(value):
            shaped.add(value)
            shape_count += 1
    return {
        "nonempty_occurrences": nonempty_count,
        "distinct_nonempty_values": len(exact),
        "atc_shaped_occurrences": shape_count,
        "distinct_atc_shaped_values": len(shaped),
        "distinct_atc_set_sha256": hashlib.sha256(
            "\n".join(sorted(shaped)).encode("ascii")
        ).hexdigest(),
        "_all_values": exact,
        "_atc_values": shaped,
    }


def compare_code_sets(
    map_summary: dict[str, Any], summary_summary: dict[str, Any]
) -> dict[str, Any]:
    map_codes = cast("set[str]", map_summary["_atc_values"])
    summary_codes = cast("set[str]", summary_summary["_atc_values"])
    shared = map_codes & summary_codes
    return {
        "item_map_distinct_atc_shaped_values": len(map_codes),
        "summary_distinct_atc_shaped_values": len(summary_codes),
        "distinct_values_in_both": len(shared),
        "item_map_values_also_in_summary": len(map_codes & summary_codes),
        "item_map_values_absent_from_summary": len(map_codes - summary_codes),
        "summary_values_absent_from_item_map": len(summary_codes - map_codes),
        "sets_equal": map_codes == summary_codes,
        "shared_set_sha256": hashlib.sha256(
            "\n".join(sorted(shared)).encode("ascii")
        ).hexdigest(),
    }


def _csv_atc_values(payload: bytes) -> dict[str, Any]:
    with io.TextIOWrapper(
        io.BytesIO(payload), encoding="latin-1", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or "ATC5_Code" not in reader.fieldnames:
            raise ValueError("Pinned item map no longer has ATC5_Code")
        return _code_set_summary(
            row.get("ATC5_Code", "") or "" for row in reader
        )


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    info = archive.getinfo("xl/sharedStrings.xml")
    if info.file_size > MAX_SHARED_STRINGS_XML_BYTES:
        raise ValueError("PBS summary shared strings exceed the byte bound")
    with archive.open(info) as stream:
        payload = stream.read(MAX_SHARED_STRINGS_XML_BYTES + 1)
    if len(payload) != info.file_size:
        raise ValueError("PBS summary shared strings size mismatch")
    policy = ParserPolicy(
        max_bytes=MAX_SHARED_STRINGS_XML_BYTES,
        max_xml_depth=16,
        max_xml_elements=8_000_000,
        max_xml_text_bytes=MAX_SHARED_STRINGS_XML_BYTES,
    )
    values: list[str] = []
    for event, element, parent in iter_xml_events(payload, policy=policy):
        if event == "end" and element.tag.endswith("}si"):
            values.append(
                "".join(
                    child.text or ""
                    for child in element.iter()
                    if child.tag.endswith("}t")
                )
            )
            if parent is not None:
                parent.remove(element)
            element.clear()
    return values


def _sheet_codes(
    archive: zipfile.ZipFile, sheet_index: int, shared: list[str]
) -> tuple[list[str], str]:
    name = f"xl/worksheets/sheet{sheet_index + 1}.xml"
    info = archive.getinfo(name)
    if info.file_size > MAX_WORKSHEET_XML_BYTES:
        raise ValueError("PBS summary worksheet exceeds the byte bound")
    with archive.open(info) as stream:
        payload = stream.read(MAX_WORKSHEET_XML_BYTES + 1)
    if len(payload) != info.file_size:
        raise ValueError("PBS summary worksheet size mismatch")
    policy = ParserPolicy(
        max_bytes=MAX_WORKSHEET_XML_BYTES,
        max_xml_depth=16,
        max_xml_elements=MAX_XML_ELEMENTS,
        max_xml_text_bytes=MAX_XML_TEXT_BYTES,
    )
    values: list[str] = []
    header_digest: str | None = None
    for event, row, parent in iter_xml_events(payload, policy=policy):
        if event != "end" or not row.tag.endswith("}row"):
            continue
        for cell in row:
            if not cell.tag.endswith("}c") or not cell.attrib.get(
                "r", ""
            ).startswith("C"):
                continue
            value = cell.find("{*}v")
            if value is None or value.text is None:
                continue
            text = (
                shared[int(value.text)]
                if cell.attrib.get("t") == "s"
                else value.text
            )
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest == SUMMARY_HEADER_SHA256:
                header_digest = digest
                continue
            normalized = _normalize_code(text)
            if ATC_PATTERN.fullmatch(normalized):
                values.append(normalized)
        if parent is not None:
            parent.remove(row)
        row.clear()
    if header_digest is None:
        raise ValueError("Expected ATC5_CODE header digest was not found")
    return values, header_digest


def _xlsx_atc_values(payload: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        shared = _shared_strings(archive)
        all_values: list[str] = []
        verified_headers = 0
        for index in range(len(EXPECTED_SUMMARY_SHEETS)):
            values, _ = _sheet_codes(archive, index, shared)
            all_values.extend(values)
            verified_headers += 1
    result = _code_set_summary(all_values)
    result["verified_atc_header_count"] = verified_headers
    result["expected_atc_header_count"] = len(EXPECTED_SUMMARY_SHEETS)
    return result


def qualify() -> dict[str, Any]:
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=180,
        max_bytes=MAX_OBJECT_BYTES,
        max_attempts=1,
        max_redirects=3,
    )
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(180),
        trust_env=False,
        max_redirects=policy.max_redirects,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        map_payload = _fetch_exact(client, OBJECTS[0])
        summary_payload = _fetch_exact(client, OBJECTS[1])
    map_result = _csv_atc_values(map_payload)
    summary_result = _xlsx_atc_values(summary_payload)
    comparison = compare_code_sets(map_result, summary_result)
    for result in (map_result, summary_result):
        result.pop("_all_values")
        result.pop("_atc_values")
    return {
        "schema_id": "global-medicines-atlas.pbs-utilisation-atc-internal-consistency",
        "schema_version": 1,
        "dataset": DATASET,
        "revision": REVISION,
        "objects": [
            {
                "path": item["path"],
                "bytes": item["bytes"],
                "sha256": item["sha256"],
            }
            for item in OBJECTS
        ],
        "method": {
            "fields": ["ATC5_Code", "ATC5_CODE"],
            "summary_sheets": list(EXPECTED_SUMMARY_SHEETS),
            "field_header_evidence": (
                "quality/qualifications/australian-pbs-utilisation-summary-workbook-header-resolution-20261021.json"
            ),
            "comparison": "Trim and uppercase, then compare distinct values matching the already-qualified seven-character ATC-like shape; output counts and digests only.",
            "vocabulary_membership_tested": False,
        },
        "results": {
            "item_map": map_result,
            "summary_workbook": summary_result,
            "cross_file": comparison,
        },
        "interpretation": (
            "Agreement between two fields in the existing PBS inventory is "
            "internal consistency evidence only. It does not verify WHO ATC "
            "membership, licensing, field semantics, or relationship validity."
        ),
        "boundaries": {
            "new_sources_added": False,
            "source_bytes_persisted": False,
            "source_values_emitted_or_retained": False,
            "rights_or_vocabulary_conclusion_changed": False,
            "v4_admission_or_canary_performed": False,
            "public_dataset_mutated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = (
        json.dumps(qualify(), sort_keys=True, separators=(",", ":")) + "\n"
    )
    output = args.output.expanduser()
    if args.check:
        if (
            not output.is_file()
            or output.read_text(encoding="utf-8") != encoded
        ):
            raise SystemExit(f"PBS ATC consistency report is stale: {output}")
        print("PBS ATC internal-consistency report passed")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8")
    print(
        f"wrote {output} sha256={hashlib.sha256(encoded.encode()).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
