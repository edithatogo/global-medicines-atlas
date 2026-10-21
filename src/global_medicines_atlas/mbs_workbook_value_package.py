"""Deterministic P7 typed candidates with exact native-cell restore evidence.

No date convention, source meaning, rights, admission or publication is inferred.
The caller retains the immutable source and separately binds output permissions.
"""

from __future__ import annotations

import json
from collections import Counter
from itertools import zip_longest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pyarrow.parquet as pq

from .adapters.au_mbs_workbook import parse_mbs_workbook
from .mbs_demographic_package import (
    candidate_parquet_writer,
    canonical_package_json,
    file_fingerprint,
)
from .mbs_workbook_values import iter_workbook_value_batches
from .receipts import SourceReceipt

PARQUET = "cells.parquet"
MANIFEST = "qualification.json"
MAX_PARQUET_BYTES = 128 * 1024 * 1024


def _coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "native_cells": len(rows),
        "unresolved_cells": sum(
            row["interpretation_state"] == "native_unresolved" for row in rows
        ),
        "formula_cells": sum(
            row["formula_state"] != "missing_field" for row in rows
        ),
        "error_cells": sum(row["error_code"] is not None for row in rows),
        "domain_statuses": dict(
            sorted(Counter(row["domain_status"] for row in rows).items())
        ),
        "storage_statuses": dict(
            sorted(Counter(row["conversion_status"] for row in rows).items())
        ),
        "sheets": dict(
            sorted(Counter(row["sheet_path"] for row in rows).items())
        ),
    }


def _restore(
    output: Path, payload: bytes, receipt: SourceReceipt
) -> dict[str, Any]:
    """Compare restored values, schema and every native cell against exact source."""
    workbook = parse_mbs_workbook(payload, receipt)
    if not 0 < (output / PARQUET).stat().st_size <= MAX_PARQUET_BYTES:
        raise ValueError("P7 candidate exceeds restore byte bound")
    parquet = pq.ParquetFile(output / PARQUET)
    expected_batches = list(iter_workbook_value_batches(payload, receipt))
    expected_schema = expected_batches[0].schema
    if not parquet.schema_arrow.equals(expected_schema, check_metadata=True):
        raise ValueError("P7 typed schema or source metadata differs")
    restored = [
        row
        for batch in parquet.iter_batches(batch_size=1024)  # pyright: ignore[reportUnknownMemberType] -- Arrow optional selectors lack stubs
        for row in batch.to_pylist()
    ]
    expected = [row for batch in expected_batches for row in batch.to_pylist()]
    if restored != expected:
        raise ValueError("P7 typed restore differs from source projection")
    native = (cell for sheet in workbook.sheets for cell in sheet.cells)
    for cell, row in zip_longest(native, restored):
        if cell is None or row is None:
            raise ValueError("P7 native cell denominator differs")
        if any(
            row[key] != value
            for key, value in cell.model_dump(mode="json").items()
        ):
            raise ValueError("P7 native cell evidence differs")
        if (
            row["interpretation_state"] != "native_unresolved"
            or row["domain_date"] is not None
        ):
            raise ValueError(
                "P7 unresolved date or source meaning was promoted"
            )
    return {
        "schema_id": "global-medicines-atlas.mbs-p7-typed-candidate-package",
        "schema_version": 1,
        "source_sha256": receipt.payload.sha256,
        "source_receipt_sha256": receipt.digest(),
        "parquet": file_fingerprint(output / PARQUET),
        "coverage": _coverage(restored),
        "sheet_count": workbook.sheet_count,
        "date_profile": None,
        "candidate_only": True,
        "native_cell_parity_verified": True,
        "typed_parquet_restore_verified": True,
        "semantic_promotion": False,
        "rights_qualified": False,
        "output_admitted": False,
        "published": False,
    }


def build_workbook_value_package(
    payload: bytes, receipt: SourceReceipt, output: Path
) -> dict[str, Any]:
    """Atomically write source-bound native/typed cells without date guessing."""
    if output.exists():
        raise ValueError("P7 candidate destination already exists")
    batches = iter_workbook_value_batches(payload, receipt)
    first = next(batches)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".p7-candidate-", dir=output.parent
    ) as temporary:
        staging = Path(temporary) / "package"
        staging.mkdir()
        with candidate_parquet_writer(
            staging / PARQUET, first.schema
        ) as writer:
            writer.write_batch(first)
            for batch in batches:
                writer.write_batch(batch)
        report = _restore(staging, payload, receipt)
        (staging / MANIFEST).write_bytes(canonical_package_json(report))
        verify_workbook_value_package(staging, payload, receipt)
        staging.rename(output)
    return report


def verify_workbook_value_package(
    output: Path, payload: bytes, receipt: SourceReceipt
) -> dict[str, Any]:
    """Restore fixed package files against original bytes and supplied B1 receipt.

    An external trusted digest of this manifest is required for admission;
    equality here establishes candidate reconstruction only.
    """
    if {path.name for path in output.iterdir()} != {PARQUET, MANIFEST}:
        raise ValueError("P7 candidate package file set differs")
    if any((output / name).is_symlink() for name in (PARQUET, MANIFEST)):
        raise ValueError("P7 candidate package symlinks are forbidden")
    if (output / MANIFEST).stat().st_size > 1024 * 1024:
        raise ValueError("P7 candidate manifest exceeds byte bound")
    claimed = json.loads((output / MANIFEST).read_bytes())
    actual = _restore(output, payload, receipt)
    if claimed != actual:
        raise ValueError(
            "P7 candidate manifest differs from independent restore"
        )
    return actual
