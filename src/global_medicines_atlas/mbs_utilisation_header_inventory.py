"""Metadata-only inventory for the exact, previously verified MBS CSVs."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

SEMANTIC_REQUIREMENTS_PATH = Path(
    "quality/qualifications/australian-mbs-utilisation-semantic-requirements-20261005.json"
)
SEMANTIC_REQUIREMENTS_SHA256 = (
    "af64e7ac68e0e67587ca153023e2dd3ea8779046407f257f9babd425513afdc2"
)
STRUCTURAL_RECEIPT_PATH = Path(
    "quality/qualifications/australian-mbs-utilisation-payload-validation-receipt-20261004.json"
)
STRUCTURAL_RECEIPT_SHA256 = (
    "f622434530f3d184a5aea6684e67dc7f874424c2ada634b2f154490a39c6f457"
)
MAX_HEADER_COLUMNS = 10_000
MAX_HEADER_FIELD_BYTES = 1_048_576
EXPECTED_CSV_SCHEMA_COUNT = 4


@dataclass(frozen=True)
class HeaderInventory:
    """A first-record inventory retained in memory inside the hosted worker."""

    headers: tuple[str, ...]
    header_sha256: str
    column_count: int
    schema_matches: tuple[str, ...]


def load_header_inventory_contract(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, ...]]]:
    """Load four CSV identities joined to exact prior receipts and schemas."""
    requirements = _read_bound_json(
        root,
        SEMANTIC_REQUIREMENTS_PATH,
        SEMANTIC_REQUIREMENTS_SHA256,
        "semantic requirements",
    )
    structural = _read_bound_json(
        root,
        STRUCTURAL_RECEIPT_PATH,
        STRUCTURAL_RECEIPT_SHA256,
        "structural receipt",
    )
    schemas: dict[str, tuple[str, ...]] = {}
    approved_headers: set[str] = set()
    for snapshot in requirements["csv_schema_metadata_snapshots"]:
        fields = snapshot["fields"]
        names = tuple(field["id"] for field in fields)
        resource_id = snapshot["resource_id"]
        if resource_id in schemas or not names:
            raise ValueError("CSV catalogue schema metadata is invalid")
        # CKAN's generated row identifier is catalogue metadata, not assumed
        # to be a source-native field in the immutable CSV bytes.
        schemas[resource_id] = tuple(name for name in names if name != "_id")
        approved_headers.update(names)
    if len(schemas) != EXPECTED_CSV_SCHEMA_COUNT:
        raise ValueError(
            "exactly four reviewed CSV catalogue schemas are required"
        )
    source_by_resource = {
        row["resource_id"]: row["source_id"] for row in requirements["records"]
    }

    receipt_by_path: dict[str, dict[str, Any]] = {}
    for receipt in structural["per_object_receipts"]:
        document = receipt["document"]
        reference = document["raw_reference"]
        receipt_by_path[reference["path"]] = receipt

    selected: list[dict[str, Any]] = []
    for row in requirements["records"]:
        if row.get("hosted_inventory_candidate") is not True:
            continue
        reference = row["raw_reference"]
        if Path(reference["path"]).suffix.lower() != ".csv":
            continue
        if row["resource_id"] not in schemas:
            raise ValueError("CSV object has no reviewed schema snapshot")
        prior = receipt_by_path.get(reference["path"])
        if not _has_exact_structural_receipt(
            prior, row, reference, len(schemas[row["resource_id"]])
        ):
            raise ValueError("CSV object lacks exact prior structural receipt")
        selected.append({
            **row,
            "approved_headers": sorted(approved_headers),
            "schema_candidate_ids": sorted(
                resource_id
                for resource_id in schemas
                if source_by_resource.get(resource_id) == row["source_id"]
            ),
        })
    if (
        len(selected) != EXPECTED_CSV_SCHEMA_COUNT
        or len({row["resource_id"] for row in selected})
        != EXPECTED_CSV_SCHEMA_COUNT
    ):
        raise ValueError("exactly four distinct CSV resources must be selected")
    return selected, schemas


def _has_exact_structural_receipt(
    prior: dict[str, Any] | None,
    row: dict[str, Any],
    reference: dict[str, Any],
    expected_column_count: int,
) -> bool:
    if prior is None:
        return False
    document = prior.get("document", {})
    checks = document.get("result", {}).get("checks", {})
    return all((
        prior.get("url") == row.get("structural_receipt_url"),
        document.get("status") == "structure_verified",
        document.get("raw_reference") == reference,
        document.get("acquisition_id") == row["acquisition_id"],
        document.get("result", {}).get("anonymous_digest_verified") is True,
        checks.get("format") == "csv",
        checks.get("column_count") == expected_column_count,
        row.get("structural_state") == "structure_verified",
        row.get("processing_admitted") is False,
    ))


def inventory_csv_header(
    path: Path,
    candidate_schemas: dict[str, tuple[str, ...]],
) -> HeaderInventory:
    """Parse just the CSV header record; do not iterate over source data rows."""
    old_limit = csv.field_size_limit()
    csv.field_size_limit(MAX_HEADER_FIELD_BYTES)
    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source, strict=True)
            headers = next(reader, None)
    except (UnicodeError, csv.Error) as error:
        raise ValueError("CSV header cannot be decoded") from error
    finally:
        csv.field_size_limit(old_limit)
    if (
        headers is None
        or not headers
        or len(headers) > MAX_HEADER_COLUMNS
        or any(not name or "\x00" in name for name in headers)
    ):
        raise ValueError("CSV header missing or exceeds inventory bounds")
    immutable_headers = tuple(headers)
    canonical = json.dumps(
        list(immutable_headers), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return HeaderInventory(
        headers=immutable_headers,
        header_sha256=hashlib.sha256(canonical).hexdigest(),
        column_count=len(immutable_headers),
        schema_matches=tuple(
            name
            for name, schema in sorted(candidate_schemas.items())
            if immutable_headers == schema
        ),
    )


def public_header_result(
    inventory: HeaderInventory, approved_headers: frozenset[str]
) -> dict[str, Any]:
    """Mask all header tokens absent from the reviewed public catalogue."""
    public_names = [
        name for name in inventory.headers if name in approved_headers
    ]
    unexpected = [
        name for name in inventory.headers if name not in approved_headers
    ]
    return {
        "header_sha256": inventory.header_sha256,
        "column_count": inventory.column_count,
        "headers": public_names,
        "unexpected_field_count": len(unexpected),
        "unexpected_headers_sha256": _canonical_digest(unexpected)
        if unexpected
        else None,
        "schema_matches": list(inventory.schema_matches),
    }


def workflow_run_url(run_id: str | None = None) -> str:
    """Return a validated GitHub Actions run URL for durable receipts."""
    value = os.environ.get("GITHUB_RUN_ID") if run_id is None else run_id
    if value is None or not re.fullmatch(r"[0-9]+", value):
        raise ValueError("workflow run identity is missing or invalid")
    return (
        "https://github.com/edithatogo/global-medicines-atlas/actions/runs/"
        f"{value}"
    )


def _read_bound_json(
    root: Path, relative: Path, expected_sha256: str, label: str
) -> dict[str, Any]:
    try:
        payload = (root / relative).read_bytes()
    except OSError as error:
        raise ValueError(f"{label} is unavailable") from error
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError(f"{label} digest differs")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError(f"{label} is not an object")
    return cast("dict[str, Any]", value)


def _canonical_digest(value: list[str]) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
