"""Validate the exact historical MBS cohort only in protected main Actions."""

# Fixed subprocess arrays use hosted PATH and never invoke a shell.
# ruff: file-ignore[subprocess-without-shell-equals-true]
from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from publish_mbs_utilisation_rights import current_main
from publish_source_metadata import HubTransport, persist_receipt

from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.mbs_utilisation_validation import (
    load_validation_cohort,
    validate_staged_payload,
    verify_staged_identity,
)

ROOT = Path(__file__).resolve().parents[1]
WORKER_SECONDS = 120
WORKER_MEMORY_BYTES = 2 * 1024 * 1024 * 1024
WORKER_ARGUMENT_COUNT = 4


def worker(index: int, path: Path) -> dict[str, Any]:
    """Isolate format parsing with Linux address-space and parent time limits."""
    require_hosted_main(os.environ.get("GITHUB_SHA", ""))
    if sys.platform != "linux":
        raise ValueError("hosted validation worker requires Linux")
    resource = importlib.import_module("resource")
    resource.setrlimit(
        resource.RLIMIT_AS, (WORKER_MEMORY_BYTES, WORKER_MEMORY_BYTES)
    )
    row = load_validation_cohort(ROOT)[index]
    if not row["validation_dispatch_eligible"]:
        raise ValueError("resource-held object cannot enter validation worker")
    reference = row["raw_reference"]
    try:
        verify_staged_identity(path, reference)
    except ValueError, OSError:
        return {"status": "identity_failed", "anonymous_digest_verified": False}
    try:
        checks = validate_staged_payload(path, reference)
    except ValueError, OSError, UnicodeError, MemoryError, EOFError, csv.Error:
        return {"status": "structure_failed", "anonymous_digest_verified": True}
    return {
        "status": "structure_verified",
        "anonymous_digest_verified": True,
        "checks": checks,
    }


def run_worker(index: int, path: Path) -> dict[str, Any]:
    """Kill a stalled parser and strip all credentials from its environment."""
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                str(index),
                str(path),
            ],
            env={
                key: value
                for key, value in os.environ.items()
                if key not in {"HF_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"}
            },
            timeout=WORKER_SECONDS,
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(completed.stdout)
    except subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError:
        return {
            "status": "worker_failed_or_timed_out",
            "anonymous_digest_verified": False,
        }
    if not isinstance(result, dict):
        raise TypeError("validation worker returned invalid result")
    result = cast("dict[str, Any]", result)
    if (
        result.get("status")
        not in {
            "identity_failed",
            "structure_failed",
            "structure_verified",
        }
        or type(result.get("anonymous_digest_verified")) is not bool
    ):
        raise ValueError("validation worker returned invalid result")
    if result["anonymous_digest_verified"] != (
        result["status"] != "identity_failed"
    ):
        raise ValueError("validation worker identity claim differs")
    return result


def main() -> None:
    """Persist each independent result before cleanup of verified raw bytes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    cohort = load_validation_cohort(ROOT)
    if current_main() != args.exact_commit:
        raise ValueError("reviewed main has advanced")
    receipts = ROOT / "build/mbs-utilisation-validation-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    cache = Path(tempfile.mkdtemp(prefix="gma-mbs-validation-"))
    hub = HubTransport(cache)
    hub.head(
        cohort[0]["raw_reference"]["dataset"]
    )  # Refuse private/gated datasets.
    observations: list[dict[str, Any]] = []
    for index, row in enumerate(cohort):
        reference = row["raw_reference"]
        target = None
        outcome: dict[str, Any] = {
            "status": "resource_hold",
            "anonymous_digest_verified": False,
        }
        if row["validation_dispatch_eligible"]:
            try:
                target = hub.download_object(
                    reference["dataset"],
                    reference["revision"],
                    reference["path"],
                    reference["byte_count"],
                )
            except ValueError, OSError:
                outcome = {
                    "status": "download_failed",
                    "anonymous_digest_verified": False,
                }
            else:
                try:
                    outcome = run_worker(index, target)
                except ValueError, OSError, TypeError:
                    outcome = {
                        "status": "worker_result_invalid",
                        "anonymous_digest_verified": False,
                    }
        document = {
            "schema_id": "global-medicines-atlas.mbs-utilisation-payload-validation",
            "schema_version": 1,
            "status": outcome["status"],
            "recorded_at": datetime.now(UTC).isoformat(),
            "code_commit": args.exact_commit,
            "workflow_run": f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{os.environ['GITHUB_RUN_ID']}",
            "acquisition_id": row["acquisition_id"],
            "raw_reference": reference,
            "result": outcome,
            "processing_admitted": False,
            "semantic_validation": False,
            "quarantine_decision": row["quarantine_decision"],
        }
        object_receipts = receipts / row["acquisition_id"]
        object_receipts.mkdir()
        receipt_url = persist_receipt(document, object_receipts)
        if not re.fullmatch(
            r"https://github\.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-[0-9]+",
            receipt_url,
        ):
            raise ValueError("validation receipt is not durable issue evidence")
        removed = False
        if target is not None and outcome["anonymous_digest_verified"]:
            target.unlink()
            removed = True
        observations.append({
            "path": row["path"],
            "status": outcome["status"],
            "receipt_url": receipt_url,
            "cache_removed": removed,
        })
        print(
            json.dumps({
                "path": row["path"],
                "status": outcome["status"],
                "receipt_url": receipt_url,
            })
        )
    summary: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.mbs-utilisation-validation-summary",
        "schema_version": 1,
        "status": "cohort_validation_recorded",
        "code_commit": args.exact_commit,
        "recorded_at": datetime.now(UTC).isoformat(),
        "records": observations,
        "processing_admitted": False,
    }
    print(
        json.dumps({"summary_receipt_url": persist_receipt(summary, receipts)})
    )


if __name__ == "__main__":
    if len(sys.argv) == WORKER_ARGUMENT_COUNT and sys.argv[1] == "--worker":
        print(json.dumps(worker(int(sys.argv[2]), Path(sys.argv[3]))))
    else:
        main()
