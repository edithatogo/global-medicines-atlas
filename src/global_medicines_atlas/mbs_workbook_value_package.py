"""Deterministic P7 typed candidates with exact native-cell restore evidence.

Only the pinned P7 file-consistency receipt may select DMY within its four
contracted literal date fields. Other source meaning, rights, admission and
publication remain independently gated.
"""

from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
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
        "interpreted_cells": sum(
            row["interpretation_state"] == "interpreted" for row in rows
        ),
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
    output: Path,
    payload: bytes,
    receipt: SourceReceipt,
    calendar_profile_evidence: bytes | None = None,
    calendar_profile_sha256: str | None = None,
    date_inference_evidence: bytes | None = None,
    date_inference_sha256: str | None = None,
) -> dict[str, Any]:
    """Compare restored values, schema and every native cell against exact source."""
    workbook = parse_mbs_workbook(payload, receipt)
    if not 0 < (output / PARQUET).stat().st_size <= MAX_PARQUET_BYTES:
        raise ValueError("P7 candidate exceeds restore byte bound")
    parquet = pq.ParquetFile(output / PARQUET)
    expected_batches = list(
        iter_workbook_value_batches(
            payload,
            receipt,
            calendar_profile_evidence=calendar_profile_evidence,
            calendar_profile_sha256=calendar_profile_sha256,
            date_inference_evidence=date_inference_evidence,
            date_inference_sha256=date_inference_sha256,
        )
    )
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
            row["domain_date"] is not None
            and row["interpretation_state"] != "interpreted"
        ):
            raise ValueError(
                "P7 date lacks its bounded interpretation evidence"
            )
    return {
        "schema_id": "global-medicines-atlas.mbs-p7-typed-candidate-package",
        "schema_version": 1,
        "source_sha256": receipt.payload.sha256,
        "source_receipt_sha256": receipt.digest(),
        "parquet": file_fingerprint(output / PARQUET),
        "coverage": _coverage(restored),
        "sheet_count": workbook.sheet_count,
        "date_profile": (
            {
                "schema_version": 2,
                "source_bound_per_cell_unique_dates": True,
                "profile_sha256": sha256(calendar_profile_evidence).hexdigest(),
                "date_order_selected": False,
            }
            if calendar_profile_evidence is not None
            else None
        ),
        "date_inference": (
            {
                "kind": "selected_internal_file_consistency_inference",
                "source_sha256": receipt.payload.sha256,
                "profile": "dotted_DMY",
                "fields": [
                    "BenefitStartDate",
                    "DescriptionStartDate",
                    "FeeStartDate",
                    "ItemStartDate",
                ],
                "interpreted_cells": 1194,
                "evidence_sha256": sha256(date_inference_evidence).hexdigest(),
                "department_provenance_established": False,
                "domain_meaning_established": False,
                "other_workbooks_or_eras_in_scope": False,
            }
            if date_inference_evidence is not None
            else None
        ),
        "candidate_only": True,
        "native_cell_parity_verified": True,
        "typed_parquet_restore_verified": True,
        "semantic_promotion": bool(_coverage(restored)["interpreted_cells"]),
        "rights_qualified": False,
        "output_admitted": False,
        "published": False,
    }


def build_workbook_value_package(
    payload: bytes,
    receipt: SourceReceipt,
    output: Path,
    *,
    calendar_profile_evidence: bytes | None = None,
    calendar_profile_sha256: str | None = None,
    date_inference_evidence: bytes | None = None,
    date_inference_sha256: str | None = None,
) -> dict[str, Any]:
    """Atomically write source-bound native/typed cells without date guessing."""
    if output.exists():
        raise ValueError("P7 candidate destination already exists")
    batches = iter_workbook_value_batches(
        payload,
        receipt,
        calendar_profile_evidence=calendar_profile_evidence,
        calendar_profile_sha256=calendar_profile_sha256,
        date_inference_evidence=date_inference_evidence,
        date_inference_sha256=date_inference_sha256,
    )
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
        report = _restore(
            staging,
            payload,
            receipt,
            calendar_profile_evidence,
            calendar_profile_sha256,
            date_inference_evidence,
            date_inference_sha256,
        )
        (staging / MANIFEST).write_bytes(canonical_package_json(report))
        verify_workbook_value_package(
            staging,
            payload,
            receipt,
            calendar_profile_evidence=calendar_profile_evidence,
            calendar_profile_sha256=calendar_profile_sha256,
            date_inference_evidence=date_inference_evidence,
            date_inference_sha256=date_inference_sha256,
        )
        staging.rename(output)
    return report


def verify_workbook_value_package(
    output: Path,
    payload: bytes,
    receipt: SourceReceipt,
    *,
    calendar_profile_evidence: bytes | None = None,
    calendar_profile_sha256: str | None = None,
    date_inference_evidence: bytes | None = None,
    date_inference_sha256: str | None = None,
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
    actual = _restore(
        output,
        payload,
        receipt,
        calendar_profile_evidence,
        calendar_profile_sha256,
        date_inference_evidence,
        date_inference_sha256,
    )
    if claimed != actual:
        raise ValueError(
            "P7 candidate manifest differs from independent restore"
        )
    return actual
