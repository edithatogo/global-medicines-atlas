"""Append four digest-approved historical public reports from Actions only.

Source bytes travel as a bounded dispatch input, never as Git objects. The
committed allowlist binds every byte before any staging or Hub operation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import zlib
from pathlib import Path
from typing import Any, cast

from scripts.harvest_australian_pbs_utilisation import (
    DATASET,
    publish_to_huggingface,
)

from global_medicines_atlas.australian_harvesting import (
    DiscoveredHarvestResource,
    HarvestStageResult,
    build_harvest_manifest,
    stage_harvest_payload,
)

CONTRACT = Path("quality/qualifications/pbs-public-exports-20261105.json")
MAX_ENCODED = 60_000
MAX_EXPANDED = 2_000_000


def decode_bundle(encoded: str, approved: dict[str, Any]) -> dict[str, bytes]:
    """Reject oversized, incomplete, altered or unapproved input before writes."""
    if len(encoded) > MAX_ENCODED:
        raise ValueError("Public export input exceeds bound")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    raw = decoder.decompress(
        base64.b64decode(encoded, validate=True), MAX_EXPANDED + 1
    )
    if len(raw) > MAX_EXPANDED or not decoder.eof or decoder.unused_data:
        raise ValueError("Public export expansion exceeds bound or is invalid")
    if not raw.lstrip().startswith(b"{"):
        raise ValueError("Public export must be an object")
    pairs = cast(
        "list[tuple[str, str]]", json.loads(raw, object_pairs_hook=list)
    )
    payloads = dict(pairs)
    if len(payloads) != len(pairs) or set(payloads) != set(approved):
        raise ValueError("Public export file set differs from approval")
    result: dict[str, bytes] = {}
    for name, value in payloads.items():
        content = value.encode("latin1")
        expected = approved[name]
        if (
            len(content) != expected["bytes"]
            or hashlib.sha256(content).hexdigest() != expected["sha256"]
        ):
            raise ValueError("Public export content differs from approval")
        result[name] = content
    return result


def main() -> None:
    """Publish only the reviewed exact cohort and retain anonymous readback."""
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
    ):
        raise PermissionError("Public export publication requires Actions main")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract["dataset"] != DATASET:
        raise ValueError("Public export target mismatch")
    payloads = decode_bundle(
        os.environ["PUBLIC_EXPORT_BUNDLE"], contract["files"]
    )
    stage_dir = Path("build/harvest/public-exports")
    stages: list[HarvestStageResult] = []
    for name, content in payloads.items():
        digest = contract["files"][name]["sha256"]
        resource = DiscoveredHarvestResource(
            source_id="au-pbs-public-query-export",
            category="historical_public_aggregate_query_export",
            url=contract["source_url"],
            filename=name,
            archive_path=f"raw/pbs/utilisation/query-exports/{digest}/{name}",
            period_label="See original report requested processing period",
        )
        stage = stage_harvest_payload(
            resource,
            stage_dir,
            lambda _url, data=content: data,
            allowed_domains=frozenset({"data.gov.au"}),
        )
        receipt = json.loads(
            stage.staged_receipt_path.read_text(encoding="utf-8")
        )
        receipt["provenance_limitation"] = contract["provenance"]
        receipt["source_url_role"] = "publisher dataset landing page only"
        receipt["retrieved_at_role"] = "hosted custodial-copy materialization"
        stage.staged_receipt_path.write_text(
            json.dumps(receipt, indent=2), encoding="utf-8"
        )
        stages.append(stage)
    manifest = build_harvest_manifest(DATASET, stages)
    revision, final = publish_to_huggingface(
        stages, manifest, stage_dir, os.environ["HF_TOKEN"]
    )
    receipt = {
        "dataset": DATASET,
        "revision": revision,
        "workflow_commit": os.environ["GITHUB_SHA"],
        "anonymous_digest_verification": "passed",
        "new_public_reports": len(stages),
        "verified_file_count": final["file_count"],
        "participant_files_published": 0,
        "temporary_source_bytes_removed": False,
    }
    Path("build/pbs-utilisation-harvest-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
