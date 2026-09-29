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
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

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
from global_medicines_atlas.mbs_silver_qualification import (
    OFFICIAL_MBS_V3_URI,
    MbsSilverQualification,
    MbsSourceEraVerification,
    qualify_mbs_silver,
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
SOURCE_URI = (
    "https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/"
    "resolve/4d1dae488ac43522f20e8320a8b2a56bf9138341/"
    "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML"
)
RIGHTS_REFERENCE = (
    "https://github.com/edithatogo/global-medicines-atlas/issues/340"
)
MAX_BYTES = 9_000_000
MAX_METADATA_BYTES = 2_000_000
OFFICIAL_RELEASE_ID = "MBS-XML-20250701 Version 3"
OFFICIAL_RELEASED_AT = date(2025, 6, 16)
OFFICIAL_EFFECTIVE_AT = date(2025, 7, 1)
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
PUBLIC_V4_DATASET = "edithatogo/australian-mbs-source-archive"
PUBLIC_V4_PREFIX = "silver/mbs/v4/2025-07-v3"
PUBLIC_V4_OBJECT_COUNT = 9
PUBLICATION_RECEIPT_COMMENT = 5859624790
_PUBLIC_V4_TABLES = frozenset({
    "services.parquet",
    "hierarchy.parquet",
    "descriptions.parquet",
    "fees.parquet",
    "benefits.parquet",
    "caps.parquet",
})


def verify_public_v4_identity(
    report: MbsSilverQualification,
    *,
    current_revision: str,
    manifest_bytes: bytes,
    qualification_bytes: bytes,
    source_receipt_bytes: bytes,
    tree_entries: list[dict[str, Any]],
    publication_receipt: dict[str, Any],
) -> dict[str, object]:
    """Bind the public candidate to its anonymous receipt and exact tables."""
    if len(current_revision) != GIT_SHA1_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in current_revision
    ):
        raise ValueError("public dataset revision is invalid")
    manifest = _json_object(manifest_bytes, "public v4 manifest")
    qualification_document = _json_object(
        qualification_bytes, "public v4 qualification"
    )
    source_receipt = _json_object(source_receipt_bytes, "public B1 receipt")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    publication_revision = _validate_public_manifest_receipt(
        manifest, publication_receipt, manifest_sha256
    )
    _validate_public_source(report, manifest, source_receipt)
    _validate_public_qualification(report, manifest, qualification_document)
    verified_object_count = _validate_public_object_inventory(
        manifest,
        manifest_bytes,
        qualification_bytes,
        source_receipt_bytes,
        tree_entries,
        publication_receipt,
    )

    return {
        "status": "verified",
        "dataset": PUBLIC_V4_DATASET,
        "publication_revision": publication_revision,
        "current_revision": current_revision,
        "prefix": PUBLIC_V4_PREFIX,
        "manifest_sha256": manifest_sha256,
        "source_sha256": report.source_sha256,
        "verified_object_count": verified_object_count,
        "table_count": len(_PUBLIC_V4_TABLES),
        "projection_denominator_matches_public_v4": True,
        "candidate_only": True,
    }


def _validate_public_manifest_receipt(
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    manifest_sha256: str,
) -> str:
    """Require the expected immutable dataset, manifest and receipt."""
    checks = (
        manifest.get("schema_id")
        != "global-medicines-atlas.mbs-silver-v4-manifest",
        manifest.get("schema_version") != 1,
        manifest.get("dataset") != PUBLIC_V4_DATASET,
        manifest.get("destination_prefix") != PUBLIC_V4_PREFIX,
        manifest.get("candidate_only") is not True,
        receipt.get("dataset") != PUBLIC_V4_DATASET,
        receipt.get("candidate_only") is not True,
        receipt.get("anonymous_digest_verification") != "passed",
        receipt.get("manifest_sha256") != manifest_sha256,
    )
    if any(checks):
        raise ValueError("public v4 manifest or publication receipt differs")
    revision = receipt.get("revision")
    if not isinstance(revision, str):
        raise TypeError("public v4 publication revision is not a string")
    if len(revision) != GIT_SHA1_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise ValueError("public v4 publication revision is invalid")
    return revision


def _validate_public_source(
    report: MbsSilverQualification,
    manifest: dict[str, Any],
    source_receipt: dict[str, Any],
) -> None:
    """Bind the public B1 receipt and manifest to the source candidate."""
    source = manifest.get("source")
    payload = source_receipt.get("payload")
    receipt_source = source_receipt.get("source")
    if not all(
        isinstance(item, dict) for item in (source, payload, receipt_source)
    ):
        raise TypeError("public v4 source identity is malformed")
    source = cast("dict[str, Any]", source)
    payload = cast("dict[str, Any]", payload)
    receipt_source = cast("dict[str, Any]", receipt_source)
    parsed_receipt = SourceReceipt.model_validate(source_receipt)
    checks = (
        source.get("source_id") != report.source_id,
        source.get("sha256") != report.source_sha256,
        source.get("byte_count") != report.source_byte_count,
        source.get("receipt_sha256") != parsed_receipt.digest(),
        payload.get("sha256") != report.source_sha256,
        payload.get("byte_count") != report.source_byte_count,
        receipt_source.get("source_id") != report.source_id,
        source_receipt.get("rights_state") != "permitted",
    )
    if any(checks):
        raise ValueError("public v4 B1 source or receipt identity differs")


def _validate_public_qualification(
    report: MbsSilverQualification,
    manifest: dict[str, Any],
    qualification_document: dict[str, Any],
) -> MbsSilverQualification:
    """Verify the embedded report and compare deterministic denominators."""
    public_qualification = qualification_document.get("qualification")
    checks = (
        qualification_document.get("schema_id")
        != "global-medicines-atlas.mbs-silver-qualification",
        qualification_document.get("schema_version") != 1,
        qualification_document.get("candidate_only") is not True,
        qualification_document.get("field_count") != report.field_count,
        qualification_document.get("field_occurrence_count")
        != report.field_occurrence_count,
    )
    if any(checks):
        raise ValueError("public v4 qualification identity differs")
    if not isinstance(public_qualification, dict):
        raise TypeError("public v4 qualification is not an object")
    public_report = MbsSilverQualification.model_validate(public_qualification)
    if (
        manifest.get("qualification_sha256")
        != public_report.qualification_sha256
    ):
        raise ValueError("public v4 qualification digest differs")
    if _comparable_qualification(public_report) != _comparable_qualification(
        report
    ):
        raise ValueError("public v4 candidate denominator differs")
    return public_report


def _validate_public_object_inventory(
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    qualification_bytes: bytes,
    source_receipt_bytes: bytes,
    tree_entries: list[dict[str, Any]],
    publication_receipt: dict[str, Any],
) -> int:
    """Match all object sizes and digests to the receipt and public tree."""
    expected_manifest_path = f"{PUBLIC_V4_PREFIX}/manifest.json"
    receipt_objects = publication_receipt.get("verified_objects")
    manifest_objects = manifest.get("objects")
    if not isinstance(receipt_objects, list) or not isinstance(
        manifest_objects, list
    ):
        raise TypeError("public v4 object inventory is malformed")
    receipt_objects = cast("list[Any]", receipt_objects)
    manifest_objects = cast("list[Any]", manifest_objects)
    receipt_inventory = _object_inventory(receipt_objects)
    manifest_inventory = _object_inventory(manifest_objects)
    expected_paths = {
        f"{PUBLIC_V4_PREFIX}/{name}"
        for name in (
            *_PUBLIC_V4_TABLES,
            "qualification.json",
            "source-receipt.json",
            "manifest.json",
        )
    }
    expected_manifest_children = set(receipt_inventory) - {
        expected_manifest_path
    }
    inventories_match = set(manifest_inventory) == expected_manifest_children
    object_hashes_match = all(
        manifest_inventory[path] == receipt_inventory[path]
        for path in manifest_inventory
    )
    if (
        len(receipt_inventory) != PUBLIC_V4_OBJECT_COUNT
        or set(receipt_inventory) != expected_paths
        or not inventories_match
        or not object_hashes_match
    ):
        raise ValueError("public v4 object inventory differs from receipt")
    _validate_metadata_object(
        receipt_inventory,
        expected_manifest_path,
        manifest_bytes,
    )
    _validate_metadata_object(
        receipt_inventory,
        f"{PUBLIC_V4_PREFIX}/qualification.json",
        qualification_bytes,
    )
    _validate_metadata_object(
        receipt_inventory,
        f"{PUBLIC_V4_PREFIX}/source-receipt.json",
        source_receipt_bytes,
    )
    tree_inventory = _tree_inventory(tree_entries)
    if set(tree_inventory) != set(receipt_inventory):
        raise ValueError("public v4 tree inventory differs from receipt")
    for path, (byte_count, sha256) in receipt_inventory.items():
        entry = tree_inventory[path]
        if path.endswith(".parquet"):
            lfs = entry.get("lfs")
            if not isinstance(lfs, dict):
                raise TypeError("public v4 table has no LFS identity")
            lfs = cast("dict[str, Any]", lfs)
            if (
                entry.get("size") != byte_count
                or lfs.get("size") != byte_count
                or lfs.get("oid") != sha256
            ):
                raise ValueError("public v4 object identity differs")
        elif entry.get("size") != byte_count:
            raise ValueError("public v4 metadata size differs")
    return len(receipt_inventory)


def _validate_metadata_object(
    inventory: dict[str, tuple[int, str]],
    path: str,
    payload: bytes,
) -> None:
    """Match fetched metadata bytes to their anonymous receipt digest."""
    actual = (len(payload), hashlib.sha256(payload).hexdigest())
    if inventory.get(path) != actual:
        raise ValueError("public v4 metadata object differs from receipt")


def _tree_inventory(
    entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Select unique objects beneath the versioned public product prefix."""
    prefix = f"{PUBLIC_V4_PREFIX}/"
    inventory: dict[str, dict[str, Any]] = {}
    for entry in entries:
        path = entry.get("path")
        if isinstance(path, str) and path.startswith(prefix):
            if path in inventory:
                raise ValueError("public v4 tree has duplicate object paths")
            inventory[path] = entry
    return inventory


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError(f"{label} is not a JSON object")
    return cast("dict[str, Any]", value)


def _object_inventory(
    objects: list[Any],
) -> dict[str, tuple[int, str]]:
    inventory: dict[str, tuple[int, str]] = {}
    for item in objects:
        if not isinstance(item, dict):
            raise TypeError("public v4 object inventory item is not an object")
        item = cast("dict[str, Any]", item)
        path = item.get("path")
        byte_count = item.get("byte_count")
        sha256 = item.get("sha256")
        if not isinstance(path, str):
            raise TypeError("public v4 object path is not a string")
        if type(byte_count) is not int:
            raise TypeError("public v4 object size is not an integer")
        if not isinstance(sha256, str):
            raise TypeError("public v4 object digest is not a string")
        invalid_values = (
            not path.startswith(f"{PUBLIC_V4_PREFIX}/"),
            byte_count < 1,
            not re.fullmatch(r"[0-9a-f]{64}", sha256),
            path in inventory,
        )
        if any(invalid_values):
            raise ValueError("public v4 object inventory is malformed")
        inventory[path] = (byte_count, sha256)
    return inventory


def _comparable_qualification(
    report: MbsSilverQualification,
) -> dict[str, Any]:
    """Ignore only per-run receipt and comparison-time identities."""
    values = report.model_dump(mode="json")
    values.pop("receipt_sha256")
    values.pop("qualification_sha256")
    era = values.get("source_era_verification")
    if isinstance(era, dict):
        cast("dict[str, Any]", era).pop("compared_at", None)
    return values


def _read_public_v4_identity(  # ruff: ignore[too-many-locals] - bounded metadata
    report: MbsSilverQualification,
) -> dict[str, object]:
    """Verify public v4 metadata and its receipt without fetching Parquet."""
    policy = AcquisitionPolicy(
        allowed_hosts=(*HOSTS, "api.github.com"),
        timeout_seconds=30,
        max_bytes=MAX_METADATA_BYTES,
        max_attempts=1,
        max_redirects=3,
    )
    base = "https://huggingface.co"
    dataset_api = f"{base}/api/datasets/{PUBLIC_V4_DATASET}"
    publication_path = f"{base}/api/datasets/{PUBLIC_V4_DATASET}/tree"
    github_receipt = (
        "https://api.github.com/repos/edithatogo/global-medicines-atlas/"
        f"issues/comments/{PUBLICATION_RECEIPT_COMMENT}"
    )
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(30),
        trust_env=False,
        max_redirects=policy.max_redirects,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        dataset = _fetch_json(client, dataset_api)
        if not isinstance(dataset, dict):
            raise TypeError("public MBS v4 dataset metadata is not an object")
        private = dataset.get("private")
        gated = dataset.get("gated")
        if (private is not False and private is not None) or (
            gated is not False and gated is not None
        ):
            raise ValueError("public MBS v4 dataset is no longer open")
        current_revision = dataset.get("sha")
        if not isinstance(current_revision, str):
            raise TypeError("public MBS v4 current revision is absent")
        tree_url = (
            f"{publication_path}/{current_revision}/{PUBLIC_V4_PREFIX}"
            "?recursive=true&expand=true&limit=100"
        )
        tree_value = _fetch_json(client, tree_url)
        if not isinstance(tree_value, list) or any(
            not isinstance(entry, dict) for entry in tree_value
        ):
            raise TypeError("public MBS v4 tree is malformed")
        tree_entries = cast("list[dict[str, Any]]", tree_value)
        manifest_bytes = _fetch_bytes(
            client,
            f"{base}/datasets/{PUBLIC_V4_DATASET}/resolve/"
            f"{current_revision}/{PUBLIC_V4_PREFIX}/manifest.json",
        )
        qualification_bytes = _fetch_bytes(
            client,
            f"{base}/datasets/{PUBLIC_V4_DATASET}/resolve/"
            f"{current_revision}/{PUBLIC_V4_PREFIX}/qualification.json",
        )
        source_receipt_bytes = _fetch_bytes(
            client,
            f"{base}/datasets/{PUBLIC_V4_DATASET}/resolve/"
            f"{current_revision}/{PUBLIC_V4_PREFIX}/source-receipt.json",
        )
        comment = _fetch_json(client, github_receipt)
    if not isinstance(comment, dict):
        raise TypeError("public MBS v4 receipt is not an object")
    if comment.get("id") != PUBLICATION_RECEIPT_COMMENT:
        raise ValueError("public MBS v4 receipt identity differs")
    body = comment.get("body")
    if not isinstance(body, str):
        raise TypeError("public MBS v4 receipt body is absent")
    publication_receipt = _json_object(body.encode(), "publication receipt")
    return verify_public_v4_identity(
        report,
        current_revision=current_revision,
        manifest_bytes=manifest_bytes,
        qualification_bytes=qualification_bytes,
        source_receipt_bytes=source_receipt_bytes,
        tree_entries=tree_entries,
        publication_receipt=publication_receipt,
    )


def _fetch_bytes(client: httpx.Client, url: str) -> bytes:
    """Read one bounded JSON/metadata object without following redirects."""
    chunks: list[bytes] = []
    byte_count = 0
    with client.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            byte_count += len(chunk)
            if byte_count > MAX_METADATA_BYTES:
                raise ValueError("public MBS metadata exceeds its byte limit")
            chunks.append(chunk)
    return b"".join(chunks)


def _fetch_json(client: httpx.Client, url: str) -> dict[str, Any] | list[Any]:
    """Decode a bounded public metadata response."""
    value = json.loads(_fetch_bytes(client, url))
    if not isinstance(value, (dict, list)):
        raise TypeError("public MBS metadata JSON shape differs")
    return cast("dict[str, Any] | list[Any]", value)


def qualify(  # ruff: ignore[too-many-locals] - hashes two sources in memory
    *, exact_commit: str, rows_per_batch: int = 1024
) -> dict[str, object]:
    """Restore the pinned public bytes anonymously and return safe evidence."""
    if len(exact_commit) != GIT_SHA1_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in exact_commit
    ):
        raise ValueError("exact commit must be a lowercase Git SHA-1")
    policy = AcquisitionPolicy(
        allowed_hosts=(*HOSTS, "www.mbsonline.gov.au"),
        timeout_seconds=60,
        max_bytes=MAX_BYTES,
        max_attempts=1,
        max_redirects=3,
    )
    chunks: list[bytes] = []
    byte_count = 0
    official_hash = hashlib.sha256()
    official_byte_count = 0
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
        with client.stream(
            "GET", OFFICIAL_MBS_V3_URI, follow_redirects=False
        ) as official_response:
            official_response.raise_for_status()
            for chunk in official_response.iter_bytes():
                official_byte_count += len(chunk)
                if official_byte_count > MAX_BYTES:
                    raise ValueError(
                        "official MBS source exceeds the parser byte limit"
                    )
                official_hash.update(chunk)
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
    official_sha256 = official_hash.hexdigest()
    release_matched = (
        official_byte_count == evidence.byte_count
        and official_sha256 == evidence.sha256
    )
    source_era_verification = (
        MbsSourceEraVerification(
            official_source_uri=AnyUrl(OFFICIAL_MBS_V3_URI),
            release_id=OFFICIAL_RELEASE_ID,
            released_at=OFFICIAL_RELEASED_AT,
            effective_at=OFFICIAL_EFFECTIVE_AT,
            official_source_sha256=official_sha256,
            official_source_byte_count=official_byte_count,
            compared_at=datetime.now(UTC),
        )
        if release_matched
        else None
    )
    report = qualify_mbs_silver(
        payload,
        receipt,
        date_format="mbs-dmy",
        rows_per_batch=rows_per_batch,
        source_era_verification=source_era_verification,
    )
    public_v4_identity = _read_public_v4_identity(report)
    resolved_blockers = (
        ("public_v4_identity_unverified",)
        if public_v4_identity.get("status") == "verified"
        else ()
    )
    current_blockers = tuple(
        blocker
        for blocker in report.blockers
        if blocker not in resolved_blockers
    )
    quality_diagnostics = _quality_diagnostics(
        payload, receipt, rows_per_batch=rows_per_batch
    )
    candidate_report = {
        "qualification": report.model_dump(mode="json"),
        "public_v4_identity": public_v4_identity,
        "resolved_blockers": list(resolved_blockers),
        "current_blockers": list(current_blockers),
        "quality_diagnostics": quality_diagnostics,
        "official_release_check": {
            "source_uri": OFFICIAL_MBS_V3_URI,
            "release_id": OFFICIAL_RELEASE_ID,
            "released_at": OFFICIAL_RELEASED_AT.isoformat(),
            "effective_at": OFFICIAL_EFFECTIVE_AT.isoformat(),
            "source_sha256": official_sha256,
            "source_byte_count": official_byte_count,
            "matched_pinned_archive": release_matched,
        },
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
            "memory. The existing public v4 candidate identity and all six "
            "table digests were independently reverified from metadata and "
            "the publication receipt. This aggregate remains candidate-only; "
            "it does not establish M-109 acceptance."
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
    amount_decimal_probe_ordinals: defaultdict[tuple[str, str], list[int]] = (
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
                        status != "invalid"
                        or (table, field_name) not in amount_fields
                    ):
                        continue
                    native_value = value["native_value"]
                    reason = _amount_invalid_reason(native_value)
                    amount_issue_ordinals[table, field_name, reason].append(
                        ordinal
                    )
                    if reason != "strict_numeric_grammar_mismatch":
                        continue
                    probe = _amount_decimal_probe(native_value)
                    amount_decimal_probe_ordinals[table, probe].append(ordinal)
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
        "invalid_amount_decimal_probe_source_ordinals": [
            {
                "table": table,
                "probe": probe,
                "source_ordinals": ordinals,
            }
            for (table, probe), ordinals in sorted(
                amount_decimal_probe_ordinals.items()
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


def _amount_decimal_probe(native_value: str) -> str:
    """Classify a strict-grammar mismatch without returning native text."""
    try:
        parsed = Decimal(native_value)
    except InvalidOperation:
        return "decimal_constructor_rejected"
    if not parsed.is_finite():
        return "non_finite_decimal"
    if native_value != native_value.strip():
        return "surrounding_whitespace"
    if "e" in native_value.lower():
        return "exponent_notation"
    if "_" in native_value:
        return "underscore_separator"
    return "other_finite_decimal_spelling"


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
