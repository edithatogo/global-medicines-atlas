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
from typing import Any, Literal

import httpx
from pydantic import AnyUrl

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.adapters.au_mbs import (
    inspect_mbs_source_xml_stream,
    iter_mbs_source_xml_records,
)
from global_medicines_atlas.australian_source_contracts import (
    TargetTable,
    mbs_field_contracts,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_silver import iter_mbs_silver_batches
from global_medicines_atlas.mbs_silver_qualification import (
    MbsSourceEraVerification,
    qualify_mbs_silver,
)
from global_medicines_atlas.receipts import RightsState, SourceReceipt

ROOT = Path(__file__).resolve().parents[1]
SEMANTICS_PATH = "docs/qualification/mbs-xml-v3-field-semantics-2026-08.md"
MAX_BYTES = 9_000_000
EXACT_COMMIT_LENGTH = 40
DATASET = "edithatogo/australian-mbs-source-archive"
SOURCE_DATE_FORMAT: Literal["mbs-dmy"] = "mbs-dmy"
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
_TABLES: tuple[TargetTable, ...] = (
    "services",
    "hierarchy",
    "descriptions",
    "fees",
    "benefits",
    "caps",
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
        date_format=SOURCE_DATE_FORMAT,
        source_era_verification=verification,
    )
    field_presence = field_presence_diagnostics(
        payload, receipt, date_format=SOURCE_DATE_FORMAT
    )
    semantics_sha256 = hashlib.sha256(
        (ROOT / SEMANTICS_PATH).read_bytes()
    ).hexdigest()
    presence_mismatches = sum(
        int(item["presence_state_mismatches"]) for item in field_presence
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
        "field_presence_diagnostics": field_presence,
        "source_presence_projection_alignment": (
            "matched" if presence_mismatches == 0 else "mismatch_detected"
        ),
        "field_semantics_accepted": True,
        "field_semantics_path": SEMANTICS_PATH,
        "field_semantics_sha256": semantics_sha256,
        "date_format_evidence": "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/FAQ-XML_Help",
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


# ruff: ignore[too-many-locals] - bounded per-field state reconciliation
def field_presence_diagnostics(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    date_format: Literal["iso", "mbs-dmy"] | None = None,
) -> list[dict[str, Any]]:
    """Compare source field presence and projected native state by field."""
    stream_metadata = inspect_mbs_source_xml_stream(payload, receipt)
    contracts = mbs_field_contracts()
    counts: dict[str, dict[str, Any]] = {
        field.native_name: {
            "target_table": field.target_table,
            "source_present": 0,
            "source_null": 0,
            "projected_states": {},
            "conversion_status_counts": {},
            "presence_state_mismatches": 0,
        }
        for field in contracts
    }
    for table in _TABLES:
        table_contracts = tuple(
            field for field in contracts if field.target_table == table
        )
        source_records = iter_mbs_source_xml_records(payload, stream_metadata)
        projected_rows = (
            row
            for batch in iter_mbs_silver_batches(
                payload, receipt, table=table, date_format=date_format
            )
            for row in batch.to_pylist()
        )
        row_count = 0
        for source, projected in zip(
            source_records, projected_rows, strict=True
        ):
            row_count += 1
            if (
                source.source_ordinal != projected["source_ordinal"]
                or source.source_record_id != projected["source_record_id"]
            ):
                raise ValueError(
                    "MBS source and projected row identities differ"
                )
            native_fields = {field.name: field.value for field in source.fields}
            for contract in table_contracts:
                name = contract.native_name
                projected_value = projected[name]
                source_state = (
                    "missing_field"
                    if name not in native_fields
                    else "null"
                    if native_fields[name] is None
                    else "value"
                )
                field_counts = counts[name]
                if name in native_fields:
                    field_counts["source_present"] += 1
                    if native_fields[name] is None:
                        field_counts["source_null"] += 1
                if projected_value["native_state"] != source_state:
                    field_counts["presence_state_mismatches"] += 1
                statuses = field_counts["projected_states"]
                status = projected_value["native_state"]
                statuses[status] = statuses.get(status, 0) + 1
                conversions = field_counts["conversion_status_counts"]
                conversion_status = projected_value["conversion_status"]
                conversions[conversion_status] = (
                    conversions.get(conversion_status, 0) + 1
                )
        if row_count != stream_metadata.record_count:
            raise ValueError("MBS source and projected row counts differ")
    return [
        {
            "native_field": name,
            "rows": stream_metadata.record_count,
            "target_table": field_counts["target_table"],
            "source_present": field_counts["source_present"],
            "source_null": field_counts["source_null"],
            "projected_states": field_counts["projected_states"],
            "conversion_status_counts": field_counts[
                "conversion_status_counts"
            ],
            "presence_state_mismatches": field_counts[
                "presence_state_mismatches"
            ],
            "requiredness_accepted": False,
        }
        for name, field_counts in sorted(counts.items())
    ]


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
