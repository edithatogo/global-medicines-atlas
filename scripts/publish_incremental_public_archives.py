"""Publish a committed batch chain and retain an anonymous proof per batch."""

from __future__ import annotations

import copy
import importlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from scripts.publish_mbs_public_exports import require_hosted
from scripts.publish_remaining_public_archives import publish

CONTRACT = Path(
    "quality/qualifications/incremental-public-archives-20261106.json"
)
CHECKPOINTS = Path("build/incremental-public")
MAX_BATCH_FILES = 20
MAX_BATCH_BYTES = 64 * 1024**2
MAX_BATCH_STEPS = 6


def batch_expectation(
    archive: dict[str, Any],
    index: int,
    prior: dict[str, Any] | None,
) -> dict[str, Any]:
    """Bind a batch to the approved baseline or this run's preceding proof."""
    if not 1 <= index <= len(archive["batches"]):
        raise ValueError("Batch index outside committed inventory")
    expected = copy.deepcopy(archive)
    batch = archive["batches"][index - 1]
    if (
        not batch["files"]
        or len(batch["files"]) > MAX_BATCH_FILES
        or any("draft_transport" not in f for f in batch["files"])
        or (
            len(batch["files"]) > 1
            and sum(f["bytes"] for f in batch["files"]) > MAX_BATCH_BYTES
        )
    ):
        raise ValueError("Committed batch exceeds incremental profile")
    if index == 1:
        if prior is not None:
            raise ValueError("First batch cannot substitute another parent")
    else:
        required_proof: dict[str, Any] = {
            "batch_id": archive["batches"][index - 2]["id"],
            "dataset": archive["dataset"],
            "workflow_commit": os.environ["GITHUB_SHA"],
            "workflow_run": os.environ["GITHUB_RUN_ID"],
            "anonymous_digest_verification": "passed",
            "run_coverage": {
                "coverage_status": "complete",
                "failed_resources": [],
            },
            "new_payloads": len(archive["batches"][index - 2]["files"]),
        }
        if (
            prior is None
            or any(prior.get(k) != v for k, v in required_proof.items())
            or prior.get("temporary_source_bytes_removed") is not True
            or not prior.get("manifest_sha256")
            or not prior.get("revision")
        ):
            raise RuntimeError("Prior exact-run batch proof missing or invalid")
        expected["parent_revision"] = prior["revision"]
        expected["manifest_sha256"] = prior["manifest_sha256"]
        expected["prior_verification_run"] = [
            *archive["prior_verification_run"],
            int(os.environ["GITHUB_RUN_ID"]),
        ]
    expected["files"] = batch["files"]
    return expected


def execute_batch(sdk: Any, index: int) -> dict[str, Any]:
    """Verify each append before cleanup and before advancing its parent."""
    require_hosted()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    destination = os.environ["PUBLIC_ARCHIVE_DESTINATION"]
    if contract.get("external_publication_authorized") is not True:
        raise PermissionError("Incremental public publication not authorized")
    archive = contract["archives"][destination]
    if archive["dataset"] != (
        f"edithatogo/australian-{destination}-utilisation-archive"
    ):
        raise ValueError("Incremental destination differs from review")
    if index > len(archive["batches"]):
        return {"status": "not applicable", "batch_index": index}
    prior = None
    if index > 1:
        prior = json.loads(
            (CHECKPOINTS / f"verification-{index - 1}.json").read_text(
                encoding="utf-8"
            )
        )
    expected = batch_expectation(archive, index, prior)
    cache = Path(os.environ["HF_HOME"])
    if (
        cache.resolve()
        != (Path.cwd() / f"build/{destination}-util-hf-home").resolve()
    ):
        raise ValueError("Incremental cache differs from workflow scope")
    receipt = publish(sdk, expected, Path("build/harvest/remaining-public"))
    if (
        receipt["new_payloads"] != len(expected["files"])
        or receipt["anonymous_digest_verification"] != "passed"
        or receipt["run_coverage"]["coverage_status"] != "complete"
        or not receipt.get("manifest_sha256")
    ):
        raise RuntimeError("Batch did not acquire and verify its exact cohort")
    receipt.update(
        batch_id=archive["batches"][index - 1]["id"],
        batch_index=index,
        incremental_total_new_payloads=sum(
            len(b["files"]) for b in archive["batches"][:index]
        ),
    )
    # Preserve a pre-cleanup proof if cleanup fails. The workflow retains
    # this directory even on a later failure, without promoting the next batch.
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    checkpoint = CHECKPOINTS / f"verification-{index}.json"
    checkpoint.write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    for target in (
        Path("build/harvest"),
        cache,
    ):
        if target.exists():
            shutil.rmtree(target)
    receipt["temporary_source_bytes_removed"] = True
    checkpoint.write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    final_receipt = Path(
        f"build/{destination}-utilisation-harvest-receipt.json"
    )
    final_receipt.parent.mkdir(parents=True, exist_ok=True)
    final_receipt.write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    """Keep developer machines outside the native publication origin."""
    require_hosted()
    index = int(os.environ["PUBLIC_BATCH_INDEX"])
    if not 1 <= index <= MAX_BATCH_STEPS:
        raise ValueError("Incremental step index outside fixed workflow")
    sdk = importlib.import_module("huggingface_hub")
    receipt = execute_batch(sdk, index)
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as out:
        out.write(
            "applied="
            + str(receipt.get("status") != "not applicable").lower()
            + "\n"
        )
    print(
        json.dumps({
            key: receipt[key]
            for key in ("batch_id", "new_payloads", "revision", "status")
            if key in receipt
        }),
        flush=True,
    )


if __name__ == "__main__":
    main()
