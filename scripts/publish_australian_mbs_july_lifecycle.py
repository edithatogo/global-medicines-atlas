"""Append exact July 2026 MBS lifecycle metadata from protected Actions."""

# Fixed gh argument arrays; this publisher refuses local execution before
# loading the optional Hub SDK or reading a publication credential.
# ruff: file-ignore[suspicious-subprocess-import, subprocess-without-shell-equals-true, start-process-with-partial-path, too-many-statements, too-many-locals] -- linear hosted transaction with fixed subprocess commands
# ruff: file-ignore[too-many-branches, too-many-statements-in-try-clause, raise-within-try] -- keep the gated transaction linear and preserve its cleanup boundary

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import subprocess  # fixed gh argv only
import tempfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from publish_source_metadata import HubTransport, persist_receipt

from global_medicines_atlas.australian_mbs_july_lifecycle_append import (
    AUTHORIZATION_PATH,
    CONTRACT_PATH,
    M112_REPORT_PATH,
    READBACK_PATH,
    SCHEMA_PATH,
    build_july_metadata_additions,
    build_updated_manifest,
    sha256_bytes,
    validate_july_contract,
)
from global_medicines_atlas.federation_metadata_hosted import (
    REPOSITORY,
    require_hosted_main,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = "edithatogo/australian-mbs-source-archive"
MANIFEST_PATH = "manifest.json"
MAX_PAYLOAD_BYTES = 12 * 1024 * 1024
GIT_SHA_LENGTH = 40


def current_main() -> str:
    """Read the default branch identity independently from Actions input."""
    return subprocess.check_output(
        ["gh", "api", f"repos/{REPOSITORY}/commits/main", "--jq", ".sha"],
        text=True,
        timeout=30,
    ).strip()


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {label}")
    return cast("dict[str, Any]", value)


def _require_sibling(
    siblings: dict[str, Any], *, path: str, blob_oid: str, size: int
) -> None:
    sibling = siblings.get(path)
    if (
        sibling is None
        or getattr(sibling, "blob_id", None) != blob_oid
        or getattr(sibling, "size", None) != size
    ):
        raise ValueError(f"public parent object identity differs: {path}")


def _receipt_rows(additions: dict[str, bytes]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
        for path, payload in additions.items()
    ]


def _anonymous_info(api: Any, revision: str) -> tuple[Any, dict[str, Any]]:
    info = api.dataset_info(
        DATASET, revision=revision, files_metadata=True, timeout=30
    )
    if (
        info.sha != revision
        or info.private is not False
        or info.gated is not False
        or not info.siblings
    ):
        raise ValueError("anonymous dataset revision is not exact and public")
    return info, {item.rfilename: item for item in info.siblings}


def main() -> None:
    """Verify source bytes anonymously, then append metadata using parent CAS."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    if current_main() != args.exact_commit:
        raise ValueError("reviewed repository main has advanced")

    contract_bytes = (ROOT / CONTRACT_PATH).read_bytes()
    readback_bytes = (ROOT / READBACK_PATH).read_bytes()
    auth_bytes = (ROOT / AUTHORIZATION_PATH).read_bytes()
    report_bytes = (ROOT / M112_REPORT_PATH).read_bytes()
    contract, readback, authorization = validate_july_contract(
        contract_bytes,
        (ROOT / SCHEMA_PATH).read_bytes(),
        readback_bytes,
        auth_bytes,
        report_bytes,
    )
    parent = contract["expected_parent_revision"]
    cache = Path(tempfile.mkdtemp(prefix="gma-mbs-july-lifecycle-"))
    receipts = ROOT / "build/australian-mbs-july-lifecycle-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    hub = HubTransport(cache)
    sdk: Any = None
    verification_url = ""
    try:
        # Public reads are token-free. The temporary cache exists only on the
        # hosted runner and is removed after durable digest/readback receipts.
        sdk = importlib.import_module("huggingface_hub")
        public = sdk.HfApi(token=False)
        before, siblings = _anonymous_info(public, parent)
        if before.private or before.gated:
            raise ValueError("MBS archive is private or gated")

        manifest_before = hub.metadata(DATASET, parent, MANIFEST_PATH)
        if (
            sha256_bytes(manifest_before)
            != contract["expected_parent_manifest_sha256"]
        ):
            raise ValueError(
                "current public MBS manifest differs from contract"
            )
        manifest = _json_object(manifest_before, MANIFEST_PATH)
        manifest_files = manifest.get("files")
        if (
            not isinstance(manifest_files, list)
            or manifest.get("file_count")
            != contract["expected_parent_file_count"]
        ):
            raise ValueError("current public MBS manifest count differs")
        manifest_file_rows = cast("list[Any]", manifest_files)

        object_digests: dict[str, tuple[str, int]] = {}
        cache_paths: list[Path] = []
        for item in contract["objects"]:
            source_row = next(
                row
                for row in readback["objects"]
                if row["archive_path"] == item["archive_path"]
            )
            _require_sibling(
                siblings,
                path=item["archive_path"],
                blob_oid=item["git_blob_oid"],
                size=item["bytes"],
            )
            _require_sibling(
                siblings,
                path=item["sidecar_path"],
                blob_oid=item["sidecar_blob_oid"],
                size=item["sidecar_bytes"],
            )
            sidecar_bytes = hub.metadata(DATASET, parent, item["sidecar_path"])
            if (
                len(sidecar_bytes) != item["sidecar_bytes"]
                or sha256_bytes(sidecar_bytes) != item["sidecar_sha256"]
                or json.loads(sidecar_bytes) != source_row["sidecar"]
            ):
                raise ValueError("public source sidecar differs from readback")
            raw_path = hub.download_object(
                DATASET, parent, item["archive_path"], MAX_PAYLOAD_BYTES
            )
            cache_paths.append(raw_path)
            if raw_path.stat().st_size != item["bytes"]:
                raise ValueError("anonymous source byte count differs")
            with raw_path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != item["sha256"]:
                raise ValueError("anonymous source digest differs")
            object_digests[item["archive_path"]] = (digest, item["bytes"])

        decision_time = datetime.now(UTC).replace(microsecond=0)
        additions = build_july_metadata_additions(
            contract,
            readback,
            authorization,
            anonymous_digests=object_digests,
            decided_at=decision_time,
        )
        current_paths = set(siblings)
        if current_paths.intersection(additions):
            raise ValueError("lifecycle append would overwrite a public object")
        manifest_after = build_updated_manifest(
            manifest_before,
            additions,
            generated_at=decision_time,
            expected_sha256=contract["expected_parent_manifest_sha256"],
            expected_file_count=contract["expected_parent_file_count"],
        )
        manifest_doc = _json_object(manifest_after, MANIFEST_PATH)
        if manifest_doc["file_count"] != len(manifest_file_rows) + len(
            additions
        ):
            raise ValueError("updated root manifest row count differs")

        intent = {
            "schema_id": "global-medicines-atlas.australian-mbs-july-lifecycle-append",
            "schema_version": 1,
            "status": "intent",
            "dataset": DATASET,
            "parent_revision": parent,
            "code_commit": args.exact_commit,
            "run_url": f"https://github.com/{REPOSITORY}/actions/runs/"
            + os.environ["GITHUB_RUN_ID"],
            "contract_sha256": sha256_bytes(contract_bytes),
            "authorization_sha256": sha256_bytes(auth_bytes),
            "object_digests": [
                {
                    "path": path,
                    "sha256": digest,
                    "bytes": size,
                }
                for path, (digest, size) in sorted(object_digests.items())
            ],
            "metadata_additions": _receipt_rows(additions),
            "manifest_sha256_before": sha256_bytes(manifest_before),
            "manifest_sha256_after": sha256_bytes(manifest_after),
            "boundary": "Metadata-only CAS append; no source payload bytes will be uploaded; admissions are landed only.",
        }
        intent_url = persist_receipt(intent, receipts)
        verification = {
            **intent,
            "status": "anonymous_digest_verified",
            "intent_url": intent_url,
            "parent_public": True,
            "parent_gated": False,
            "anonymous_digest_verification": "passed",
            "sidecar_readback": "passed",
        }
        verification_url = persist_receipt(verification, receipts)
        for path in cache_paths:
            path.unlink(missing_ok=True)

        if current_main() != args.exact_commit:
            raise ValueError("reviewed repository main advanced before append")
        if hub.head(DATASET) != parent:
            raise ValueError(
                "MBS dataset head advanced before parent-CAS append"
            )
        operations = [
            sdk.CommitOperationAdd(
                path_in_repo=path,
                path_or_fileobj=BytesIO(payload),
            )
            for path, payload in additions.items()
        ]
        operations.append(
            sdk.CommitOperationAdd(
                path_in_repo=MANIFEST_PATH,
                path_or_fileobj=BytesIO(manifest_after),
            )
        )
        token = os.environ.get("HF_TOKEN")
        if not token:
            raise ValueError("protected MBS publication credential unavailable")
        writer = sdk.HfApi(token=token)
        response = writer.create_commit(
            repo_id=DATASET,
            repo_type="dataset",
            parent_commit=parent,
            commit_message=(
                "Append July MBS B1/B2 metadata without source bytes"
            ),
            operations=operations,
        )
        revision = str(response.oid)
        if len(revision) != GIT_SHA_LENGTH or any(
            char not in "0123456789abcdef" for char in revision
        ):
            raise ValueError("Hub returned an invalid commit identity")
        acknowledgement = {
            **intent,
            "status": "cas_acknowledged",
            "revision": revision,
            "parent_basis": "server_enforced_parent_commit",
            "intent_url": intent_url,
        }
        acknowledgement_url = persist_receipt(acknowledgement, receipts)

        after, after_siblings = _anonymous_info(public, revision)
        if after.private or after.gated:
            raise ValueError("resulting MBS archive is private or gated")
        for item in contract["objects"]:
            _require_sibling(
                after_siblings,
                path=item["archive_path"],
                blob_oid=item["git_blob_oid"],
                size=item["bytes"],
            )
        for path, payload in additions.items():
            observed = hub.metadata(DATASET, revision, path)
            if observed != payload:
                raise ValueError(f"anonymous metadata readback differs: {path}")
        manifest_observed = hub.metadata(DATASET, revision, MANIFEST_PATH)
        if manifest_observed != manifest_after:
            raise ValueError("anonymous root manifest readback differs")
        if sha256_bytes(manifest_observed) != sha256_bytes(manifest_after):
            raise ValueError("anonymous root manifest digest differs")
        receipt = {
            **intent,
            "status": "anonymously_verified",
            "revision": revision,
            "intent_url": intent_url,
            "verification_url": verification_url,
            "cas_acknowledgement_url": acknowledgement_url,
            "result_public": True,
            "result_gated": False,
            "anonymous_metadata_readback": "passed",
            "source_objects_preserved": True,
            "landed_only": True,
            "accepted_admissions": 0,
            "v4_admissions": 0,
            "consumer_canaries": 0,
        }
        receipt_url = persist_receipt(receipt, receipts)
        shutil.rmtree(cache)
        cleanup = {
            **receipt,
            "status": "cleanup_completed",
            "temporary_hosted_cache_removed": True,
        }
        cleanup_url = persist_receipt(cleanup, receipts)
        (receipts / "result.json").write_text(
            json.dumps(
                {
                    **receipt,
                    "receipt_url": receipt_url,
                    "cleanup_receipt_url": cleanup_url,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    except Exception:
        if verification_url:
            # Once anonymous payload digests are durably recorded, source bytes
            # can be removed even if the metadata transaction later fails.
            shutil.rmtree(cache, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
