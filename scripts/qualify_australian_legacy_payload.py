#!/usr/bin/env python3
"""Qualify one exact Australian donor payload read only from standard input."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from pydantic import AnyUrl

from global_medicines_atlas.adapters.au_mbs import qualify_legacy_mbs_xml
from global_medicines_atlas.adapters.au_mbs_workbook import (
    qualify_legacy_p7_workbook,
)
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)

ROOT = Path(__file__).resolve().parents[1]
RIGHTS_REFERENCE = AnyUrl(
    "https://github.com/edithatogo/global-medicines-atlas/issues/340"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--kind", choices=("mbs-xml", "p7-workbook"), required=True
    )
    parser.add_argument("--source-uri", required=True)
    parser.add_argument("--retrieved-at", required=True)
    return parser.parse_args()


def _receipt(
    payload: bytes,
    *,
    kind: str,
    source_uri: str,
    retrieved_at: datetime,
) -> SourceReceipt:
    if kind == "mbs-xml":
        source_id = "au-mbs"
        title = "July 2025 Medicare Benefits Schedule XML"
        module = ROOT / "src/global_medicines_atlas/adapters/au_mbs.py"
    else:
        source_id = "au-mbs-p7-legacy-workbook"
        title = "July 2024 MBS Group P7 genetics workbook"
        module = ROOT / "src/global_medicines_atlas/adapters/au_mbs_workbook.py"
    evidence = PayloadEvidence.from_bytes(payload)
    transformation_sha256 = hashlib.sha256(module.read_bytes()).hexdigest()
    return SourceReceipt(
        receipt_id=f"hosted-legacy:{source_id}:{evidence.sha256}",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title=title,
            catalog_version="legacy-donor-20260829",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(source_uri),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.PERMITTED,
        rights_reference=RIGHTS_REFERENCE,
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id=f"{source_id}-exact-legacy-qualification-v1",
            transformation_sha256=transformation_sha256,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def main() -> None:
    """Read, qualify and emit only a public-safe summary receipt."""
    arguments = _arguments()
    retrieved_at = datetime.fromisoformat(arguments.retrieved_at)
    if retrieved_at.tzinfo is None:
        raise ValueError("--retrieved-at must include a timezone")
    payload = sys.stdin.buffer.read()
    receipt = _receipt(
        payload,
        kind=arguments.kind,
        source_uri=arguments.source_uri,
        retrieved_at=retrieved_at,
    )
    if arguments.kind == "mbs-xml":
        batch = qualify_legacy_mbs_xml(payload, receipt)
        summary: dict[str, object] = {
            "kind": arguments.kind,
            "sha256": receipt.payload.sha256,
            "bytes": receipt.payload.byte_count,
            "records": batch.record_count,
            "native_fields": list(batch.observed_fields),
            "fields_per_record": dict(
                sorted(
                    Counter(
                        len(record.fields) for record in batch.records
                    ).items()
                )
            ),
        }
    else:
        workbook = qualify_legacy_p7_workbook(payload, receipt)
        summary = {
            "kind": arguments.kind,
            "sha256": receipt.payload.sha256,
            "bytes": receipt.payload.byte_count,
            "sheets": [
                {
                    "name": sheet.name,
                    "dimension": sheet.dimension,
                    "cells": len(sheet.cells),
                    "formula_cells": sum(
                        cell.formula is not None for cell in sheet.cells
                    ),
                    "error_cells": sum(
                        cell.cell_type == "e" for cell in sheet.cells
                    ),
                }
                for sheet in workbook.sheets
            ],
        }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
