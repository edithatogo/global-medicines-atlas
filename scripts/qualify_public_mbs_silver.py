#!/usr/bin/env python3
"""Qualify a bounded MBS Silver denominator from one pinned public object.

The exact source bytes remain in memory in the hosted runner. Only the
aggregate candidate report is written to disk; this command never publishes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
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
from global_medicines_atlas.australian_source_contracts import (
    TargetTable,
    mbs_field_contracts,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_silver import (
    MAX_MBS_AMOUNT_INTEGER_DIGITS,
    iter_mbs_silver_batches,
)
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
GIT_SHA1_HEX_LENGTH = 40
_TABLES: tuple[TargetTable, ...] = (
    "services",
    "hierarchy",
    "descriptions",
    "fees",
    "benefits",
    "caps",
)
_QUALITY_STATUSES = frozenset({
    "blank",
    "invalid",
    "unrepresentable",
    "unsupported_format",
})
_NUMERIC_TEXT = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")


def qualify(
    *, exact_commit: str, rows_per_batch: int = 1024
) -> dict[str, object]:
    """Restore the pinned public bytes anonymously and return safe evidence."""
    if len(exact_commit) != GIT_SHA1_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in exact_commit
    ):
        raise ValueError("exact commit must be a lowercase Git SHA-1")
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
            max_redirects=policy.max_redirects,
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
            transformation_id="exact-public-source-restore-v1",
            transformation_sha256=hashlib.sha256(
                exact_commit.encode("ascii")
            ).hexdigest(),
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )
    report = qualify_mbs_silver(
        payload, receipt, date_format="mbs-dmy", rows_per_batch=rows_per_batch
    )
    quality_diagnostics = _quality_diagnostics(
        payload, receipt, rows_per_batch=rows_per_batch
    )
    candidate_report = {
        "qualification": report.model_dump(mode="json"),
        "quality_diagnostics": quality_diagnostics,
    }
    report_bytes = json.dumps(
        candidate_report,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return {
        "schema_id": "global-medicines-atlas.mbs-silver-public-candidate-qualification",
        "schema_version": 1,
        **candidate_report,
        "candidate_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "candidate_report_byte_count": len(report_bytes),
        "exact_commit": exact_commit,
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


def _quality_diagnostics(
    payload: bytes, receipt: SourceReceipt, *, rows_per_batch: int
) -> dict[str, object]:
    """Aggregate field/status counts and bad row ordinals without values."""
    field_status_counts: Counter[tuple[str, str, str]] = Counter()
    finding_ordinals: defaultdict[tuple[str, str, str], list[int]] = (
        defaultdict(list)
    )
    amount_issue_ordinals: defaultdict[tuple[str, str, str], list[int]] = (
        defaultdict(list)
    )
    amount_fields = {
        (contract.target_table, contract.native_name)
        for contract in mbs_field_contracts()
        if contract.value_type == "aud_decimal"
    }
    for table in _TABLES:
        field_names = tuple(
            contract.native_name
            for contract in mbs_field_contracts()
            if contract.target_table == table
        )
        for batch in iter_mbs_silver_batches(
            payload,
            receipt,
            table=table,
            date_format="mbs-dmy",
            rows_per_batch=rows_per_batch,
        ):
            for row in batch.to_pylist():
                ordinal = int(row["source_ordinal"])
                for field_name in field_names:
                    value = row[field_name]
                    status = str(value["conversion_status"])
                    key = (table, field_name, status)
                    field_status_counts[key] += 1
                    if status in _QUALITY_STATUSES:
                        finding_ordinals[key].append(ordinal)
                    if (
                        status == "invalid"
                        and (table, field_name) in amount_fields
                    ):
                        native_value = value["native_value"]
                        reason = _amount_invalid_reason(native_value)
                        amount_issue_ordinals[table, field_name, reason].append(
                            ordinal
                        )
    return {
        "field_status_counts": [
            {
                "table": table,
                "field": field_name,
                "status": status,
                "count": count,
            }
            for (table, field_name, status), count in sorted(
                field_status_counts.items()
            )
        ],
        "quality_finding_source_ordinals": [
            {
                "table": table,
                "field": field_name,
                "status": status,
                "source_ordinals": ordinals,
            }
            for (table, field_name, status), ordinals in sorted(
                finding_ordinals.items()
            )
        ],
        "invalid_amount_reason_source_ordinals": [
            {
                "table": table,
                "field": field_name,
                "reason": reason,
                "source_ordinals": ordinals,
            }
            for (table, field_name, reason), ordinals in sorted(
                amount_issue_ordinals.items()
            )
        ],
        "source_values_included": False,
    }


def _amount_invalid_reason(native_value: object) -> str:
    """Classify invalid amount text without retaining or returning its value."""
    if not isinstance(native_value, str) or not _NUMERIC_TEXT.fullmatch(
        native_value
    ):
        return "strict_numeric_grammar_mismatch"
    integer = native_value.lstrip("+-").partition(".")[0]
    if len(integer) > MAX_MBS_AMOUNT_INTEGER_DIGITS:
        return "integer_width_exceeded"
    return "other_numeric_validation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows-per-batch", type=int, default=1024)
    args = parser.parse_args()
    result = qualify(
        exact_commit=args.exact_commit,
        rows_per_batch=args.rows_per_batch,
    )
    args.output.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
