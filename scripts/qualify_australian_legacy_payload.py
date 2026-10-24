#!/usr/bin/env python3
"""Qualify one exact Australian donor payload read only from standard input."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
from pydantic import AnyUrl

from global_medicines_atlas.adapters.au_mbs import qualify_legacy_mbs_xml
from global_medicines_atlas.adapters.au_mbs_workbook import (
    qualify_legacy_p7_workbook,
)
from global_medicines_atlas.mbs_workbook_domain import profile_workbook_domain
from global_medicines_atlas.mbs_workbook_lineage import (
    build_workbook_field_lineage,
)
from global_medicines_atlas.mbs_workbook_qualification import (
    PUBLIC_WORKBOOK_URI,
    acquire_hosted_workbook,
    qualify_workbook_cells,
)
from global_medicines_atlas.mbs_workbook_value_package import (
    build_workbook_value_package,
    verify_workbook_value_package,
)
from global_medicines_atlas.mbs_workbook_values import profile_workbook_values
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
P7_CALENDAR_PROFILE_PATH = (
    ROOT / "quality/qualifications/"
    "mbs-p7-calendar-profile-20261024-40088209026.json"
)
P7_CALENDAR_PROFILE_SHA256 = (
    "c9b49f60a9a608bc77674a2094b8fd4439115fc17bb200b04fc202c6b463d1bf"
)
P7_SOURCE_SHA256 = (
    "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
)


def _public_workbook_storage_summary(
    qualification: dict[str, Any],
) -> dict[str, Any]:
    """Keep hosted storage evidence aggregate and free of workbook cell values."""
    sheet_fields = (
        "name",
        "path",
        "dimension",
        "cells",
        "formula_cells",
        "error_cells",
        "conversion_statuses",
        "storage_types",
    )
    return {
        key: qualification[key]
        for key in (
            "schema_version",
            "qualification",
            "source_sha256",
            "source_receipt_sha256",
            "bytes",
            "sheet_count",
            "cells",
            "parquet_roundtrip_verified",
            "domain_mapping_qualified",
            "publication_performed",
        )
    } | {
        "sheets": [
            {key: sheet[key] for key in sheet_fields}
            for sheet in qualification["sheets"]
        ]
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--kind", choices=("mbs-xml", "p7-workbook"), required=True
    )
    parser.add_argument("--source-uri", required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--public-hf-workbook", action="store_true")
    return parser.parse_args()


def _p7_calendar_profile_evidence(
    source_sha256: str,
) -> tuple[bytes | None, str | None]:
    """Load only the committed profile for its exact pinned P7 object."""
    if source_sha256 != P7_SOURCE_SHA256:
        return None, None
    evidence = P7_CALENDAR_PROFILE_PATH.read_bytes()
    actual_sha256 = hashlib.sha256(evidence).hexdigest()
    if actual_sha256 != P7_CALENDAR_PROFILE_SHA256:
        raise ValueError("committed P7 calendar profile digest differs")
    return evidence, actual_sha256


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
    if arguments.public_hf_workbook:
        if (
            arguments.kind != "p7-workbook"
            or arguments.source_uri != PUBLIC_WORKBOOK_URI
        ):
            raise ValueError("hosted workbook requires its exact public URI")
        with httpx.Client(
            follow_redirects=True, timeout=60, trust_env=False
        ) as client:
            payload = acquire_hosted_workbook(client)
    else:
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
    if arguments.public_hf_workbook:
        summary["storage_qualification"] = _public_workbook_storage_summary(
            qualify_workbook_cells(payload, receipt)
        )
        summary["header_mapping_profile"] = profile_workbook_domain(
            payload, receipt
        )
        summary["workbook_field_lineage"] = build_workbook_field_lineage(
            payload, receipt
        ).model_dump(mode="json")
        summary["domain_value_profile"] = profile_workbook_values(
            payload, receipt
        )
        calendar_profile_evidence, calendar_profile_sha256 = (
            _p7_calendar_profile_evidence(receipt.payload.sha256)
        )
        with TemporaryDirectory(prefix="mbs-p7-typed-") as temporary:
            directory = Path(temporary)
            first = build_workbook_value_package(
                payload,
                receipt,
                directory / "first",
                calendar_profile_evidence=calendar_profile_evidence,
                calendar_profile_sha256=calendar_profile_sha256,
            )
            second = build_workbook_value_package(
                payload,
                receipt,
                directory / "second",
                calendar_profile_evidence=calendar_profile_evidence,
                calendar_profile_sha256=calendar_profile_sha256,
            )
            if first != second:
                raise ValueError("P7 typed deterministic rebuild differs")
            verify_workbook_value_package(
                directory / "first",
                payload,
                receipt,
                calendar_profile_evidence=calendar_profile_evidence,
                calendar_profile_sha256=calendar_profile_sha256,
            )
            manifest_sha256 = hashlib.sha256(
                (directory / "first/qualification.json").read_bytes()
            ).hexdigest()
        summary["typed_candidate_package"] = {
            **first,
            "manifest_sha256": manifest_sha256,
            "rebuild_equal": True,
            "temporary_derivatives_removed": True,
        }
        summary["p7_calendar_profile_evidence"] = (
            {
                "path": str(P7_CALENDAR_PROFILE_PATH.relative_to(ROOT)),
                "sha256": calendar_profile_sha256,
                "source_sha256": receipt.payload.sha256,
                "date_order_selected": False,
                "source_values_emitted": False,
            }
            if calendar_profile_evidence is not None
            else None
        )
        summary["workflow_commit"] = os.environ["GITHUB_SHA"]
        summary["workflow_run"] = (
            "https://github.com/edithatogo/global-medicines-atlas/actions/runs/"
            + os.environ["GITHUB_RUN_ID"]
        )
        summary["retrieved_at"] = retrieved_at.isoformat()
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
