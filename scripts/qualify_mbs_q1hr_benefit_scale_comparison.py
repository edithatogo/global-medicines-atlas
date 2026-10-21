#!/usr/bin/env python3
"""Compare Q1 HR and CSV benefit values for a small fixed-scale set.

This is an aggregate-only diagnostic over two exact existing MBS objects. It
keeps payloads in memory, verifies their pinned identities before parsing, and
does not infer semantic equivalence or retain source values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import urllib.parse
import zipfile
from decimal import Decimal, InvalidOperation
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
OUTPUT = Path(
    "quality/qualifications/"
    "australian-mbs-demographics-q1hr-benefit-scale-comparison-20261021.json"
)
REVISION = "dee9a5b0580dfe394474dc26b372559462e157e7"
DATASET = "edithatogo/australian-mbs-utilisation-archive"
MAX_OBJECT_BYTES = 25_000_000
MAX_SHARED_STRINGS_XML_BYTES = 50_000_000
MAX_WORKSHEET_XML_BYTES = 450_000_000
FIRST_DATA_ROW = 4
EXPECTED_WORKBOOK_ROWS = 545_074
EXPECTED_CSV_ROWS = 545_070
OBJECTS = (
    {
        "path": "raw/mbs/utilisation/demographics/"
        "mbs-demographics-2016-qtr1-marchhr.xlsx",
        "bytes": 21_966_140,
        "sha256": "d44522cbd1847e73ee69cb5374c207296133254cd82be61e751f78db1a456d4d",
    },
    {
        "path": "raw/mbs/utilisation/demographics/"
        "mbs-demographics-2016-qtr-1-march.csv",
        "bytes": 23_934_884,
        "sha256": "e4c7b972587aeb96c905a737ccf7f0d5167c8d8e2edd805ce015487d4bd896a5",
    },
)
SCALE_FACTORS = {
    "1": Decimal(1),
    "0.001": Decimal("0.001"),
    "0.01": Decimal("0.01"),
    "0.1": Decimal("0.1"),
    "10": Decimal(10),
    "100": Decimal(100),
    "1000": Decimal(1000),
    "100000": Decimal(100000),
    "1/100000": Decimal("0.00001"),
}


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
                raise ValueError(
                    "Pinned object exceeded the in-memory byte limit"
                )
            chunks.append(chunk)
    payload = b"".join(chunks)
    if (
        count != item["bytes"]
        or hashlib.sha256(payload).hexdigest() != item["sha256"]
    ):
        raise ValueError("Pinned object identity mismatch; parsing stopped")
    return payload


def _xml_member(archive: zipfile.ZipFile, name: str, limit: int) -> bytes:
    info = archive.getinfo(name)
    if info.file_size > limit:
        raise ValueError("Pinned workbook XML member exceeds its byte limit")
    with archive.open(info) as source:
        payload = source.read(limit + 1)
    if len(payload) != info.file_size or len(payload) > limit:
        raise ValueError("Pinned workbook XML member size differs")
    return payload


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    values: list[str] = []
    payload = _xml_member(
        archive, "xl/sharedStrings.xml", MAX_SHARED_STRINGS_XML_BYTES
    )
    policy = ParserPolicy(
        max_bytes=MAX_SHARED_STRINGS_XML_BYTES,
        max_xml_depth=16,
        max_xml_elements=2_000_000,
        max_xml_text_bytes=MAX_SHARED_STRINGS_XML_BYTES,
    )
    for event, element, parent in iter_xml_events(payload, policy=policy):
        if event == "end" and element.tag.endswith("}si"):
            values.append(
                "".join(
                    text.text or ""
                    for text in element.iter()
                    if text.tag.endswith("}t")
                )
            )
            if parent is not None:
                parent.remove(element)
            element.clear()
    return values


def _benefit_cell(row: Any, shared: list[str]) -> str | None:
    for cell in row:
        if not cell.tag.endswith("}c") or not re.match(
            r"H\d+\Z", cell.attrib.get("r", "")
        ):
            continue
        value = cell.find("{*}v")
        if value is None or value.text is None:
            return None
        return (
            shared[int(value.text)]
            if cell.attrib.get("t") == "s"
            else value.text
        )
    return None


def _workbook_benefits(payload: bytes) -> list[str | None]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        shared = _shared_strings(archive)
        rows: list[str | None] = []
        payload = _xml_member(
            archive, "xl/worksheets/sheet1.xml", MAX_WORKSHEET_XML_BYTES
        )
        policy = ParserPolicy(
            max_bytes=MAX_WORKSHEET_XML_BYTES,
            max_xml_depth=16,
            max_xml_elements=12_000_000,
            max_xml_text_bytes=150_000_000,
        )
        for event, row, parent in iter_xml_events(payload, policy=policy):
            if event != "end" or not row.tag.endswith("}row"):
                continue
            row_number = int(row.attrib.get("r", "0"))
            if row_number >= FIRST_DATA_ROW:
                rows.append(_benefit_cell(row, shared))
            if parent is not None:
                parent.remove(row)
            row.clear()
        return rows


def _csv_benefits(payload: bytes) -> list[str | None]:
    with io.TextIOWrapper(
        io.BytesIO(payload), encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or "Benefit" not in reader.fieldnames:
            raise ValueError(
                "Pinned CSV no longer has its declared Benefit field"
            )
        return [row.get("Benefit") for row in reader]


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value.strip().replace(",", "").replace("$", ""))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def qualify() -> dict[str, object]:
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=MAX_OBJECT_BYTES,
        max_attempts=1,
        max_redirects=3,
    )
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(120),
        trust_env=False,
        max_redirects=policy.max_redirects,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        workbook_payload = _fetch_exact(client, OBJECTS[0])
        csv_payload = _fetch_exact(client, OBJECTS[1])

    workbook = _workbook_benefits(workbook_payload)
    csv_values = _csv_benefits(csv_payload)
    if (
        len(workbook) != EXPECTED_WORKBOOK_ROWS
        or len(csv_values) != EXPECTED_CSV_ROWS
    ):
        raise ValueError(
            "Pinned object row counts differ from the qualified layout"
        )

    counts = dict.fromkeys(SCALE_FACTORS, 0)
    numeric_pairs = 0
    zero_pairs = 0
    for workbook_value, csv_value in zip(workbook, csv_values, strict=False):
        left = _decimal(workbook_value)
        right = _decimal(csv_value)
        if left is None or right is None:
            continue
        numeric_pairs += 1
        zero_pairs += int(left == 0 or right == 0)
        for name, factor in SCALE_FACTORS.items():
            counts[name] += int(left == right * factor)

    return {
        "schema_id": "global-medicines-atlas.mbs-demographics-q1hr-benefit-scale-comparison",
        "schema_version": 1,
        "source": {
            "dataset": DATASET,
            "revision": REVISION,
            "objects": list(OBJECTS),
            "source_bytes_persisted": False,
        },
        "comparison": {
            "workbook_rows": len(workbook),
            "csv_rows": len(csv_values),
            "numeric_pairs": numeric_pairs,
            "pairs_with_zero_in_either_object": zero_pairs,
            "fixed_scale_factors_tested": list(SCALE_FACTORS),
            "exact_matches_by_fixed_scale": counts,
        },
        "interpretation": (
            "No tested fixed-scale relationship explains the aggregate mismatch. "
            "Row alignment and numeric coincidence do not establish semantic "
            "equivalence, a valid transform, or an age-category mapping."
        ),
        "boundaries": {
            "new_sources_added": False,
            "source_bytes_persisted_locally": False,
            "source_values_emitted_or_retained": False,
            "semantic_equivalence_established": False,
            "silver_projection_created": False,
            "admission_or_canary_performed": False,
            "public_dataset_mutated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = (
        json.dumps(qualify(), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    output = args.output.expanduser()
    if args.check:
        if not output.is_file() or output.read_bytes() != expected:
            raise SystemExit(f"Q1 HR benefit comparison is stale: {output}")
        print("Q1 HR aggregate benefit comparison passed")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(expected)
    print(f"wrote {output} sha256={hashlib.sha256(expected).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
