"""Exact offline lifecycle validation and Actions-only publication.

The reviewed contract, bundle and prior hosted receipt are pinned deliberately.
Any changed metadata or parent requires a separately reviewed implementation;
this is not a general-purpose uploader or a grant of processing admission.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from .federation_metadata_append import ObjectDigest
from .federation_metadata_hosted import MetadataHub, require_hosted_main
from .mbs_utilisation_rights_append import LIMIT, RightsAppendPayload
from .mbs_utilisation_rights_hosted import execute_validated_append

CONTRACT_PATH = "quality/qualifications/australian-mbs-utilisation-lifecycle-append-contract-20261004.json"
PAYLOAD_PATH = "quality/qualifications/australian-mbs-utilisation-lifecycle-bundle-20261004.json"
BASELINE_PATH = "quality/qualifications/australian-mbs-utilisation-rights-publication-receipt-20261004.json"
CONTRACT_SHA = (
    "8357c6432da2029561d2661696afce198c74bb1834976d49640ba26090f45012"
)
PAYLOAD_SHA = "3eff9522a7558116fa64061e9394d9a33dec3e3e1a72981053ea243d9f56d310"
BASELINE_SHA = (
    "b321f3cdee645e8d80a825201aff6242847cbcbdad7100474ba762816874e426"
)


def _reviewed_bytes(payload: bytes, digest: str) -> None:
    if (
        type(payload) is not bytes
        or not 0 < len(payload) <= LIMIT
        or hashlib.sha256(payload).hexdigest() != digest
    ):
        raise ValueError("input bytes differ from reviewed lifecycle scope")


def validate_lifecycle_append(
    contract: dict[str, Any], payload: bytes, baseline_receipt: bytes
) -> RightsAppendPayload:
    """Validate exact reviewed bytes before any transport or credential use."""
    canonical = json.dumps(
        contract, sort_keys=True, separators=(",", ":")
    ).encode()
    _reviewed_bytes(canonical, CONTRACT_SHA)
    _reviewed_bytes(payload, PAYLOAD_SHA)
    _reviewed_bytes(baseline_receipt, BASELINE_SHA)
    receipt = json.loads(baseline_receipt)
    verified = next(
        row["document"]
        for row in receipt["hosted_receipts"]
        if row["document"]["status"] == "anonymously_verified"
    )
    if verified["revision"] != contract["expected_parent_revision"]:
        raise ValueError("reviewed baseline revision diverges")
    objects = tuple(
        (row["path"], row["sha256"]) for row in verified["observed"]
    )
    addition = contract["addition"]
    return RightsAppendPayload(
        contract["dataset"],
        contract["source_revision"],
        contract["expected_parent_revision"],
        ObjectDigest(addition["path"], len(payload), PAYLOAD_SHA),
        payload,
        tuple(sorted(objects)),
        tuple(
            ObjectDigest(row["path"], row["byte_count"], row["sha256"])
            for row in verified["observed"]
        ),
    )


def execute_lifecycle_append(
    contract: dict[str, Any],
    payload: bytes,
    baseline_receipt: bytes,
    *,
    exact_commit: str,
    current_main: Callable[[], str],
    hub: MetadataHub,
    persist: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    """Execute only the exact lifecycle bundle from protected main Actions."""
    require_hosted_main(exact_commit)
    validated = validate_lifecycle_append(contract, payload, baseline_receipt)
    return execute_validated_append(
        validated,
        contract["rights_decision"],
        receipt_schema="global-medicines-atlas.mbs-utilisation-lifecycle-append",
        exact_commit=exact_commit,
        current_main=current_main,
        hub=hub,
        persist=persist,
    )
