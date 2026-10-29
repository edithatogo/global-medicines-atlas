"""Prepare the exact PBS Silver candidate on protected main Actions only.

This creates no Hub object and confers no admission or publication. The caller
must retain the staged package until a separately authorized publication and
anonymous verification transaction has completed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas import pbs_hosted_qualification as hosted

ROOT = Path(__file__).resolve().parents[1]
ATTESTATION = ROOT / (
    "quality/qualifications/"
    "australian-pbs-reproduced-silver-output-rights-attestation-20261029.json"
)
OUTPUT_ID = "8e8bacdc72ea81ecfbb84d161b3f546eee03bddeae32f82daa7231c3759d23fc"
PARQUET_SHA256 = (
    "86d65b147dc95787c5e3f14b13abe2630562f050e2221a1340939dcc7776a88c"
)
PARQUET_BYTES = 637012122
REVISION_LENGTH = 40
NATIVE_SHA256 = (
    "890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25"
)
ARCHIVE_SHA256 = (
    "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
)
DATASET = "edithatogo/australian-pbs-source-archive"
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
PUBLIC_PARENT_REVISION = "208f0b0f1db7768018b3c50929596d63d16e3392"
PUBLIC_TREE_SHA256 = (
    "8f38b87b6dee2d0d65275f29695dfcb52726b3df330835467f6a83e767e2bea3"
)
PUBLIC_TREE_ENTRY_COUNT = 16
PUBLIC_READBACK_SHA256 = (
    "ec742349ffc4abafc1ade3bfcfcf610a7547dba9109fff121c23512805dfeb2c"
)
MEMBER_SHA256 = (
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
)


def validate_candidate_identity(package: dict[str, Any]) -> None:
    """Reject changed bytes or source lineage before a candidate can be used."""
    if (
        package.get("output_id") != OUTPUT_ID
        or package.get("parquet")
        != {
            "bytes": PARQUET_BYTES,
            "sha256": PARQUET_SHA256,
        }
        or package.get("coverage", {}).get("native_core_sha256")
        != NATIVE_SHA256
        or package
        .get("member_binding", {})
        .get("member_payload", {})
        .get("sha256")
        != MEMBER_SHA256
    ):
        raise ValueError("PBS candidate differs from the attested exact output")


def verify_checkout(exact_commit: str) -> None:
    """Reject a checkout that differs from the declared Actions commit."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],  # ruff: ignore[start-process-with-partial-path] -- trusted Git executable
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.stdout.strip() != exact_commit:
        raise ValueError("PBS checkout does not match the Actions commit")
    subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--"],  # ruff: ignore[start-process-with-partial-path] -- trusted Git executable
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=10,
    )


def prepare(exact_commit: str, output: Path) -> dict[str, Any]:
    """Rebuild and retain the exact candidate without publication or admission."""
    context = hosted._context(exact_commit)  # pyright: ignore[reportPrivateUsage] -- reuse the exact hosted guard
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise ValueError(
            "PBS preparation requires an explicit workflow dispatch"
        )
    verify_checkout(exact_commit)
    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp:
        raise ValueError("RUNNER_TEMP is required")
    root = Path(runner_temp).resolve(strict=True)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("candidate output already exists")
    if not output.parent.resolve(strict=True).is_relative_to(root):
        raise ValueError("candidate output must be inside RUNNER_TEMP")
    rights = json.loads(ATTESTATION.read_text(encoding="utf-8"))
    attested = rights["authorized_output"]
    expected = {
        "output_id": OUTPUT_ID,
        "parquet_sha256": PARQUET_SHA256,
        "parquet_bytes": PARQUET_BYTES,
        "member_sha256": MEMBER_SHA256,
        "archive_sha256": ARCHIVE_SHA256,
        "dataset": DATASET,
        "revision": REVISION,
        "native_core_sha256": NATIVE_SHA256,
    }
    if rights.get("public_release_rights_attested") is not True or any(
        attested.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("exact PBS rights attestation does not match")
    retry = hosted._RetryBudget()  # pyright: ignore[reportPrivateUsage] -- reuse bounded transport
    inputs = hosted._verified_inputs(  # pyright: ignore[reportPrivateUsage] -- pinned source verification
        exact_commit, transport=None, retry=retry
    )
    result = hosted.qualify_value_package_pair(
        inputs.archive, inputs.xml, inputs.parent, inputs.binding, output
    )
    package = result["package"]
    validate_candidate_identity(package)
    if (
        result.get("complete_source_reparse_and_restore") is not True
        or result.get("parquet_bytes_identical") is not True
    ):
        raise ValueError(
            "PBS full restore or serialization parity is incomplete"
        )
    for directory in ("first", "second"):
        parquet = output / directory / "values.parquet"
        if parquet.is_symlink() or not parquet.is_file():
            raise ValueError("PBS candidate Parquet file is unavailable")
        digest = hashlib.sha256()
        with parquet.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        if (
            parquet.stat().st_size != PARQUET_BYTES
            or digest.hexdigest() != PARQUET_SHA256
        ):
            raise ValueError(
                "PBS staged Parquet bytes differ from attested output"
            )
    return {
        "schema_id": "global-medicines-atlas.pbs-reproduced-delivery-preparation",
        "schema_version": 1,
        "status": "candidate_prepared_not_published_or_admitted",
        "workflow_commit": context["workflow_commit"],
        "run_id": context["run_id"],
        "run_attempt": context["run_attempt"],
        "output_id": OUTPUT_ID,
        "parquet_sha256": PARQUET_SHA256,
        "parquet_bytes": PARQUET_BYTES,
        "source_member_sha256": MEMBER_SHA256,
        "native_core_sha256": NATIVE_SHA256,
        "publication_performed": False,
        "v4_admission_performed": False,
        "candidate_retained": True,
    }


def build_publication_plan(
    prepared: dict[str, Any], readback_bytes: bytes, tree_bytes: bytes
) -> dict[str, Any]:
    """Describe a dry-run append; do not grant authority or contact the Hub."""
    expected_preparation = {
        "status": "candidate_prepared_not_published_or_admitted",
        "output_id": OUTPUT_ID,
        "parquet_sha256": PARQUET_SHA256,
        "parquet_bytes": PARQUET_BYTES,
        "source_member_sha256": MEMBER_SHA256,
        "native_core_sha256": NATIVE_SHA256,
        "candidate_retained": True,
        "publication_performed": False,
        "v4_admission_performed": False,
    }
    if any(
        prepared.get(key) != value
        for key, value in expected_preparation.items()
    ):
        raise ValueError("PBS preparation does not bind the exact candidate")
    parent = PUBLIC_PARENT_REVISION
    tree_sha256 = PUBLIC_TREE_SHA256
    if hashlib.sha256(readback_bytes).hexdigest() != PUBLIC_READBACK_SHA256:
        raise ValueError("PBS public-tree readback digest differs")
    readback = json.loads(readback_bytes)
    expected_readback: dict[str, Any] = {
        "dataset": DATASET,
        "revision": parent,
        "tree_sha256": tree_sha256,
        "entry_count": PUBLIC_TREE_ENTRY_COUNT,
        "pagination_next": False,
        "target_output_id": OUTPUT_ID,
        "target_parquet_sha256": PARQUET_SHA256,
        "matched_paths": [],
    }
    if hashlib.sha256(tree_bytes).hexdigest() != tree_sha256 or any(
        readback.get(key) != value for key, value in expected_readback.items()
    ):
        raise ValueError(
            "PBS public-tree readback differs from the frozen observation"
        )
    raw_entries: Any = json.loads(tree_bytes)
    if not isinstance(raw_entries, list):
        raise TypeError("PBS public-tree inventory is not a list")
    entries = cast("list[Any]", raw_entries)
    path = f"silver/pbs/v4/2026-04-01/{OUTPUT_ID}/values.parquet"
    if (
        len(entries) != PUBLIC_TREE_ENTRY_COUNT
        or any(not isinstance(entry, dict) for entry in entries)
        or any(entry.get("path") == path for entry in entries)
        or PARQUET_SHA256 in json.dumps(entries, sort_keys=True)
    ):
        raise ValueError(
            "PBS target already exists or public-tree inventory differs"
        )
    return {
        "schema_id": "global-medicines-atlas.pbs-reproduced-publication-plan",
        "schema_version": 1,
        "status": "dry_run_not_authorized_or_published",
        "dataset": DATASET,
        "expected_parent_revision": parent,
        "public_tree_sha256": tree_sha256,
        "output_id": OUTPUT_ID,
        "remote_path": path,
        "parquet_sha256": PARQUET_SHA256,
        "parquet_bytes": PARQUET_BYTES,
        "workflow_commit": prepared["workflow_commit"],
        "run_id": prepared["run_id"],
        "run_attempt": prepared["run_attempt"],
        "maintainer_publication_approved": False,
        "publication_performed": False,
        "v4_admission_performed": False,
        "required_before_mutation": [
            "Record exact publication authority separately from the rights attestation.",
            "Recheck the public parent revision and destination inventory; use parent-commit CAS.",
            "Retain the exact intent artifact before any external mutation.",
            "Rehash staged bytes immediately before mutation and verify them anonymously afterward.",
        ],
    }


def verify_live_publication_parent(public: Any, plan: dict[str, Any]) -> None:
    """Fail closed if the reviewed destination changed since the frozen tree."""
    expected_path = f"silver/pbs/v4/2026-04-01/{OUTPUT_ID}/values.parquet"
    expected = {
        "dataset": DATASET,
        "expected_parent_revision": PUBLIC_PARENT_REVISION,
        "remote_path": expected_path,
        "output_id": OUTPUT_ID,
        "parquet_sha256": PARQUET_SHA256,
        "parquet_bytes": PARQUET_BYTES,
    }
    if any(plan.get(key) != value for key, value in expected.items()):
        raise ValueError(
            "PBS publication plan differs from the exact candidate"
        )
    info = public.dataset_info(DATASET, files_metadata=True, timeout=30)
    if (
        info.sha != PUBLIC_PARENT_REVISION
        or info.private is not False
        or info.gated is not False
    ):
        raise ValueError("PBS public parent changed or is not public")
    siblings = cast("list[Any]", info.siblings or [])
    if not siblings or any(
        item.rfilename == expected_path for item in siblings
    ):
        raise ValueError(
            "PBS destination inventory is empty or already contains the target"
        )


def verify_anonymous_published_candidate(
    transport: Any, revision: str
) -> dict[str, Any]:
    """Verify the exact remote PBS output without credentials or mutation."""
    if len(revision) != REVISION_LENGTH or any(
        c not in "0123456789abcdef" for c in revision
    ):
        raise ValueError("PBS publication revision must be an exact commit")
    info = transport.public.dataset_info(
        DATASET, revision=revision, files_metadata=True, timeout=30
    )
    if (
        info.sha != revision
        or info.private is not False
        or info.gated is not False
    ):
        raise ValueError("PBS publication revision is not anonymously public")
    remote_path = f"silver/pbs/v4/2026-04-01/{OUTPUT_ID}/values.parquet"
    siblings = cast("list[Any]", info.siblings or [])
    matches = [item for item in siblings if item.rfilename == remote_path]
    if len(matches) != 1 or matches[0].size != PARQUET_BYTES:
        raise ValueError("PBS published object metadata differs")
    restored = transport.download_object(
        DATASET, revision, remote_path, PARQUET_BYTES, timeout=900
    )
    digest = hashlib.sha256()
    with restored.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if (
        restored.stat().st_size != PARQUET_BYTES
        or digest.hexdigest() != PARQUET_SHA256
    ):
        raise ValueError("PBS anonymous published bytes differ")
    return {
        "dataset": DATASET,
        "revision": revision,
        "path": remote_path,
        "sha256": PARQUET_SHA256,
        "bytes": PARQUET_BYTES,
        "anonymous_digest_verification": "passed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare(args.exact_commit, args.output)
    except Exception:  # Never emit source-bearing exception text.
        print(json.dumps({"status": "preparation_failed"}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
