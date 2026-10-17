#!/usr/bin/env python3
"""Create a value-free, candidate-only MBS source-era profile in Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import AnyUrl

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_silver_qualification import (
    MbsSourceEraVerification,
    qualify_mbs_silver,
)
from global_medicines_atlas.receipts import RightsState, SourceReceipt

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 9_000_000
EXACT_COMMIT_LENGTH = 40
DATASET = "edithatogo/australian-mbs-source-archive"
ARCHIVE_REVISION = "da83cad9116e2f9a5b927be7b080e9a5e5ea6998"
ARCHIVE_PATH = (
    "raw/mbs/releases/2026-08-01/"
    "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml"
)
ARCHIVE_URI = (
    f"https://huggingface.co/datasets/{DATASET}/resolve/"
    f"{ARCHIVE_REVISION}/{ARCHIVE_PATH}"
)
OFFICIAL_URI = (
    "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/"
    "650f3eec0dfb990fca25692100069854/"
    "81efb2067580a870ca258e28007f588c/$FILE/MBS-XML-20260801.XML"
)
OFFICIAL_PAGE = (
    "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/"
    "Content/Downloads-20260801"
)
RELEASE_SHA256 = (
    "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
)
RELEASE_BYTE_COUNT = 8_293_331
RIGHTS_REFERENCE = (
    "https://github.com/edithatogo/global-medicines-atlas/"
    "issues/339#issuecomment-5467052330"
)
RECEIPT_PATH = Path(
    "quality/bronze/receipts/au-mbs/"
    "fd32879190b69ad98cd2f207ec3b70b725ab8f524218f783ec08bf98b7ffcecd.json"
)


def _validate_exact_commit(exact_commit: str) -> None:
    if (
        len(exact_commit) != EXACT_COMMIT_LENGTH
        or re.fullmatch(r"[0-9a-f]{40}", exact_commit) is None
    ):
        raise ValueError("exact commit must be a lowercase Git SHA-1")
    if os.environ.get("GITHUB_SHA") != exact_commit:
        raise ValueError("workflow commit differs from requested exact commit")


def qualify_candidate(
    *,
    payload: bytes,
    receipt: SourceReceipt,
    official_payload: bytes,
    compared_at: datetime,
    exact_commit: str,
) -> dict[str, Any]:
    """Bind the raw candidate to its B1 receipt and official release bytes."""
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    expected = (
        receipt.source.source_id == "au-mbs"
        and receipt.source.catalog_version == "2026-08-01"
        and str(receipt.retrieval.uri) == OFFICIAL_URI
        and receipt.rights_state is RightsState.PERMITTED
        and str(receipt.rights_reference) == RIGHTS_REFERENCE
        and receipt.payload.sha256 == RELEASE_SHA256
        and receipt.payload.byte_count == RELEASE_BYTE_COUNT
    )
    if not expected:
        raise ValueError(
            "B1 receipt identity or rights differ from approved release"
        )
    if (
        hashlib.sha256(payload).hexdigest() != receipt.payload.sha256
        or len(payload) != receipt.payload.byte_count
    ):
        raise ValueError("pinned archive payload differs from B1 receipt")
    official_sha256 = hashlib.sha256(official_payload).hexdigest()
    official_matches = (
        official_sha256 == receipt.payload.sha256
        and len(official_payload) == receipt.payload.byte_count
    )
    if not official_matches:
        raise ValueError("official source differs from B1 receipt")
    verification = MbsSourceEraVerification(
        official_source_uri=AnyUrl(OFFICIAL_URI),
        release_id="MBS-XML-20260801",
        released_at=date(2026, 7, 29),
        effective_at=date(2026, 8, 1),
        official_source_sha256=official_sha256,
        official_source_byte_count=len(official_payload),
        compared_at=compared_at,
        schema_era="2026-08-01",
    )
    qualification = qualify_mbs_silver(
        payload,
        receipt,
        source_era_verification=verification,
    )
    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.mbs-source-era-candidate",
        "schema_version": 1,
        "status": "candidate_only",
        "source_era": "2026-08-01",
        "archive_dataset": DATASET,
        "archive_revision": ARCHIVE_REVISION,
        "archive_path": ARCHIVE_PATH,
        "official_source_page": OFFICIAL_PAGE,
        "official_source_uri": OFFICIAL_URI,
        "exact_commit": exact_commit,
        "official_release_match": True,
        "official_release_sha256": official_sha256,
        "official_release_byte_count": len(official_payload),
        "qualification": qualification.model_dump(mode="json"),
        "field_semantics_accepted": False,
        "historical_semantic_parity_accepted": False,
        "public_v4_admission": False,
        "m109_accepted": False,
        "source_bytes_retained": False,
        "publication_performed": False,
        "boundaries": [
            "Source-field meanings require release-specific crosswalk review.",
            "Candidate counts do not establish source-era completeness.",
            "No dataset publication or production admission was performed.",
        ],
        "compared_at": compared_at.astimezone(UTC).isoformat(),
    }
    canonical = json.dumps(
        report, sort_keys=True, separators=(",", ":")
    ).encode()
    report["candidate_sha256"] = hashlib.sha256(canonical).hexdigest()
    report["candidate_byte_count"] = len(canonical)
    return report


def _fetch(client: httpx.Client, uri: str) -> bytes:
    chunks: list[bytes] = []
    count = 0
    with client.stream("GET", uri) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            count += len(chunk)
            if count > MAX_BYTES:
                raise ValueError("MBS source exceeds the 9 MB processing limit")
            chunks.append(chunk)
    return b"".join(chunks)


def qualify(*, exact_commit: str) -> dict[str, Any]:
    """Read pinned B1/B2 identities and compare source bytes in memory only."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError(
            "MBS source bytes may be processed only in GitHub Actions"
        )
    _validate_exact_commit(exact_commit)
    receipt = SourceReceipt.model_validate_json(
        (ROOT / RECEIPT_PATH).read_bytes()
    )
    policy = AcquisitionPolicy(
        allowed_hosts=(*HOSTS, "www.mbsonline.gov.au"),
        timeout_seconds=60,
        max_bytes=MAX_BYTES,
        max_attempts=1,
        max_redirects=3,
    )
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(60),
        trust_env=False,
        max_redirects=policy.max_redirects,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        archive_payload = _fetch(client, ARCHIVE_URI)
        official_payload = _fetch(client, OFFICIAL_URI)
    return qualify_candidate(
        payload=archive_payload,
        receipt=receipt,
        official_payload=official_payload,
        compared_at=datetime.now(UTC),
        exact_commit=exact_commit,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = qualify(exact_commit=args.exact_commit)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
