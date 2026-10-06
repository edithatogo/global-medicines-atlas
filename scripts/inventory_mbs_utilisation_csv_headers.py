"""Inventory only first records of the four exact verified MBS CSV objects."""

# Fixed subprocess arrays use hosted PATH and never invoke a shell.
# ruff: file-ignore[subprocess-without-shell-equals-true]
from __future__ import annotations

import argparse
import hashlib
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
    SEMANTIC_REQUIREMENTS_PATH,
    SEMANTIC_REQUIREMENTS_SHA256,
    inventory_csv_header,
    load_header_inventory_contract,
    public_header_result,
    workflow_run_url,
)
from global_medicines_atlas.mbs_utilisation_validation import (
    verify_staged_identity,
)

ROOT = Path(__file__).resolve().parents[1]
WORKER_SECONDS = 60
WORKER_MEMORY_BYTES = 1_073_741_824
WORKER_ARGUMENT_COUNT = 5
RECEIPT_URL_PATTERN = re.compile(
    r"https://github\.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-[0-9]+"
)


def worker(index: int, path: Path, exact_commit: str) -> dict[str, Any]:
    """Verify exact bytes, parse a header only, and return public-safe data."""
    require_hosted_main(exact_commit)
    if sys.platform != "linux":
        raise ValueError("header inventory worker requires Linux")
    resource = importlib.import_module("resource")
    resource.setrlimit(
        resource.RLIMIT_AS, (WORKER_MEMORY_BYTES, WORKER_MEMORY_BYTES)
    )
    selected, schemas = load_header_inventory_contract(ROOT)
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
        inventory = inventory_csv_header(
            path,
            {
                resource_id: schemas[resource_id]
                for resource_id in row["schema_candidate_ids"]
            },
        )
        header = public_header_result(
            inventory, frozenset(row["approved_headers"])
        )
    except OSError, UnicodeError, ValueError:
        return {
            "status": "header_inventory_failed",
            "anonymous_digest_verified": True,
        }
    return {
        "status": "header_inventory_verified",
        "anonymous_digest_verified": True,
        "header": header,
    }


def run_worker(index: int, path: Path, exact_commit: str) -> dict[str, Any]:
    """Enforce a hard wall-clock limit and remove all workflow tokens."""
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
        raise TypeError("header inventory worker returned invalid result")
    result = cast("dict[str, Any]", value)
    if result.get("status") not in {
        "identity_failed",
        "identity_unavailable",
        "header_inventory_failed",
        "header_inventory_verified",
    }:
        raise ValueError("header inventory worker returned invalid status")
    if result.get("anonymous_digest_verified") != (
        result["status"] not in {"identity_failed", "identity_unavailable"}
    ):
        raise ValueError("header inventory worker identity claim differs")
    return result


def main() -> None:  # ruff: ignore[too-many-locals] -- ordered per-object evidence and cleanup
    """Persist independently, then remove only digest-verified cache files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    if current_main() != args.exact_commit:
        raise ValueError("reviewed main has advanced")
    selected, _schemas = load_header_inventory_contract(ROOT)
    requirements_bytes = (ROOT / SEMANTIC_REQUIREMENTS_PATH).read_bytes()
    if (
        hashlib.sha256(requirements_bytes).hexdigest()
        != SEMANTIC_REQUIREMENTS_SHA256
    ):
        raise ValueError("semantic requirements digest differs")
    requirements = json.loads(requirements_bytes)
    schema_by_resource = {
        item["resource_id"]: item
        for item in requirements["csv_schema_metadata_snapshots"]
    }

    cache = Path(tempfile.mkdtemp(prefix="gma-mbs-header-inventory-"))
    receipts = ROOT / "build/mbs-utilisation-header-receipts"
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
        schema = schema_by_resource[row["resource_id"]]
        document = {
            "schema_id": "global-medicines-atlas.mbs-utilisation-csv-header-inventory",
            "schema_version": 1,
            "status": outcome["status"],
            "recorded_at": datetime.now(UTC).isoformat(),
            "code_commit": args.exact_commit,
            "workflow_run": workflow_run_url(),
            "acquisition_id": row["acquisition_id"],
            "raw_reference": reference,
            "catalogue_resource_id": row["resource_id"],
            "catalogue_response_sha256": schema["response_sha256"],
            "candidate_schema_resource_ids": row["schema_candidate_ids"],
            "structural_receipt_url": row["structural_receipt_url"],
            "result": outcome,
            "inventory_profile": "first-record-csv-utf8-bom-v1",
            "semantic_validation": False,
            "processing_admitted": False,
        }
        url = persist_receipt(document, receipts)
        if not RECEIPT_URL_PATTERN.fullmatch(url):
            raise ValueError(
                "header inventory receipt is not durable issue evidence"
            )
        removed = False
        if target is not None and outcome["anonymous_digest_verified"]:
            target.unlink()
            removed = True
        observations.append({
            "path": row["raw_reference"]["path"],
            "status": outcome["status"],
            "receipt_url": url,
            "cache_removed": removed,
        })
        print(json.dumps(observations[-1]))

    summary = {
        "schema_id": "global-medicines-atlas.mbs-utilisation-csv-header-summary",
        "schema_version": 1,
        "status": "header_inventory_recorded",
        "code_commit": args.exact_commit,
        "recorded_at": datetime.now(UTC).isoformat(),
        "workflow_run": workflow_run_url(),
        "records": observations,
        "candidate_source_count": len(selected),
        "source_inventory_expanded": False,
        "semantic_validation": False,
        "processing_admitted": False,
    }
    summary_url = persist_receipt(summary, receipts)
    if not RECEIPT_URL_PATTERN.fullmatch(summary_url):
        raise ValueError("header summary is not durable issue evidence")
    print(json.dumps({"summary_receipt_url": summary_url}))


if __name__ == "__main__":
    if len(sys.argv) == WORKER_ARGUMENT_COUNT and sys.argv[1] == "--worker":
        print(
            json.dumps(worker(int(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]))
        )
    else:
        main()
