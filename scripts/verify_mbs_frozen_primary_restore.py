"""Restore three assessed frozen MBS raw objects in memory, without values."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

import httpx
import scripts.qualify_australian_v4_privacy_readiness as guarded
import scripts.reconcile_mbs_frozen_v3_replays as replays

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.federation_reader import HOSTS


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def restore_in_memory(
    client: httpx.Client, url: str, *, expected_sha256: str, expected_bytes: int
) -> dict[str, Any]:
    """Reconstruct and hash a bounded response, then close its memory buffer."""
    _require(expected_bytes > 0, "primary restore size must be positive")
    deadline = time.monotonic() + guarded.READ_TIMEOUT
    for _ in range(guarded.MAX_REDIRECTS + 1):
        guarded._allowed_url(url)  # pyright: ignore[reportPrivateUsage]
        _require(time.monotonic() <= deadline, "primary restore timed out")
        client.cookies.clear()
        with client.stream("GET", url) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                _require(
                    location is not None,
                    "primary restore redirect lacks a location",
                )
                url = urljoin(url, str(location))
                continue
            _require(
                response.status_code == HTTPStatus.OK,
                "primary restore HTTP failure",
            )
            _require(
                response.headers.get("content-encoding", "identity")
                == "identity",
                "primary restore content encoding differs",
            )
            buffer = BytesIO()
            with buffer:
                size = 0
                for chunk in response.iter_bytes(guarded.CHUNK_BYTES):
                    size += len(chunk)
                    _require(
                        size <= expected_bytes,
                        "primary restore exceeds byte bound",
                    )
                    _require(
                        time.monotonic() <= deadline,
                        "primary restore timed out",
                    )
                    buffer.write(chunk)
                _require(
                    size == expected_bytes, "primary restore byte count differs"
                )
                buffer.seek(0)
                digest = hashlib.sha256()
                while chunk := buffer.read(guarded.CHUNK_BYTES):
                    digest.update(chunk)
                _require(
                    digest.hexdigest() == expected_sha256,
                    "primary restore digest differs",
                )
            _require(buffer.closed, "primary restore buffer did not close")
            return {
                "sha256": digest.hexdigest(),
                "byte_count": size,
                "restore_medium": "memory",
                "memory_buffer_closed": True,
                "source_values_interpreted_or_emitted": False,
                "source_payload_files_written": False,
            }
    raise ValueError("primary restore redirect limit exceeded")


def hosted_restore(*, commit: str) -> dict[str, Any]:
    """Restore only the three replay-qualified objects on an exact main run."""
    require_hosted_main(commit)
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    _require(
        re.fullmatch(r"[1-9][0-9]*", attempt) is not None
        and re.fullmatch(r"[1-9][0-9]*", run_id) is not None,
        "missing run identity or attempt",
    )
    report = replays.build()
    _require(
        report["summary"]["exact_replays_passed"] == len(replays.RUNS),
        "replay evidence differs",
    )
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=guarded.READ_TIMEOUT,
        max_attempts=1,
        max_redirects=guarded.MAX_REDIRECTS,
    )
    objects: list[dict[str, Any]] = []
    with httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        trust_env=False,
        follow_redirects=False,
        timeout=guarded.READ_TIMEOUT,
        headers={"Accept-Encoding": "identity"},
    ) as client:
        try:
            for row in report["objects"]:
                _require(
                    row["status"] == "passed", "MBS replay is not qualified"
                )
                url = (
                    f"https://huggingface.co/datasets/{row['dataset']}/resolve/"
                    f"{row['revision']}/{quote(row['path'], safe='/')}"
                )
                restored = restore_in_memory(
                    client,
                    url,
                    expected_sha256=row["sha256"],
                    expected_bytes=row["byte_count"],
                )
                objects.append({
                    **{
                        key: row[key] for key in ("dataset", "revision", "path")
                    },
                    **restored,
                    "restored_at": datetime.now(UTC).isoformat(),
                })
        except httpx.HTTPError:
            raise ValueError("primary restore transport failed") from None
    return {
        "schema_id": "global-medicines-atlas.mbs-frozen-primary-memory-restore",
        "schema_version": 1,
        "workflow_commit": commit,
        "workflow_run": run_id,
        "workflow_attempt": attempt,
        "objects": objects,
        "boundaries": {
            "primary_copy_only": True,
            "independent_recovery_established": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_added_or_published": False,
            "v4_admission_or_consumer_canary": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = hosted_restore(commit=args.workflow_commit)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"restored {len(receipt['objects'])} existing MBS objects in memory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
