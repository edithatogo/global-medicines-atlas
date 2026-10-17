#!/usr/bin/env python3
"""Compare approved MBS release eras without retaining source values."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

import httpx
from pydantic import AnyUrl, TypeAdapter

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.adapters.au_mbs import (
    MBS_NATIVE_FIELDS,
    inspect_mbs_source_xml_stream,
    iter_mbs_source_xml_records,
)
from global_medicines_atlas.federation_reader import HOSTS
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
DATASET = "edithatogo/australian-mbs-source-archive"
ARCHIVE_REVISION = "da83cad9116e2f9a5b927be7b080e9a5e5ea6998"
MAX_BYTES = 9_000_000
EXACT_COMMIT_LENGTH = 40


class ReleaseIdentity(TypedDict):
    source_era: str
    release_id: str
    archive_path: str
    sha256: str
    byte_count: int
    official_uri: str
    official_page: str
    rights_reference: str
    harvest_receipt_path: str
    harvest_receipt_sha256: str


JULY: ReleaseIdentity = {
    "source_era": "2026-07-01",
    "release_id": "MBS-XML-20260701",
    "archive_path": "raw/mbs/releases/Downloads-20260701/MBS-XML-20260701.XML",
    "harvest_receipt_path": "bronze/mbs/releases/Downloads-20260701/MBS-XML-20260701.XML.receipt.json",
    "harvest_receipt_sha256": "01988fb6cf56c4a23bba680e8c9ee6d9b3b39d504d044676e49b4b78d1f5ba56",
    "sha256": "5834d849743a3eab2b8c03e826a5ed6a488a6f65cf4c4148da3ec227e5007805",
    "byte_count": 8_291_891,
    "official_uri": "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/650f3eec0dfb990fca25692100069854/d4bd04ca56657072ca258df70023b066/$FILE/MBS-XML-20260701.XML",
    "official_page": "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-20260701",
    "rights_reference": "https://github.com/edithatogo/global-medicines-atlas/blob/2ceafb1b889a701506a6c8f0ec9b1fc86fdddbda/quality/qualifications/australian-mbs-harvest-publication-authorization.json",
}
AUGUST: ReleaseIdentity = {
    "source_era": "2026-08-01",
    "release_id": "MBS-XML-20260801",
    "archive_path": "raw/mbs/releases/2026-08-01/c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml",
    "sha256": "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565",
    "byte_count": 8_293_331,
    "official_uri": "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/650f3eec0dfb990fca25692100069854/81efb2067580a870ca258e28007f588c/$FILE/MBS-XML-20260801.XML",
    "official_page": "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-20260801",
    "rights_reference": "https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-5467052330",
    "harvest_receipt_path": "bronze/mbs/releases/Downloads-20260801/MBS-XML-20260801.XML.receipt.json",
    "harvest_receipt_sha256": "9bca6260ea9d25d7ee9c184b59eed03b059d8da486dea31ec1d058965aae55ed",
}


def _exact_commit(value: str) -> None:
    if len(value) != EXACT_COMMIT_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("exact commit must be a lowercase Git SHA-1")
    if os.environ.get("GITHUB_SHA") != value:
        raise ValueError("workflow commit differs from requested exact commit")


def _receipt(era: ReleaseIdentity, retrieved_at: datetime) -> SourceReceipt:
    payload = PayloadEvidence(
        sha256=era["sha256"], byte_count=era["byte_count"]
    )
    return SourceReceipt(
        receipt_id=f"mbs-release:{era['sha256']}",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="Medicare Benefits Schedule XML releases",
            catalog_version=era["source_era"],
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(era["official_uri"]),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=payload,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(era["rights_reference"]),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="raw-acquisition-v1",
            transformation_sha256=hashlib.sha256(
                b"raw-acquisition-v1"
            ).hexdigest(),
            output_sha256=payload.sha256,
            output_byte_count=payload.byte_count,
        ),
    )


def _record_identity(fields: dict[str, str | None]) -> tuple[str, ...]:
    """Return the release-independent MBS item identity, kept in memory only."""
    return tuple(
        (fields.get(name) or "").strip()
        for name in ("ItemNum", "SubItemNum", "ItemStartDate")
    )


def _profile(payload: bytes, receipt: SourceReceipt) -> dict[str, Any]:
    metadata = inspect_mbs_source_xml_stream(payload, receipt)
    field_counts: dict[str, Counter[str]] = {
        name: Counter() for name in MBS_NATIVE_FIELDS
    }
    records: dict[tuple[str, ...], dict[str, str | None]] = {}
    for record in iter_mbs_source_xml_records(payload, metadata):
        values = {field.name: field.value for field in record.fields}
        identity = _record_identity(values)
        if identity in records:
            raise ValueError(
                "ambiguous repeated MBS item identity; comparison is incomplete"
            )
        records[identity] = values
        for field in MBS_NATIVE_FIELDS:
            if field not in values:
                field_counts[field]["absent"] += 1
            elif values[field] is None:
                field_counts[field]["null"] += 1
            else:
                field_counts[field]["value"] += 1
    return {
        "record_count": metadata.record_count,
        "native_fields": sorted(metadata.observed_fields),
        "field_counts": field_counts,
        "records": records,
    }


# ruff: ignore[too-many-locals] - keep release comparison state in one bounded scope
def compare_releases(
    *,
    july_payload: bytes,
    august_payload: bytes,
    july_official_payload: bytes,
    august_official_payload: bytes,
    compared_at: datetime,
    exact_commit: str,
) -> dict[str, Any]:
    """Verify both source identities and return aggregate-only diagnostics."""
    july_receipt = _receipt(JULY, compared_at)
    august_receipt = _receipt(AUGUST, compared_at)
    payloads: tuple[tuple[ReleaseIdentity, bytes, bytes], ...] = (
        (JULY, july_payload, july_official_payload),
        (AUGUST, august_payload, august_official_payload),
    )
    for era, archived, official in payloads:
        for label, payload in (("archive", archived), ("official", official)):
            if (
                len(payload) != era["byte_count"]
                or hashlib.sha256(payload).hexdigest() != era["sha256"]
            ):
                raise ValueError(
                    f"{era['source_era']} {label} bytes differ from pinned identity"
                )
    july = _profile(july_payload, july_receipt)
    august = _profile(august_payload, august_receipt)
    july_records = july["records"]
    august_records = august["records"]
    july_ids = set(july_records)
    august_ids = set(august_records)
    shared_ids = july_ids & august_ids
    changed_records = 0
    changed_fields: Counter[str] = Counter()
    added_fields: Counter[str] = Counter()
    removed_fields: Counter[str] = Counter()
    fields_on_added_records: Counter[str] = Counter()
    fields_on_removed_records: Counter[str] = Counter()
    for identity in shared_ids:
        before = july_records[identity]
        after = august_records[identity]
        record_changed = False
        for name in set(before) | set(after):
            if name not in before:
                added_fields[name] += 1
                record_changed = True
            elif name not in after:
                removed_fields[name] += 1
                record_changed = True
            elif before[name] != after[name]:
                changed_fields[name] += 1
                record_changed = True
        changed_records += int(record_changed)
    for identity in august_ids - july_ids:
        fields_on_added_records.update(august_records[identity].keys())
    for identity in july_ids - august_ids:
        fields_on_removed_records.update(july_records[identity].keys())

    def field_summary(profile: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "native_field": name,
                "rows": profile["record_count"],
                "present_non_null": profile["field_counts"][name]["value"],
                "present_null": profile["field_counts"][name]["null"],
                "absent": profile["field_counts"][name]["absent"],
            }
            for name in sorted(MBS_NATIVE_FIELDS)
        ]

    def counts(values: Counter[str]) -> list[dict[str, Any]]:
        return [
            {"native_field": name, "count": values[name]}
            for name in sorted(values)
        ]

    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.mbs-predecessor-comparison",
        "schema_version": 1,
        "status": "aggregate_comparison_complete",
        "exact_commit": exact_commit,
        "compared_at": compared_at.astimezone(UTC).isoformat(),
        "releases": [
            {
                "source_era": era["source_era"],
                "release_id": era["release_id"],
                "archive_revision": ARCHIVE_REVISION,
                "archive_path": era["archive_path"],
                "official_source_uri": era["official_uri"],
                "official_download_page": era["official_page"],
                "sha256": era["sha256"],
                "byte_count": era["byte_count"],
                "rights_reference": era["rights_reference"],
                "harvest_receipt_sha256": era["harvest_receipt_sha256"],
                "archive_official_identity_match": True,
                "record_count": profile["record_count"],
                "native_fields": profile["native_fields"],
                "field_presence_counts": field_summary(profile),
            }
            for era, profile in ((JULY, july), (AUGUST, august))
        ],
        "comparison": {
            "matched_record_count": len(shared_ids),
            "added_record_count": len(august_ids - july_ids),
            "removed_record_count": len(july_ids - august_ids),
            "changed_record_count": changed_records,
            "changed_field_counts": counts(changed_fields),
            "added_field_counts": counts(added_fields),
            "removed_field_counts": counts(removed_fields),
            "fields_on_added_records": counts(fields_on_added_records),
            "fields_on_removed_records": counts(fields_on_removed_records),
        },
        "source_values_retained": False,
        "source_identifiers_emitted": False,
        "silver_generated": False,
        "publication_performed": False,
        "semantics_accepted": False,
        "m109_accepted": False,
        "boundary": (
            "Aggregate structural/content comparison only. It does not establish "
            "field-semantic continuity, temporal meaning, Silver admission, "
            "rights for derived products, or M-109 acceptance."
        ),
    }
    core = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["comparison_sha256"] = hashlib.sha256(core).hexdigest()
    report["comparison_byte_count"] = len(core)
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


def _validate_harvest_receipt(
    era: ReleaseIdentity, receipt_bytes: bytes
) -> None:
    if (
        hashlib.sha256(receipt_bytes).hexdigest()
        != era["harvest_receipt_sha256"]
    ):
        raise ValueError(
            f"{era['source_era']} harvest receipt differs from pinned sidecar identity"
        )
    receipt = TypeAdapter(dict[str, object]).validate_json(receipt_bytes)
    expected: dict[str, object] = {
        "schema_id": "global-medicines-atlas.australian-harvest-receipt",
        "schema_version": 1,
        "source_id": "au-mbs",
        "category": "monthly_schedule_xml",
        "source_url": era["official_uri"],
        "final_url": era["official_uri"],
        "archive_path": era["archive_path"],
        "sha256": era["sha256"],
        "byte_count": era["byte_count"],
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError(
            f"{era['source_era']} harvest receipt identity is not approved"
        )


def compare(*, exact_commit: str) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError(
            "MBS source bytes may be processed only in GitHub Actions"
        )
    _exact_commit(exact_commit)
    hosts = (*HOSTS, "www.mbsonline.gov.au")
    policy = AcquisitionPolicy(
        allowed_hosts=hosts,
        timeout_seconds=60,
        max_bytes=MAX_BYTES,
        max_attempts=1,
        max_redirects=3,
    )
    base = (
        f"https://huggingface.co/datasets/{DATASET}/resolve/{ARCHIVE_REVISION}/"
    )
    july_archive = base + JULY["archive_path"]
    august_archive = base + AUGUST["archive_path"]
    july_sidecar = base + JULY["harvest_receipt_path"]
    august_sidecar = base + AUGUST["harvest_receipt_path"]
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(60),
        trust_env=False,
        max_redirects=policy.max_redirects,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        july_sidecar_bytes = _fetch(client, july_sidecar)
        august_sidecar_bytes = _fetch(client, august_sidecar)
        _validate_harvest_receipt(JULY, july_sidecar_bytes)
        _validate_harvest_receipt(AUGUST, august_sidecar_bytes)
        july_payload = _fetch(client, july_archive)
        august_payload = _fetch(client, august_archive)
        july_official = _fetch(client, JULY["official_uri"])
        august_official = _fetch(client, AUGUST["official_uri"])
    return compare_releases(
        july_payload=july_payload,
        august_payload=august_payload,
        july_official_payload=july_official,
        august_official_payload=august_official,
        compared_at=datetime.now(UTC),
        exact_commit=exact_commit,
    )


def _incomplete_report(
    *, exact_commit: str, compared_at: datetime, error: Exception
) -> dict[str, Any]:
    failure_class = (
        "source_endpoint_unavailable"
        if isinstance(error, httpx.HTTPError)
        else "identity_or_structure_mismatch"
    )
    return {
        "schema_id": "global-medicines-atlas.mbs-predecessor-comparison",
        "schema_version": 1,
        "status": "incomplete",
        "exact_commit": exact_commit,
        "compared_at": compared_at.astimezone(UTC).isoformat(),
        "failure_class": failure_class,
        "releases": [
            {
                "source_era": era["source_era"],
                "release_id": era["release_id"],
                "archive_revision": ARCHIVE_REVISION,
                "archive_path": era["archive_path"],
                "official_source_uri": era["official_uri"],
                "official_download_page": era["official_page"],
                "sha256": era["sha256"],
                "byte_count": era["byte_count"],
                "harvest_receipt_sha256": era["harvest_receipt_sha256"],
                "rights_reference": era["rights_reference"],
                "verification_complete": False,
            }
            for era in (JULY, AUGUST)
        ],
        "source_values_retained": False,
        "source_identifiers_emitted": False,
        "silver_generated": False,
        "publication_performed": False,
        "semantics_accepted": False,
        "m109_accepted": False,
        "retry_guidance": (
            "Retry only after an endpoint/transport change or a diagnosed "
            "transient condition; do not infer equality from missing data."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = compare(exact_commit=args.exact_commit)
        exit_code = 0
    except (httpx.HTTPError, SyntaxError, ValueError) as error:
        report = _incomplete_report(
            exact_commit=args.exact_commit,
            compared_at=datetime.now(UTC),
            error=error,
        )
        exit_code = 1
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
