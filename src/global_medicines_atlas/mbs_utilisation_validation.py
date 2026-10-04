"""Bounded structural checks for the exact historical MBS utilisation cohort."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from global_medicines_atlas.archive_safety import (
    DEFAULT_ARCHIVE_POLICY,
    verify_zip_file,
)
from global_medicines_atlas.australian_harvesting import (
    MAX_XLSX_PAYLOAD_BYTES,
    MAX_XLSX_UNCOMPRESSED_BYTES,
    validate_xlsx_payload,
)

PREFLIGHT_PATH = Path(
    "quality/qualifications/australian-mbs-utilisation-validation-preflight-20261004.json"
)
PREFLIGHT_SHA256 = (
    "c7fa8c0ee0d9991fff6ea70ca4058a79b5af46c0675a493dc0bedbd611f7edbb"
)
MAX_CSV_BYTES = 32 * 1024 * 1024
MAX_CSV_COLUMNS = 10_000
MAX_CSV_ROWS = 10_000_000


def load_validation_cohort(root: Path) -> list[dict[str, Any]]:
    """Load only the reviewed preflight and verify all its evidence bindings."""
    payload = (root / PREFLIGHT_PATH).read_bytes()
    if hashlib.sha256(payload).hexdigest() != PREFLIGHT_SHA256:
        raise ValueError("exact validation preflight differs")
    document = json.loads(payload)
    for binding in document["inputs"].values():
        if (
            hashlib.sha256((root / binding["path"]).read_bytes()).hexdigest()
            != binding["sha256"]
        ):
            raise ValueError("validation input binding differs")
    return document["records"]


def validate_staged_payload(
    path: Path, reference: dict[str, Any]
) -> dict[str, Any]:
    """Verify receipt identity and format structure; return counts, never values.

    The isolated caller must enforce a hard time and memory bound. ZIP members
    are not interpreted as tables. XLSX checks package metadata only; CSV uses
    strict UTF-8 with optional BOM and rectangular records, without guessing an
    encoding or interpreting domain fields. This is not processing admission.
    """
    suffix = Path(reference["path"]).suffix.lower()
    verify_staged_identity(path, reference)
    size = reference["byte_count"]
    if suffix == ".csv":
        return _validate_csv(path)
    if suffix not in {".zip", ".xlsx"}:
        raise ValueError("unsupported payload format")
    policy = DEFAULT_ARCHIVE_POLICY
    if suffix == ".xlsx":
        policy = replace(
            policy,
            max_archive_bytes=MAX_XLSX_PAYLOAD_BYTES,
            max_total_uncompressed_bytes=MAX_XLSX_UNCOMPRESSED_BYTES,
        )
    receipt = verify_zip_file(
        path,
        expected_sha256=reference["sha256"],
        expected_size=size,
        policy=policy,
    )
    if not receipt.members:
        raise ValueError("archive contains no regular members")
    if suffix == ".xlsx":
        validate_xlsx_payload(reference["path"], path.read_bytes())
    # No source-native names or values leave the worker; bind the internal
    # member inventory using its canonical digest instead.
    inventory = [
        (member.path, member.sha256, member.size_bytes)
        for member in receipt.members
    ]
    return {
        "format": suffix[1:],
        "member_count": len(receipt.members),
        "expanded_bytes": receipt.total_uncompressed_bytes,
        "member_inventory_sha256": hashlib.sha256(
            json.dumps(inventory, separators=(",", ":")).encode()
        ).hexdigest(),
        "check_profile": "zip-stream-integrity-and-ooxml-package"
        if suffix == ".xlsx"
        else "zip-stream-integrity",
    }


def verify_staged_identity(path: Path, reference: dict[str, Any]) -> None:
    """Stream-check exact receipt size and digest before any format parsing."""
    suffix = Path(reference["path"]).suffix.lower()
    limit = (
        DEFAULT_ARCHIVE_POLICY.max_archive_bytes
        if suffix == ".zip"
        else MAX_CSV_BYTES
    )
    size = reference["byte_count"]
    if type(size) is not int or not 0 < size <= limit:
        raise ValueError("payload resource limit")
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as source:
        while block := source.read(DEFAULT_ARCHIVE_POLICY.chunk_bytes):
            count += len(block)
            if count > size:
                raise ValueError("payload byte count differs")
            digest.update(block)
    if count != size or digest.hexdigest() != reference["sha256"]:
        raise ValueError("payload identity differs")


def _validate_csv(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        header = next(reader, list[str]())
        width = len(header)
        if not 0 < width <= MAX_CSV_COLUMNS or not any(header):
            raise ValueError("CSV header missing or exceeds limit")
        rows = 0
        for row in reader:
            rows += 1
            if rows > MAX_CSV_ROWS or len(row) != width:
                raise ValueError("CSV shape or row bound failed")
        if not rows:
            raise ValueError("CSV contains no data records")
    return {
        "format": "csv",
        "row_count": rows,
        "column_count": width,
        "check_profile": "utf8-bom-rectangular-csv",
    }
