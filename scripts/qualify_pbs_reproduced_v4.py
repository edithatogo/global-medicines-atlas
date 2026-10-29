"""Validate exact PBS publication receipt inputs for later v4 qualification.

Matching fields alone do not authenticate a hosted artifact or admit a product.
The caller must independently retain and authenticate the Actions evidence and
close all configured receipt roles before invoking the shared admission gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal, cast

from scripts import prepare_pbs_reproduced_delivery as candidate

from global_medicines_atlas.strict_json import unique_json_object

MAX_RECEIPT_BYTES = 64 * 1024
PREPARATION_FILE_COUNT = 2


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


def _authenticated_archive(
    *,
    workflow_commit: str,
    run_id: str,
    artifact_id: str,
    artifact_kind: Literal["receipt", "preparation"],
) -> bytes:
    """Bind an artifact archive to one successful exact-main workflow run."""
    import subprocess  # ruff: ignore[import-outside-top-level, suspicious-subprocess-import]

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
        "name": f"pbs-silver-publication-receipt-{run_id}-1"
        if artifact_kind == "receipt"
        else f"pbs-silver-preparation-{run_id}-1",
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
    return cast(
        "bytes", read_api(f"actions/artifacts/{artifact_id}/zip", binary=True)
    )


def authenticate_publication_artifact(
    *, workflow_commit: str, run_id: str, artifact_id: str
) -> tuple[bytes, dict[str, Any]]:
    """Read the exact successful Actions run and its retained receipt artifact."""
    import io  # ruff: ignore[import-outside-top-level]
    import zipfile  # ruff: ignore[import-outside-top-level]

    archive = _authenticated_archive(
        workflow_commit=workflow_commit,
        run_id=run_id,
        artifact_id=artifact_id,
        artifact_kind="receipt",
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


def authenticate_preparation_artifact(
    *, workflow_commit: str, run_id: str, artifact_id: str
) -> tuple[bytes, bytes]:
    """Authenticate the bounded manifest and reconstruction receipt for this run."""
    import io  # ruff: ignore[import-outside-top-level]
    import zipfile  # ruff: ignore[import-outside-top-level]

    archive = _authenticated_archive(
        workflow_commit=workflow_commit,
        run_id=run_id,
        artifact_id=artifact_id,
        artifact_kind="preparation",
    )
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        entries = zipped.infolist()
        names = {entry.filename for entry in entries}
        if (
            len(entries) != PREPARATION_FILE_COUNT
            or names != {"preparation.json", "candidate/first/manifest.json"}
            or any(entry.file_size > MAX_RECEIPT_BYTES for entry in entries)
        ):
            raise ValueError("PBS preparation artifact inventory differs")
        receipt_raw = zipped.read("preparation.json")
        manifest_raw = zipped.read("candidate/first/manifest.json")
    receipt: dict[str, Any] = json.loads(
        receipt_raw, object_pairs_hook=unique_json_object
    )
    manifest: dict[str, Any] = json.loads(
        manifest_raw, object_pairs_hook=unique_json_object
    )
    candidate.validate_candidate_identity(manifest)
    expected = {
        "status": "candidate_prepared_not_published_or_admitted",
        "workflow_commit": workflow_commit,
        "run_id": run_id,
        "run_attempt": "1",
        "output_id": candidate.OUTPUT_ID,
        "parquet_sha256": candidate.PARQUET_SHA256,
        "parquet_bytes": candidate.PARQUET_BYTES,
        "source_member_sha256": candidate.MEMBER_SHA256,
        "native_core_sha256": candidate.NATIVE_SHA256,
        "package_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "complete_source_reparse_and_restore": True,
        "parquet_bytes_identical": True,
        "independent_pipeline_builds": False,
        "publication_performed": False,
        "v4_admission_performed": False,
    }
    if any(
        type(receipt.get(key)) is not type(value) or receipt.get(key) != value
        for key, value in expected.items()
    ):
        raise ValueError(
            "PBS preparation receipt differs from the exact candidate"
        )
    return receipt_raw, manifest_raw


def retain_authenticated_receipts(
    output_dir: Path,
    *,
    workflow_commit: str,
    run_id: str,
    publication_artifact_id: str,
    preparation_artifact_id: str,
) -> dict[str, Any]:
    """Retain two authenticated metadata artifacts without creating admission."""
    from tempfile import TemporaryDirectory  # ruff: ignore[import-outside-top-level]

    publication_raw, publication = authenticate_publication_artifact(
        workflow_commit=workflow_commit,
        run_id=run_id,
        artifact_id=publication_artifact_id,
    )
    preparation_raw, manifest_raw = authenticate_preparation_artifact(
        workflow_commit=workflow_commit,
        run_id=run_id,
        artifact_id=preparation_artifact_id,
    )
    output_dir = Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError("PBS receipt output already exists")
    if not output_dir.parent.is_dir():
        raise ValueError("PBS receipt output parent does not exist")
    inputs = {
        "publication.json": publication_raw,
        "preparation.json": preparation_raw,
        "package-manifest.json": manifest_raw,
    }
    summary = {
        "schema_id": "global-medicines-atlas.pbs-authenticated-hosted-receipts",
        "schema_version": 1,
        "status": "authenticated_not_admitted",
        "workflow_commit": workflow_commit,
        "run_id": run_id,
        "publication_artifact_id": publication_artifact_id,
        "preparation_artifact_id": preparation_artifact_id,
        "dataset": candidate.DATASET,
        "revision": publication["revision"],
        "output_id": candidate.OUTPUT_ID,
        "parquet_sha256": candidate.PARQUET_SHA256,
        "files": {
            name: hashlib.sha256(raw).hexdigest()
            for name, raw in sorted(inputs.items())
        },
        "v4_admission_performed": False,
        "consumer_canaries_run": False,
    }
    with TemporaryDirectory(
        prefix=".pbs-hosted-receipts-", dir=output_dir.parent
    ) as temporary:
        staged = Path(temporary) / "receipts"
        staged.mkdir()
        for name, raw in inputs.items():
            (staged / name).write_bytes(raw)
        (staged / "manifest.json").write_text(
            json.dumps(summary, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        staged.rename(output_dir)
    return summary
