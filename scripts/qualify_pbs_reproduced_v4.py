"""Validate exact PBS publication receipt inputs for later v4 qualification.

Matching fields alone do not authenticate a hosted artifact or admit a product.
The caller must independently retain and authenticate the Actions evidence and
close all configured receipt roles before invoking the shared admission gate.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

from scripts import prepare_pbs_reproduced_delivery as candidate

from global_medicines_atlas.strict_json import unique_json_object

MAX_RECEIPT_BYTES = 64 * 1024


def validate_publication_receipt(
    raw: bytes, *, workflow_commit: str, run_id: str, run_attempt: str
) -> dict[str, Any]:
    """Validate the exact output binding without conferring admission authority."""
    if len(raw) > MAX_RECEIPT_BYTES:
        raise ValueError("PBS publication receipt exceeds its bound")
    if (
        re.fullmatch(r"[0-9a-f]{40}", workflow_commit) is None
        or re.fullmatch(r"[1-9][0-9]*", run_id) is None
        or run_attempt != "1"
    ):
        raise ValueError("PBS publication run identity is invalid")
    parsed: Any = json.loads(raw, object_pairs_hook=unique_json_object)
    if not isinstance(parsed, dict):
        raise TypeError("PBS publication receipt must be an object")
    document = cast("dict[str, Any]", parsed)
    expected = {
        "schema_id": "global-medicines-atlas.pbs-silver-publication-receipt",
        "status": "anonymous_verification_passed_not_admitted",
        "dataset": candidate.DATASET,
        "parent_revision": candidate.PUBLIC_PARENT_REVISION,
        "path": f"silver/pbs/v4/2026-04-01/{candidate.OUTPUT_ID}/values.parquet",
        "sha256": candidate.PARQUET_SHA256,
        "bytes": candidate.PARQUET_BYTES,
        "prior_file_count": 9,
        "prior_file_blobs_preserved": True,
        "anonymous_digest_verification": "passed",
        "v4_admission_performed": False,
        "workflow_commit": workflow_commit,
        "run_id": run_id,
        "run_attempt": run_attempt,
    }
    if any(
        type(document.get(key)) is not type(value) or document.get(key) != value
        for key, value in expected.items()
    ):
        raise ValueError(
            "PBS publication receipt does not bind the exact output"
        )
    revision = document.get("revision")
    if (
        not isinstance(revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
    ):
        raise ValueError("PBS publication receipt revision is not immutable")
    return document
