"""Bind a PBS publication intent to a retained artifact from its exact run.

Only read-only GitHub artifact calls are performed here. This module does not
publish the candidate or establish publication approval.
"""

from __future__ import annotations

import io
import json
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import zipfile
from pathlib import Path
from typing import Any

from scripts import prepare_pbs_reproduced_delivery as preparation

REPOSITORY = "edithatogo/global-medicines-atlas"
MAX_ARTIFACT_BYTES = 1024 * 1024
MAX_INTENT_BYTES = 16 * 1024


def build_intent(plan: dict[str, Any]) -> dict[str, Any]:
    """Bind the dry-run candidate and parent to the exact Actions run."""
    commit = os.environ.get("GITHUB_SHA", "")
    context = preparation.hosted._context(commit)  # pyright: ignore[reportPrivateUsage] -- same protected-run guard
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise ValueError("PBS publication intent requires workflow dispatch")
    expected = {
        "dataset": preparation.DATASET,
        "expected_parent_revision": preparation.PUBLIC_PARENT_REVISION,
        "output_id": preparation.OUTPUT_ID,
        "parquet_sha256": preparation.PARQUET_SHA256,
        "parquet_bytes": preparation.PARQUET_BYTES,
        "remote_path": f"silver/pbs/v4/2026-04-01/{preparation.OUTPUT_ID}/values.parquet",
        "status": "dry_run_not_authorized_or_published",
        "publication_performed": False,
        "v4_admission_performed": False,
        **context,
    }
    if any(plan.get(key) != value for key, value in expected.items()):
        raise ValueError(
            "PBS publication intent does not match the prepared candidate"
        )
    return {
        "schema_id": "global-medicines-atlas.pbs-silver-publication-intent",
        "schema_version": 1,
        "repository": REPOSITORY,
        **expected,
        "candidate_only": True,
    }


def verify_retained_intent(
    commit: str, intent_path: Path, *, attempt_artifact: bool = False
) -> None:
    """Verify exact artifact metadata and bytes before a future Hub mutation."""
    variable = (
        "PUBLICATION_ATTEMPT_ARTIFACT_ID"
        if attempt_artifact
        else "PUBLICATION_INTENT_ARTIFACT_ID"
    )
    artifact_id = os.environ.get(variable, "")
    if (
        not artifact_id.isascii()
        or not artifact_id.isdigit()
        or int(artifact_id) < 1
    ):
        raise ValueError("PBS publication intent artifact ID is unavailable")
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ValueError("PBS publication repository differs")
    run_id = os.environ["GITHUB_RUN_ID"]
    run_attempt = os.environ["GITHUB_RUN_ATTEMPT"]
    kind = "attempt" if attempt_artifact else "intent"
    response = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        ["gh", "api", f"repos/{REPOSITORY}/actions/artifacts/{artifact_id}"],  # ruff: ignore[start-process-with-partial-path]
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    artifact: dict[str, Any] = json.loads(response.stdout)
    run: dict[str, Any] = artifact.get("workflow_run") or {}
    size = artifact.get("size_in_bytes")
    if type(size) is not int or not 0 < size <= MAX_ARTIFACT_BYTES:
        raise ValueError("PBS publication intent artifact size is invalid")
    if (
        artifact.get("id") != int(artifact_id)
        or artifact.get("name")
        != f"pbs-silver-publication-{kind}-{run_id}-{run_attempt}"
        or artifact.get("expired") is not False
        or str(run.get("id")) != run_id
        or run.get("head_sha") != commit
    ):
        raise ValueError(
            "PBS publication intent artifact differs from this run"
        )
    archive = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [  # ruff: ignore[start-process-with-partial-path]
            "gh",
            "api",
            f"repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout
    if len(archive) > MAX_ARTIFACT_BYTES:
        raise ValueError("PBS publication intent artifact exceeds its budget")
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        entries = zipped.infolist()
        if (
            len(entries) != 1
            or entries[0].filename
            != ("append-attempt.json" if attempt_artifact else "intent.json")
            or entries[0].file_size > MAX_INTENT_BYTES
            or zipped.read(entries[0]) != intent_path.read_bytes()
        ):
            raise ValueError("PBS retained intent bytes differ")
