"""Observe value shapes in four exact hosted MBS utilisation CSV objects."""

# Fixed subprocess arrays use hosted PATH and never invoke a shell.
# ruff: file-ignore[subprocess-without-shell-equals-true]
from __future__ import annotations

import argparse
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
from global_medicines_atlas.mbs_utilisation_header_inventory import (
    workflow_run_url,
)
from global_medicines_atlas.mbs_utilisation_validation import (
    verify_staged_identity,
)
from global_medicines_atlas.mbs_utilisation_value_observer import (
    load_value_observer_cohort,
    observe_utilisation_csv_values,
)

ROOT = Path(__file__).resolve().parents[1]
WORKER_SECONDS = 120
WORKER_MEMORY_BYTES = 1_073_741_824
WORKER_ARGUMENT_COUNT = 5
RECEIPT_URL_PATTERN = re.compile(
    r"https://github\.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-[0-9]+"
)


def worker(index: int, path: Path, exact_commit: str) -> dict[str, Any]:
    """Verify identity, observe value shapes, and return aggregates only."""
    require_hosted_main(exact_commit)
    if sys.platform != "linux":
        raise ValueError("MBS CSV observer worker requires Linux")
    resource = importlib.import_module("resource")
    resource.setrlimit(
        resource.RLIMIT_AS, (WORKER_MEMORY_BYTES, WORKER_MEMORY_BYTES)
    )
    selected = load_value_observer_cohort(ROOT)
    row = selected[index]
    reference = row["raw_reference"]
    try:
        verify_staged_identity(path, reference)
    except OSError, MemoryError:
        return {
            "status": "identity_unavailable",
            "anonymous_digest_verified": False,
        }
    except ValueError:
        return {"status": "identity_failed", "anonymous_digest_verified": False}
    try:
        observation = observe_utilisation_csv_values(
            path, expected_headers=row["expected_headers"]
        )
    except OSError, MemoryError:
        return {
            "status": "observation_unavailable",
            "anonymous_digest_verified": True,
        }
    except ValueError:
        return {
            "status": "value_observation_failed",
            "anonymous_digest_verified": True,
        }
    return {
        "status": "value_observed",
        "anonymous_digest_verified": True,
        "observation": observation.to_public_summary(),
    }


def run_worker(index: int, path: Path, exact_commit: str) -> dict[str, Any]:
    """Enforce a wall-clock bound and strip workflow credentials."""
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                str(index),
                str(path),
                exact_commit,
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
        value = json.loads(completed.stdout)
    except subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError:
        return {
            "status": "worker_failed_or_timed_out",
            "anonymous_digest_verified": False,
        }
    if not isinstance(value, dict):
        raise TypeError("MBS CSV observer worker returned invalid result")
    result = cast("dict[str, Any]", value)
    if result.get("status") not in {
        "identity_failed",
        "identity_unavailable",
        "observation_unavailable",
        "value_observation_failed",
        "value_observed",
    }:
        raise ValueError("MBS CSV observer worker returned invalid status")
    if result.get("anonymous_digest_verified") != (
        result["status"] not in {"identity_failed", "identity_unavailable"}
    ):
        raise ValueError("MBS CSV observer identity claim differs")
    return result


def main() -> None:
    """Persist independent aggregate receipts before removing verified files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    if current_main() != args.exact_commit:
        raise ValueError("reviewed main has advanced")
    selected = load_value_observer_cohort(ROOT)
    cache = Path(tempfile.mkdtemp(prefix="gma-mbs-value-observer-"))
    receipts = ROOT / "build/mbs-utilisation-value-observer-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    hub = HubTransport(cache)
    hub.head(selected[0]["raw_reference"]["dataset"])
    observations: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        reference = row["raw_reference"]
        target = None
        outcome: dict[str, Any] = {
            "status": "download_failed",
            "anonymous_digest_verified": False,
        }
        try:
            target = hub.download_object(
                reference["dataset"],
                reference["revision"],
                reference["path"],
                reference["byte_count"],
            )
        except ValueError, OSError:
            pass
        else:
            try:
                outcome = run_worker(index, target, args.exact_commit)
            except OSError, TypeError, ValueError:
                outcome = {
                    "status": "worker_result_invalid",
                    "anonymous_digest_verified": False,
                }
        document = {
            "schema_id": "global-medicines-atlas.mbs-utilisation-value-observation",
            "schema_version": 1,
            "status": outcome["status"],
            "recorded_at": datetime.now(UTC).isoformat(),
            "code_commit": args.exact_commit,
            "workflow_run": workflow_run_url(),
            "acquisition_id": row["acquisition_id"],
            "raw_reference": reference,
            "catalogue_resource_id": row["resource_id"],
            "header_schema_candidate_id": row["observed_schema_id"],
            "prior_header_receipt_url": row["prior_header_receipt_url"],
            "observation_profile": "mbs-utilisation-csv-value-shape-v1",
            "result": outcome,
            "semantic_validation": False,
            "semantic_mapping_selected": False,
            "processing_admitted": False,
            "silver_published": False,
        }
        receipt_url = persist_receipt(document, receipts)
        if not RECEIPT_URL_PATTERN.fullmatch(receipt_url):
            raise ValueError("value observation is not durable issue evidence")
        removed = False
        if target is not None and outcome["anonymous_digest_verified"]:
            target.unlink()
            removed = True
        observations.append({
            "path": reference["path"],
            "status": outcome["status"],
            "receipt_url": receipt_url,
            "cache_removed": removed,
        })
        print(json.dumps(observations[-1]))

    summary = {
        "schema_id": "global-medicines-atlas.mbs-utilisation-value-observation-summary",
        "schema_version": 1,
        "status": "value_observation_recorded",
        "code_commit": args.exact_commit,
        "recorded_at": datetime.now(UTC).isoformat(),
        "workflow_run": workflow_run_url(),
        "records": observations,
        "candidate_source_count": len(selected),
        "source_inventory_expanded": False,
        "semantic_validation": False,
        "semantic_mapping_selected": False,
        "processing_admitted": False,
        "silver_published": False,
    }
    summary_url = persist_receipt(summary, receipts)
    if not RECEIPT_URL_PATTERN.fullmatch(summary_url):
        raise ValueError(
            "value observation summary is not durable issue evidence"
        )
    print(json.dumps({"summary_receipt_url": summary_url}))


if __name__ == "__main__":
    if len(sys.argv) == WORKER_ARGUMENT_COUNT and sys.argv[1] == "--worker":
        print(
            json.dumps(worker(int(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]))
        )
    else:
        main()
