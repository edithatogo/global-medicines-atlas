"""Hosted-only orchestration for the exact MBS rights metadata append.

Transports supply anonymous all-object observations and server-enforced CAS.
Failures propagate without rollback or automatic retries. An ambiguous write
requires separate durable-receipt reconciliation before any subsequent write.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from global_medicines_atlas.federation_metadata_append import (
    MAX_OBJECTS,
    MetadataAppend,
    ObjectDigest,
)
from global_medicines_atlas.federation_metadata_hosted import (
    MAX_RECEIPT_CHARS,
    REPOSITORY,
    MetadataHub,
    PublicSnapshot,
    require_hosted_main,
)
from global_medicines_atlas.mbs_utilisation_rights_append import (
    validate_rights_append,
)


def _inventory(
    snapshot: PublicSnapshot, revision: str
) -> dict[str, ObjectDigest]:
    if (
        snapshot.revision != revision
        or snapshot.private is not False
        or snapshot.gated is not False
        or type(snapshot.objects) is not tuple
        or not 1 <= len(snapshot.objects) <= MAX_OBJECTS
    ):
        raise ValueError(
            "snapshot must be exact, bounded, public and non-gated"
        )
    result: dict[str, ObjectDigest] = {}
    for obj in snapshot.objects:
        if type(obj) is not ObjectDigest:
            raise TypeError("snapshot requires exact object identities")
        obj.__post_init__()
        if obj.path in result:
            raise ValueError("duplicate snapshot path")
        result[obj.path] = obj
    return result


def _persist(
    document: dict[str, Any], persist: Callable[[dict[str, Any]], str]
) -> str:
    if len(json.dumps(document, sort_keys=True)) > MAX_RECEIPT_CHARS:
        raise ValueError("durable receipt exceeds supported size")
    url = persist(json.loads(json.dumps(document)))
    if (
        type(url) is not str
        or re.fullmatch(
            rf"https://github.com/{re.escape(REPOSITORY)}/issues/340#issuecomment-[0-9]+",
            url,
        )
        is None
    ):
        raise ValueError("durable receipt URL missing or invalid")
    return url


def execute_rights_append(
    contract: dict[str, Any],
    payload: bytes,
    decision_bytes: bytes,
    join_bytes: bytes,
    *,
    exact_commit: str,
    current_main: Callable[[], str],
    hub: MetadataHub,
    persist: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    """Validate, durably record intent, CAS-add and anonymously verify.

    ``current_main`` must independently read the repository main head.
    ``persist`` must durably save and read back its exact public-safe document.
    No source cache is removed here; only a returned verification receipt may
    authorize the caller's cleanup. This function provides no v4 admission.
    """
    require_hosted_main(exact_commit)
    validated = validate_rights_append(
        contract, payload, decision_bytes, join_bytes
    )
    if current_main() != exact_commit:
        raise ValueError("reviewed main has advanced")
    before = hub.snapshot(validated.dataset, validated.parent_revision)
    baseline = _inventory(before, validated.parent_revision)
    if len(baseline) == MAX_OBJECTS:
        raise ValueError("snapshot has no capacity for metadata addition")
    for path, digest in validated.required_objects:
        if path not in baseline or baseline[path].sha256 != digest:
            raise ValueError(
                "baseline does not bind approved source identities"
            )
    if validated.addition.path in baseline:
        raise ValueError("metadata already exists; reconcile before retry")
    plan = MetadataAppend(
        validated.dataset,
        validated.parent_revision,
        tuple(sorted(baseline.values(), key=lambda obj: obj.path)),
        validated.addition,
        validated.payload,
    )
    if hub.head(plan.dataset) != plan.parent_revision:
        raise ValueError("default head drifted before intent")
    intent = {
        "schema_id": "global-medicines-atlas.mbs-utilisation-rights-append",
        "schema_version": 1,
        "status": "intent",
        "dataset": plan.dataset,
        "parent_revision": plan.parent_revision,
        "source_revision": validated.source_revision,
        "code_commit": exact_commit,
        "run_url": f"https://github.com/{REPOSITORY}/actions/runs/"
        + os.environ["GITHUB_RUN_ID"],
        "authorization": contract["rights_decision"],
        "addition": asdict(plan.addition),
        "baseline": [asdict(obj) for obj in plan.baseline],
    }
    # Fail before writing if the eventual public receipt would be too large.
    projected = {
        **intent,
        "status": "anonymously_verified",
        "revision": "f" * 40,
        "intent_url": "x" * 256,
        "parent_basis": "server_enforced_parent_commit",
        "observed": [asdict(obj) for obj in (*plan.baseline, plan.addition)],
        "private": False,
        "gated": False,
    }
    if len(json.dumps(projected, sort_keys=True)) > MAX_RECEIPT_CHARS:
        raise ValueError("durable receipt exceeds supported size")
    intent_url = _persist(intent, persist)
    if (
        current_main() != exact_commit
        or hub.head(plan.dataset) != plan.parent_revision
    ):
        raise ValueError("main or dataset head drifted after intent")
    revision = hub.append(plan)
    if (
        type(revision) is not str
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
        or revision == plan.parent_revision
    ):
        raise ValueError(
            "append returned invalid new revision; reconcile before retry"
        )
    acknowledgement = {
        **intent,
        "status": "cas_acknowledged",
        "revision": revision,
        "intent_url": intent_url,
        "parent_basis": "server_enforced_parent_commit",
    }
    _persist(acknowledgement, persist)
    after = hub.snapshot(plan.dataset, revision)
    observed = _inventory(after, revision)
    if observed != {**baseline, plan.addition.path: plan.addition}:
        raise ValueError("complete sibling inventory differs from exact append")
    if hub.metadata(plan.dataset, revision, plan.addition.path) != plan.payload:
        raise ValueError("anonymous metadata bytes differ")
    receipt = {
        **acknowledgement,
        "status": "anonymously_verified",
        "observed": [
            asdict(obj)
            for obj in sorted(observed.values(), key=lambda obj: obj.path)
        ],
        "private": False,
        "gated": False,
    }
    receipt_url = _persist(receipt, persist)
    return {**receipt, "receipt_url": receipt_url}
