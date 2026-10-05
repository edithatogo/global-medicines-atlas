"""Validate the exact historical MBS cohort only in protected main Actions."""

# Fixed subprocess arrays use hosted PATH and never invoke a shell.
# ruff: file-ignore[subprocess-without-shell-equals-true]
from __future__ import annotations

import argparse
import csv
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
from global_medicines_atlas.mbs_csv_header_inventory import (
    header_candidates,
    inventory_csv_header,
)
from global_medicines_atlas.mbs_streaming_workbook import (
    PROFILE,
    streaming_limits,
    validate_streaming_workbook,
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
DIAGNOSTIC_RECEIPT_PATH = Path(
    "quality/qualifications/australian-mbs-utilisation-payload-validation-receipt-20261004.json"
)
DIAGNOSTIC_RECEIPT_SHA256 = (
    "f622434530f3d184a5aea6684e67dc7f874424c2ada634b2f154490a39c6f457"
)
FAILURE_CODES = {
    "CSV header byte limit": "csv_header_byte_limit",
    "CSV header field count limit": "csv_header_field_count_limit",
    "CSV header field byte limit": "csv_header_field_byte_limit",
    "CSV header decoding or syntax invalid": "csv_header_invalid",
    "archive total uncompressed bytes limit exceeded": "archive_expanded_byte_limit",
    "archive member byte limit exceeded": "archive_member_byte_limit",
    "archive decompression ratio exceeded": "archive_decompression_ratio_limit",
    "archive entry count limit exceeded": "archive_entry_count_limit",
    "archive member integrity failed": "archive_stream_integrity_failed",
    "archive directory contains payload or invalid CRC": "archive_directory_integrity_failed",
    "Workbook ZIP exceeds uncompressed size limit": "xlsx_expanded_byte_limit",
    "Workbook metadata member exceeds size limit": "xlsx_metadata_byte_limit",
    "Workbook OOXML required member is missing": "xlsx_required_member_missing",
    "Workbook OOXML required members have unexpected roots": "xlsx_package_roots_unexpected",
}

STREAMING_ERRORS = {
    "streaming workbook " + reason
    for reason in (
        "XML root invalid",
        "XML resource limit",
        "metadata record limit",
        "XML text limit",
        "XML declaration forbidden",
        "metadata byte limit",
        "XML malformed",
        "relationship invalid",
        "format invalid",
        "required member missing",
    )
}


def failed_workbook_paths(root: Path, cohort: list[dict[str, Any]]) -> set[str]:
    """Select only exact recorded workbook failures from the trusted receipt."""
    payload = (root / DIAGNOSTIC_RECEIPT_PATH).read_bytes()
    if hashlib.sha256(payload).hexdigest() != DIAGNOSTIC_RECEIPT_SHA256:
        raise ValueError("diagnostic receipt differs")
    rows = {row["path"]: row for row in cohort}
    selected: set[str] = set()
    for receipt in json.loads(payload)["per_object_receipts"]:
        document = receipt["document"]
        reference = document["raw_reference"]
        if document["status"] == "structure_failed" and reference[
            "path"
        ].endswith(".xlsx"):
            row = rows[reference["path"]]
            if (
                reference != row["raw_reference"]
                or not row["validation_dispatch_eligible"]
            ):
                raise ValueError("diagnostic source identity differs")
            selected.add(reference["path"])
    return selected


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
    except OSError, MemoryError:
        return {
            "status": "identity_unavailable",
            "anonymous_digest_verified": False,
        }
    except ValueError:
        return {"status": "identity_failed", "anonymous_digest_verified": False}
    streaming = os.environ.get("GMA_MBS_STREAMING_PROFILE") == "1"
    if streaming and reference["path"] not in failed_workbook_paths(
        ROOT, load_validation_cohort(ROOT)
    ):
        raise ValueError("streaming profile source not selected")
    headers = os.environ.get("GMA_MBS_HEADER_INVENTORY") == "1"
    candidates = (
        header_candidates(ROOT, load_validation_cohort(ROOT)) if headers else {}
    )
    if headers and (streaming or reference["path"] not in candidates):
        raise ValueError("header inventory source not selected")
    try:
        checks = (
            inventory_csv_header(path, reference, candidates[reference["path"]])
            if headers
            else validate_streaming_workbook(path, reference)
            if streaming
            else validate_staged_payload(path, reference)
        )
    except OSError, MemoryError:
        return {
            "status": "validation_unavailable",
            "anonymous_digest_verified": True,
        }
    except ValueError as error:
        # Shared archive/package guards preserve the original I/O exception
        # as a cause; it is still inconclusive evidence, not a source verdict.
        status = (
            "validation_unavailable"
            if isinstance(error.__cause__, (OSError, MemoryError))
            else "structure_failed"
        )
        return {
            "status": status,
            "anonymous_digest_verified": True,
            "failure_code": "infrastructure_unavailable"
            if status == "validation_unavailable"
            else (
                str(error)
                .replace("streaming workbook ", "xlsx_stream_")
                .replace(" ", "_")
                .lower()
                if str(error) in STREAMING_ERRORS
                else FAILURE_CODES.get(
                    str(error), "structural_profile_failure_unclassified"
                )
            ),
        }
    except UnicodeError, EOFError, csv.Error:
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
            "identity_unavailable",
            "validation_unavailable",
            "structure_failed",
            "structure_verified",
        }
        or type(result.get("anonymous_digest_verified")) is not bool
    ):
        raise ValueError("validation worker returned invalid result")
    if result["anonymous_digest_verified"] != (
        result["status"] not in {"identity_failed", "identity_unavailable"}
    ):
        raise ValueError("validation worker identity claim differs")
    return result


def main() -> None:  # ruff: ignore[too-many-locals, too-many-statements, too-many-branches] -- linear receipt and cleanup gates
    """Persist each independent result before cleanup of verified raw bytes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--failed-workbooks-only", action="store_true")
    parser.add_argument("--streaming-workbooks", action="store_true")
    parser.add_argument("--csv-headers-only", action="store_true")
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    if args.csv_headers_only and (
        args.streaming_workbooks or args.failed_workbooks_only
    ):
        raise ValueError("header inventory modes conflict")
    os.environ.pop("GMA_MBS_HEADER_INVENTORY", None)
    if args.csv_headers_only:
        os.environ["GMA_MBS_HEADER_INVENTORY"] = "1"
    os.environ.pop("GMA_MBS_STREAMING_PROFILE", None)
    if args.streaming_workbooks:
        args.failed_workbooks_only = True
        os.environ["GMA_MBS_STREAMING_PROFILE"] = "1"
    cohort = load_validation_cohort(ROOT)
    selected = (
        set(header_candidates(ROOT, cohort))
        if args.csv_headers_only
        else failed_workbook_paths(ROOT, cohort)
        if args.failed_workbooks_only
        else {row["path"] for row in cohort}
    )
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
        if row["path"] not in selected:
            continue
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
            "validation_mode": "csv_headers_only"
            if args.csv_headers_only
            else "streaming_workbooks"
            if args.streaming_workbooks
            else "failed_workbooks_only"
            if args.failed_workbooks_only
            else "full_cohort",
        }
        if args.streaming_workbooks:
            document["validation_profile"] = PROFILE
            document["resource_limits"] = {
                **streaming_limits(),
                "worker_seconds": WORKER_SECONDS,
                "worker_memory_bytes": WORKER_MEMORY_BYTES,
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
        "validation_mode": "csv_headers_only"
        if args.csv_headers_only
        else "streaming_workbooks"
        if args.streaming_workbooks
        else "failed_workbooks_only"
        if args.failed_workbooks_only
        else "full_cohort",
    }
    print(
        json.dumps({"summary_receipt_url": persist_receipt(summary, receipts)})
    )


if __name__ == "__main__":
    if len(sys.argv) == WORKER_ARGUMENT_COUNT and sys.argv[1] == "--worker":
        print(json.dumps(worker(int(sys.argv[2]), Path(sys.argv[3]))))
    else:
        main()
