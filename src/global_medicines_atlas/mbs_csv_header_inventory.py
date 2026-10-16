"""Exact-cohort CSV header metadata, with arbitrary source tokens redacted."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .mbs_utilisation_validation import verify_staged_identity

REQUIREMENTS_PATH = Path(
    "quality/qualifications/australian-mbs-utilisation-semantic-requirements-20261005.json"
)
REQUIREMENTS_SHA256 = (
    "af64e7ac68e0e67587ca153023e2dd3ea8779046407f257f9babd425513afdc2"
)
PROFILE = "mbs-utilisation-csv-header-inventory-v1"
MAX_HEADER_BYTES = 1024 * 1024
MAX_HEADER_FIELDS = 10_000
MAX_FIELD_BYTES = 128 * 1024


def header_candidates(
    root: Path, cohort: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Bind four prior structural passes and published field-name allowlists."""
    payload = (root / REQUIREMENTS_PATH).read_bytes()
    if hashlib.sha256(payload).hexdigest() != REQUIREMENTS_SHA256:
        raise ValueError("header requirements differ")
    report = json.loads(payload)
    for binding in report["inputs"].values():
        if (
            hashlib.sha256((root / binding["path"]).read_bytes()).hexdigest()
            != binding["sha256"]
        ):
            raise ValueError("header requirements input differs")
    schemas = {
        row["resource_id"]: row
        for row in report["csv_schema_metadata_snapshots"]
    }
    rows = {row["path"]: row for row in cohort}
    selected: dict[str, list[str]] = {}
    for record in report["records"]:
        if not record["path"].endswith(".csv"):
            continue
        row = rows[record["path"]]
        if (
            record["raw_reference"] != row["raw_reference"]
            or record["acquisition_id"] != row["acquisition_id"]
            or not row["validation_dispatch_eligible"]
            or record["structural_state"] != "structure_verified"
        ):
            raise ValueError("header candidate identity differs")
        selected[record["path"]] = [
            field["id"]
            for field in schemas[record["resource_id"]]["fields"]
            if field["id"] != "_id"
        ]
    return selected


def inventory_csv_header(
    path: Path, reference: dict[str, Any], published_fields: list[str]
) -> dict[str, Any]:
    """Hash exact bytes, parse only the first CSV record, emit safe metadata."""
    verify_staged_identity(path, reference)
    with path.open("rb") as source:

        def lines():
            count = 0
            first = True
            while line := source.readline(MAX_HEADER_BYTES - count + 1):
                count += len(line)
                if count > MAX_HEADER_BYTES:
                    raise ValueError("CSV header byte limit")
                yield line.decode("utf-8-sig" if first else "utf-8")
                first = False

        try:
            header = next(csv.reader(lines(), strict=True), list[str]())
        except (UnicodeError, csv.Error) as error:
            raise ValueError("CSV header decoding or syntax invalid") from error
    if not header or len(header) > MAX_HEADER_FIELDS:
        raise ValueError("CSV header field count limit")
    if any(len(field.encode()) > MAX_FIELD_BYTES for field in header):
        raise ValueError("CSV header field byte limit")
    return {
        "format": "csv",
        "check_profile": PROFILE,
        "header_sha256": hashlib.sha256(
            json.dumps(header, separators=(",", ":")).encode()
        ).hexdigest(),
        "field_count": len(header),
        "published_field_names_in_order": [
            name if name in published_fields else None for name in header
        ],
        "unknown_field_count": sum(
            name not in published_fields for name in header
        ),
        "empty_field_count": header.count(""),
        "duplicate_field_count": len(header) - len(set(header)),
        "matches_catalogue_order": header == published_fields,
        "data_records_parsed": 0,
        "semantic_validation": False,
        "limits": {
            "header_bytes": MAX_HEADER_BYTES,
            "fields": MAX_HEADER_FIELDS,
            "field_bytes": MAX_FIELD_BYTES,
        },
    }
