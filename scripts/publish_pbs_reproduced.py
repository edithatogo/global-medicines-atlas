"""Append the exact prepared PBS candidate from protected main Actions.

The exact publication authority record must already exist. Local execution,
ambiguous retries, and missing retained intent are rejected before a Hub write.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
from typing import Any, cast

from scripts import pbs_publication_intent as intent
from scripts import prepare_pbs_reproduced_delivery as preparation

AUTHORITY = (
    preparation.ROOT
    / "quality/qualifications/pbs-reproduced-publication-authority.json"
)


def prepare_attempt(root: Path) -> None:
    """Persist the run-bound attempt for artifact retention before mutation."""
    commit = os.environ.get("GITHUB_SHA", "")
    context = preparation.hosted._context(commit)  # pyright: ignore[reportPrivateUsage]
    if context["run_attempt"] != "1":
        raise ValueError("PBS publication does not retry Actions attempts")
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise ValueError("PBS append requires explicit workflow dispatch")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    root = root.resolve(strict=True)
    if not root.is_relative_to(runner_temp):
        raise ValueError("PBS transaction directory must be inside RUNNER_TEMP")
    intent_path = root / "intent.json"
    plan = json.loads(intent_path.read_text(encoding="utf-8"))
    if intent.build_intent(plan) != plan:
        raise ValueError("PBS publication intent does not match this run")
    intent.verify_retained_intent(commit, intent_path)
    document = {
        "status": "append_prepared",
        "intent_sha256": hashlib.sha256(intent_path.read_bytes()).hexdigest(),
        **context,
    }
    with (root / "append-attempt.json").open("x", encoding="utf-8") as output:
        json.dump(document, output, sort_keys=True)
        output.write("\n")


def append_once(root: Path, sdk: Any) -> dict[str, Any]:  # ruff: ignore[too-many-locals, too-many-statements]
    """Perform one server-CAS append and persist the returned revision."""
    commit = os.environ.get("GITHUB_SHA", "")
    context = preparation.hosted._context(commit)  # pyright: ignore[reportPrivateUsage] -- protected-run guard
    if context["run_attempt"] != "1":
        raise ValueError("PBS publication does not retry Actions attempts")
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise ValueError("PBS append requires explicit workflow dispatch")
    preparation.verify_checkout(commit)
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    root = root.resolve(strict=True)
    if not root.is_relative_to(runner_temp):
        raise ValueError("PBS transaction directory must be inside RUNNER_TEMP")
    ack_path = root / "cas-acknowledgement.json"
    started_path = root / "append-started.json"
    if any(
        path.exists() or path.is_symlink() for path in (ack_path, started_path)
    ):
        raise ValueError("PBS transaction has already been attempted")
    intent_path = root / "intent.json"
    plan = json.loads(intent_path.read_text(encoding="utf-8"))
    if intent.build_intent(plan) != plan:
        raise ValueError("PBS publication intent does not match this run")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    expected = {
        "schema_id": "global-medicines-atlas.pbs-reproduced-publication-authority",
        "publication_approved": True,
        "dataset": preparation.DATASET,
        "output_id": preparation.OUTPUT_ID,
        "parquet_sha256": preparation.PARQUET_SHA256,
        "parquet_bytes": preparation.PARQUET_BYTES,
        "remote_path": plan["remote_path"],
    }
    if any(authority.get(key) != value for key, value in expected.items()):
        raise ValueError("exact PBS publication authority is unavailable")
    intent.verify_retained_intent(commit, intent_path)
    attempt_path = root / "append-attempt.json"
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    if attempt != {
        "status": "append_prepared",
        "intent_sha256": hashlib.sha256(intent_path.read_bytes()).hexdigest(),
        **context,
    }:
        raise ValueError("PBS append attempt does not match this run")
    intent.verify_retained_intent(commit, attempt_path, attempt_artifact=True)
    staged = root / "candidate/first/values.parquet"
    if staged.is_symlink() or not staged.is_file():
        raise ValueError("PBS staged candidate is unavailable")
    with staged.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if (
        staged.stat().st_size != preparation.PARQUET_BYTES
        or digest != preparation.PARQUET_SHA256
    ):
        raise ValueError("PBS staged candidate differs")
    public: Any = sdk.HfApi(token=False)
    preparation.verify_live_publication_parent(public, plan)
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError("protected PBS publication credential unavailable")
    with started_path.open("x", encoding="utf-8") as output:
        json.dump(
            {"status": "append_attempted", **context}, output, sort_keys=True
        )
        output.write("\n")
    result: Any = sdk.HfApi(token=token).create_commit(
        repo_id=preparation.DATASET,
        repo_type="dataset",
        parent_commit=preparation.PUBLIC_PARENT_REVISION,
        commit_message="Publish qualified PBS Silver v4 candidate",
        operations=[
            sdk.CommitOperationAdd(
                path_in_repo=plan["remote_path"], path_or_fileobj=str(staged)
            )
        ],
    )
    revision = str(result.oid)
    if len(revision) != preparation.REVISION_LENGTH or any(
        c not in "0123456789abcdef" for c in revision
    ):
        raise ValueError("PBS Hub returned an invalid revision")
    acknowledgement = {
        "schema_id": "global-medicines-atlas.pbs-silver-cas-acknowledgement",
        "status": "cas_acknowledged_not_yet_verified",
        "dataset": preparation.DATASET,
        "parent_revision": preparation.PUBLIC_PARENT_REVISION,
        "revision": revision,
        "remote_path": plan["remote_path"],
        "parquet_sha256": digest,
        **context,
    }
    with ack_path.open("x", encoding="utf-8") as output:
        json.dump(acknowledgement, output, sort_keys=True)
        output.write("\n")
    return acknowledgement


def verify_append(root: Path, transport: Any) -> dict[str, Any]:  # ruff: ignore[too-many-locals]
    """Verify the acknowledged revision and preserve the earlier file inventory."""
    commit = os.environ.get("GITHUB_SHA", "")
    context = preparation.hosted._context(commit)  # pyright: ignore[reportPrivateUsage] -- protected-run guard
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise ValueError("PBS verification requires explicit workflow dispatch")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    root = root.resolve(strict=True)
    if not root.is_relative_to(runner_temp):
        raise ValueError("PBS transaction directory must be inside RUNNER_TEMP")
    plan = json.loads((root / "intent.json").read_text(encoding="utf-8"))
    if intent.build_intent(plan) != plan:
        raise ValueError("PBS publication intent does not match this run")
    acknowledgement = json.loads(
        (root / "cas-acknowledgement.json").read_text(encoding="utf-8")
    )
    expected = {
        "schema_id": "global-medicines-atlas.pbs-silver-cas-acknowledgement",
        "status": "cas_acknowledged_not_yet_verified",
        "dataset": preparation.DATASET,
        "parent_revision": preparation.PUBLIC_PARENT_REVISION,
        "remote_path": plan["remote_path"],
        "parquet_sha256": preparation.PARQUET_SHA256,
        **context,
    }
    if any(
        acknowledgement.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("PBS acknowledgement does not match this transaction")
    revision = acknowledgement.get("revision")
    if not isinstance(revision, str):
        raise TypeError("PBS acknowledgement has no immutable revision")
    tree_path = (
        preparation.ROOT
        / "quality/qualifications/pbs-reproduced-public-tree-readback-20261029/tree.json"
    )
    tree_bytes = tree_path.read_bytes()
    if hashlib.sha256(tree_bytes).hexdigest() != preparation.PUBLIC_TREE_SHA256:
        raise ValueError("PBS parent inventory digest differs")
    tree: list[dict[str, Any]] = json.loads(tree_bytes)
    prior_files = {
        entry["path"]: entry["oid"] for entry in tree if entry["type"] == "file"
    }
    info = transport.public.dataset_info(
        preparation.DATASET, revision=revision, files_metadata=True, timeout=30
    )
    if (
        info.sha != revision
        or info.private is not False
        or info.gated is not False
    ):
        raise ValueError("PBS acknowledged revision is not public")
    siblings = cast("list[Any]", info.siblings or [])
    files = {item.rfilename: item.blob_id for item in siblings}
    if set(files) != set(prior_files) | {plan["remote_path"]} or any(
        files[path] != oid for path, oid in prior_files.items()
    ):
        raise ValueError("PBS append did not preserve the prior file inventory")
    verified = preparation.verify_anonymous_published_candidate(
        transport, revision
    )
    receipt = {
        "schema_id": "global-medicines-atlas.pbs-silver-publication-receipt",
        "status": "anonymous_verification_passed_not_admitted",
        "parent_revision": preparation.PUBLIC_PARENT_REVISION,
        "prior_file_count": len(prior_files),
        "prior_file_blobs_preserved": True,
        "v4_admission_performed": False,
        **context,
        **verified,
    }
    receipt_path = root / "hosted-receipt.json"
    with receipt_path.open("x", encoding="utf-8") as output:
        json.dump(receipt, output, sort_keys=True)
        output.write("\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument(
        "--stage", required=True, choices=("attempt", "append", "verify")
    )
    args = parser.parse_args()
    try:  # ruff: ignore[too-many-statements-in-try-clause]
        if args.stage == "attempt":
            prepare_attempt(args.root)
            result = {"status": "append_prepared"}
        elif args.stage == "append":
            sdk: Any = importlib.import_module("huggingface_hub")
            result = append_once(args.root, sdk)
        else:
            from scripts.publish_source_metadata import HubTransport  # ruff: ignore[import-outside-top-level]

            cache = args.root / "verify-cache"
            cache.mkdir(exist_ok=False)
            result = verify_append(args.root, HubTransport(cache))
    except Exception:  # Do not expose source-bearing errors or credentials.
        print(json.dumps({"status": "transaction_failed", "stage": args.stage}))
        return 1
    print(json.dumps({"status": result["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
