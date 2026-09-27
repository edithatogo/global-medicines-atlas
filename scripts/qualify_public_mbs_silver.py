#!/usr/bin/env python3
"""Qualify a bounded MBS Silver denominator from one pinned public object.

The exact source bytes remain in memory in the hosted runner. Only the
aggregate candidate report is written to disk; this command never publishes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import AnyUrl

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.adapters.au_mbs import (
    LEGACY_MBS_BYTES,
    LEGACY_MBS_SHA256,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_silver_qualification import qualify_mbs_silver
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
SOURCE_URI = (
    "https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/"
    "resolve/4d1dae488ac43522f20e8320a8b2a56bf9138341/"
    "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML"
)
RIGHTS_REFERENCE = (
    "https://github.com/edithatogo/global-medicines-atlas/issues/340"
)
MAX_BYTES = 9_000_000
TRANSFORMATION_PATHS = (
    "scripts/qualify_public_mbs_silver.py",
    "src/global_medicines_atlas/adapters/au_mbs.py",
    "src/global_medicines_atlas/australian_source_contracts.py",
    "src/global_medicines_atlas/mbs_silver.py",
    "src/global_medicines_atlas/mbs_silver_qualification.py",
    "src/global_medicines_atlas/mbs_typed_values.py",
)


def qualify(*, rows_per_batch: int = 1024) -> dict[str, object]:
    """Restore the pinned public bytes anonymously and return safe evidence."""
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=60,
        max_bytes=MAX_BYTES,
        max_attempts=1,
        max_redirects=3,
    )
    chunks: list[bytes] = []
    byte_count = 0
    with (
        httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(60),
            trust_env=False,
            transport=BoundIPAddressTransport(policy=policy),
        ) as client,
        client.stream("GET", SOURCE_URI) as response,
    ):
        response.raise_for_status()
        for chunk in response.iter_bytes():
            byte_count += len(chunk)
            if byte_count > MAX_BYTES:
                raise ValueError(
                    "pinned MBS source exceeds the parser byte limit"
                )
            chunks.append(chunk)
    payload = b"".join(chunks)
    if len(payload) != LEGACY_MBS_BYTES:
        raise ValueError("pinned MBS source byte count differs")
    evidence = PayloadEvidence.from_bytes(payload)
    if evidence.sha256 != LEGACY_MBS_SHA256:
        raise ValueError("pinned MBS source digest differs")

    retrieved_at = datetime.now(UTC)
    transformation_digest = hashlib.sha256(
        json.dumps(
            {
                path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                for path in TRANSFORMATION_PATHS
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    receipt = SourceReceipt(
        receipt_id=f"public-archive:au-mbs:{evidence.sha256}",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="July 2025 Medicare Benefits Schedule XML",
            catalog_version="2025-07-version-3",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(SOURCE_URI),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(RIGHTS_REFERENCE),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="mbs-silver-candidate-v1",
            transformation_sha256=transformation_digest,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )
    report = qualify_mbs_silver(
        payload, receipt, date_format="mbs-dmy", rows_per_batch=rows_per_batch
    )
    return {
        "schema_id": "global-medicines-atlas.mbs-silver-public-candidate-qualification",
        "schema_version": 1,
        "qualification": report.model_dump(mode="json"),
        "source_uri": SOURCE_URI,
        "retrieved_at": retrieved_at.isoformat(),
        "publication_performed": False,
        "source_bytes_retained": False,
        "boundary": (
            "Exact public source bytes were digest-verified and processed in "
            "memory. This aggregate is candidate-only; it does not qualify "
            "the real schema era, public v4 identity, Silver publication, or "
            "M-109 acceptance."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows-per-batch", type=int, default=1024)
    args = parser.parse_args()
    result = qualify(rows_per_batch=args.rows_per_batch)
    args.output.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
