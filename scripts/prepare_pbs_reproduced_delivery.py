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
import sys
from pathlib import Path
from typing import Any

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
NATIVE_SHA256 = (
    "890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25"
)
ARCHIVE_SHA256 = (
    "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
)
DATASET = "edithatogo/australian-pbs-source-archive"
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
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


def prepare(exact_commit: str, output: Path) -> dict[str, Any]:
    """Rebuild and retain the exact candidate without publication or admission."""
    context = hosted._context(exact_commit)  # pyright: ignore[reportPrivateUsage] -- reuse the exact hosted guard
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
