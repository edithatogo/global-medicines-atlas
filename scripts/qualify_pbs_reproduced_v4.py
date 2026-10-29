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


def authenticate_publication_artifact(
    *, workflow_commit: str, run_id: str, artifact_id: str
) -> tuple[bytes, dict[str, Any]]:
    """Read the exact successful Actions run and its retained receipt artifact."""
    import io  # ruff: ignore[import-outside-top-level]
    import subprocess  # ruff: ignore[import-outside-top-level, suspicious-subprocess-import]
    import zipfile  # ruff: ignore[import-outside-top-level]

    if re.fullmatch(r"[0-9a-f]{40}", workflow_commit) is None or any(
        re.fullmatch(r"[1-9][0-9]*", value) is None
        for value in (run_id, artifact_id)
    ):
        raise ValueError("PBS publication artifact identity is invalid")
    repository = "edithatogo/global-medicines-atlas"

    def read_api(path: str, *, binary: bool = False) -> Any:
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [  # ruff: ignore[start-process-with-partial-path]
                "gh",
                "api",
                "--allow-escape-sequences",
                f"repos/{repository}/{path}",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        if len(result.stdout) > 1024 * 1024:
            raise ValueError("PBS Actions response exceeds its bound")
        return (
            result.stdout
            if binary
            else json.loads(result.stdout, object_pairs_hook=unique_json_object)
        )

    run: dict[str, Any] = read_api(f"actions/runs/{run_id}")
    run_repository: dict[str, Any] = run.get("repository") or {}
    expected_run = {
        "id": int(run_id),
        "head_branch": "main",
        "head_sha": workflow_commit,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "run_attempt": 1,
        "path": ".github/workflows/australian-pbs-reproduced-publication.yml",
    }
    if (
        any(
            type(run.get(key)) is not type(value) or run.get(key) != value
            for key, value in expected_run.items()
        )
        or run_repository.get("full_name") != repository
    ):
        raise ValueError(
            "PBS publication run is not the exact successful main workflow"
        )
    artifact: dict[str, Any] = read_api(f"actions/artifacts/{artifact_id}")
    workflow_run: dict[str, Any] = artifact.get("workflow_run") or {}
    size = artifact.get("size_in_bytes")
    expected_artifact = {
        "id": int(artifact_id),
        "name": f"pbs-silver-publication-receipt-{run_id}-1",
        "expired": False,
    }
    if (
        any(
            type(artifact.get(key)) is not type(value)
            or artifact.get(key) != value
            for key, value in expected_artifact.items()
        )
        or type(size) is not int
        or not 0 < size <= 1024 * 1024
        or workflow_run.get("id") != int(run_id)
        or workflow_run.get("head_sha") != workflow_commit
    ):
        raise ValueError(
            "PBS publication receipt artifact differs from the exact run"
        )
    archive: bytes = read_api(
        f"actions/artifacts/{artifact_id}/zip", binary=True
    )
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        entries = zipped.infolist()
        if (
            len(entries) != 1
            or entries[0].filename != "hosted-receipt.json"
            or entries[0].file_size > MAX_RECEIPT_BYTES
        ):
            raise ValueError("PBS publication receipt archive is invalid")
        raw = zipped.read(entries[0])
    return raw, validate_publication_receipt(
        raw, workflow_commit=workflow_commit, run_id=run_id, run_attempt="1"
    )
