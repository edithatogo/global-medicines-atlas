"""Offline validation for the approved fourteen-object rights supplement.

This module performs no I/O or publication. A hosted runner must independently
verify the complete public inventory, enforce CAS, and persist readback proof.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, cast

from global_medicines_atlas.federation_metadata_append import ObjectDigest

BASE = "quality/qualifications/"
DECISION_PATH = (
    BASE
    + "australian-mbs-utilisation-exact-scope-rights-decision-20261004.json"
)
JOIN_PATH = BASE + "australian-m112-receipt-sidecar-join-audit-20260930.json"
PAYLOAD_PATH = (
    BASE + "australian-mbs-utilisation-object-rights-metadata-20261004.json"
)
DECISION_SHA = (
    "3b6e03a483be822b7ea3cf82ed48ff9d7c360fbc3b813512c39f2143afb47b13"
)
JOIN_SHA = "53e7a1659f57f24290dfe08e534131dde59e930ff386655cf0fa047a0dae657b"
DATASET = "edithatogo/australian-mbs-utilisation-archive"
LIMIT = 1024 * 1024
COHORT_SIZE = 14


@dataclass(frozen=True)
class RightsAppendPayload:
    """Validated addition and required source identities, without live proof."""

    dataset: str
    source_revision: str
    parent_revision: str
    addition: ObjectDigest
    payload: bytes
    required_objects: tuple[tuple[str, str], ...]


def _document(payload: bytes) -> dict[str, Any]:
    if type(payload) is not bytes or not 0 < len(payload) <= LIMIT:
        raise ValueError("metadata byte bound exceeded")
    result = json.loads(payload)
    if not isinstance(result, dict):
        raise TypeError("metadata must be an object")
    return cast("dict[str, Any]", result)


def _require(actual: Any, expected: Any) -> None:
    # Compare JSON types too: True must not stand in for an integer schema.
    if json.dumps(actual, sort_keys=True) != json.dumps(
        expected, sort_keys=True
    ):
        raise ValueError("rights append contract differs from approved scope")


def validate_rights_append(
    contract: dict[str, Any],
    payload: bytes,
    decision_bytes: bytes,
    join_bytes: bytes,
) -> RightsAppendPayload:
    """Validate the exact approved cohort before any hosted side effect.

    Approval and join digests are pinned deliberately: new source scope needs
    a separately reviewed implementation. A newer reviewed CAS parent may be
    used while retaining the original source revision as provenance.
    """
    decision = _document(decision_bytes)
    joins = _document(join_bytes)
    metadata = _document(payload)
    _require(hashlib.sha256(decision_bytes).hexdigest(), DECISION_SHA)
    _require(hashlib.sha256(join_bytes).hexdigest(), JOIN_SHA)
    decision_ref = {"path": DECISION_PATH, "sha256": DECISION_SHA}
    join_ref = {"path": JOIN_PATH, "sha256": JOIN_SHA}
    scope = decision["scope"]
    source = next(row for row in joins["datasets"] if row["dataset"] == DATASET)
    _require(
        contract["schema_id"],
        "global-medicines-atlas.australian-mbs-utilisation-rights-append-contract",
    )
    _require(contract["schema_version"], 1)
    _require(contract["status"], "prepared_not_executed")
    _require(
        metadata["schema_id"],
        "global-medicines-atlas.australian-mbs-utilisation-object-rights-metadata",
    )
    _require(metadata["schema_version"], 1)
    _require(metadata["status"], "prepared_not_published")
    for document in (contract, metadata):
        _require(document["dataset"], DATASET)
        _require(document["source_revision"], scope["revision"])
        _require(document["rights_decision"], decision_ref)
    _require(contract["source_manifest_sha256"], scope["manifest_sha256"])
    _require(metadata["manifest_sha256"], scope["manifest_sha256"])
    _require(metadata["receipt_join_audit"], join_ref)
    for key in (
        "historical_receipts_modified",
        "complete_b1_b2_lineage",
        "v4_admission",
        "consumer_canaries",
    ):
        _require(metadata[key], expected=False)
    parent = contract["expected_parent_revision"]
    if type(parent) is not str or re.fullmatch(r"[0-9a-f]{40}", parent) is None:
        raise ValueError("CAS parent must be an exact revision")
    _require(contract["parent_readback"]["revision"], parent)
    _require(contract["parent_readback"]["private"], expected=False)
    _require(contract["parent_readback"]["gated"], expected=False)
    digest = hashlib.sha256(payload).hexdigest()
    path = f"metadata/rights/mbs-utilisation/{digest}.json"
    _require(
        contract["addition"],
        {
            "local_path": PAYLOAD_PATH,
            "path": path,
            "sha256": digest,
            "byte_count": len(payload),
        },
    )
    _require(
        contract["execution_controls"],
        {
            "origin": "github_actions_only",
            "environment": "australian-hf-publication",
            "exact_reviewed_main_commit_required": True,
            "parent_compare_and_swap_required": True,
            "durable_intent_before_write": True,
            "allowed_operations": ["add_exact_metadata_object"],
            "historical_overwrite_allowed": False,
            "raw_source_acquisition_allowed": False,
        },
    )
    _require(
        contract["verification"],
        {
            "expected_inventory_delta": {
                "added": [path],
                "removed": [],
                "modified": [],
            },
            "anonymous_all_object_digest_readback": True,
            "durable_receipt_before_cleanup": True,
            "preserve_failed_published_revision": True,
        },
    )
    _require(
        contract["recovery"],
        {
            "retry_after_ambiguous_write": "read_back_and_reconcile_before_any_new_write",
            "parent_drift": "stop_and_prepare_a_new_reviewed_contract",
        },
    )
    _require(
        contract["completion_claims"],
        dict.fromkeys(
            (
                "external_publication_performed",
                "complete_b1_b2_lineage",
                "v4_admission",
                "consumer_canaries",
                "m112_federation_accepted",
            ),
            False,
        ),
    )
    required = _validate_records(
        metadata, source, decision["disposition"], decision_ref
    )
    return RightsAppendPayload(
        DATASET,
        scope["revision"],
        parent,
        ObjectDigest(path, len(payload), digest),
        payload,
        tuple(sorted(required.items())),
    )


def _validate_records(
    metadata: dict[str, Any],
    source: dict[str, Any],
    disposition: dict[str, Any],
    decision_ref: dict[str, str],
) -> dict[str, str]:
    expected = {row["path"]: row for row in source["joined_objects"]}
    records = metadata["records"]
    if type(records) is not list:
        raise TypeError("rights records must be a list")
    records = cast("list[dict[str, Any]]", records)
    if len(records) != COHORT_SIZE:
        raise ValueError("exact fourteen-object cohort required")
    observed: set[str] = set()
    required = {source["manifest_path"]: source["manifest_sha256"]}
    for row in records:
        native = expected.get(row["path"])
        if native is None or row["path"] in observed:
            raise ValueError("unknown or duplicate rights object")
        observed.add(row["path"])
        for key in (
            "path",
            "source_id",
            "category",
            "sha256",
            "byte_count",
            "receipt_path",
            "receipt_sha256",
        ):
            _require(row[key], native[key])
        _require(row["rights_state"], "maintainer-approved-exact-object")
        _require(row["reuse"], disposition)
        _require(row["approval_record"], decision_ref)
        _require(row["recorded_at"], metadata["recorded_at"])
        required[row["path"]] = row["sha256"]
        required[row["receipt_path"]] = row["receipt_sha256"]
    return required
