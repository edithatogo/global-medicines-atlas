#!/usr/bin/env python3
"""Read the exact pinned P7 workbook in main Actions and emit counts only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import AnyUrl

from global_medicines_atlas.adapters.au_mbs_workbook import (
    LEGACY_P7_BYTES,
    LEGACY_P7_SHA256,
)
from global_medicines_atlas.mbs_p7_calendar_profile import (
    profile_p7_calendar_dates,
)
from global_medicines_atlas.mbs_workbook_qualification import (
    PUBLIC_WORKBOOK_URI,
    acquire_hosted_workbook,
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


def _receipt(payload: bytes, retrieved_at: datetime) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    module = ROOT / "src/global_medicines_atlas/adapters/au_mbs_workbook.py"
    return SourceReceipt(
        receipt_id=f"hosted-legacy:au-mbs-p7-legacy-workbook:{evidence.sha256}",
        source=SourceIdentity(
            catalog_id="au-mbs-p7-legacy-workbook",
            source_id="au-mbs-p7-legacy-workbook",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="July 2024 MBS Group P7 genetics workbook",
            catalog_version="legacy-donor-20260829",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(PUBLIC_WORKBOOK_URI),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.PERMITTED,
        rights_reference=RIGHTS_REFERENCE,
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="au-mbs-p7-calendar-profile-v1",
            transformation_sha256=hashlib.sha256(
                module.read_bytes()
            ).hexdigest(),
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY")
        != "edithatogo/global-medicines-atlas"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
    ):
        raise ValueError("exact P7 profiling is restricted to main Actions")
    retrieved_at = datetime.now(UTC)
    with httpx.Client(
        follow_redirects=True, timeout=60, trust_env=False
    ) as client:
        payload = acquire_hosted_workbook(client)
    if (
        len(payload) != LEGACY_P7_BYTES
        or hashlib.sha256(payload).hexdigest() != LEGACY_P7_SHA256
    ):
        raise ValueError("hosted workbook identity changed")
    receipt = _receipt(payload, retrieved_at)
    report: dict[str, Any] = {
        "kind": "mbs_p7_unique_calendar_date_profile",
        "profile": profile_p7_calendar_dates(payload, receipt),
        "workflow_commit": os.environ["GITHUB_SHA"],
        "workflow_run": (
            "https://github.com/edithatogo/global-medicines-atlas/actions/runs/"
            + os.environ["GITHUB_RUN_ID"]
        ),
        "retrieved_at": retrieved_at.isoformat(),
    }
    arguments.output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
