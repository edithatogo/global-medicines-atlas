#!/usr/bin/env python3
"""Profile and assess value-free date consistency for the exact P7 copy."""

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
from global_medicines_atlas.mbs_p7_date_consistency import (
    decide_p7_date_consistency,
    profile_p7_date_consistency,
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
    module = ROOT / "src/global_medicines_atlas/mbs_p7_date_consistency.py"
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
            transformation_id="au-mbs-p7-date-consistency-v1",
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
    parser.add_argument("--exact-commit", required=True)
    arguments = parser.parse_args()
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY")
        != "edithatogo/global-medicines-atlas"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_SHA") != arguments.exact_commit
    ):
        raise ValueError("date consistency qualification requires exact main")
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
    profile = profile_p7_date_consistency(payload, receipt)
    decision = decide_p7_date_consistency(
        profile, expected_source_sha256=LEGACY_P7_SHA256
    )
    decision["workflow_commit"] = arguments.exact_commit
    decision["workflow_run"] = (
        "https://github.com/edithatogo/global-medicines-atlas/actions/runs/"
        + os.environ["GITHUB_RUN_ID"]
    )
    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.mbs-p7-date-consistency-inference",
        "schema_version": 1,
        "profile": profile,
        "decision": decision,
        "retrieved_at": retrieved_at.isoformat(),
    }
    arguments.output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
