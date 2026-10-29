"""Qualify bounded same-member PBS XLink candidates on GitHub Actions."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from global_medicines_atlas.pbs_hosted_qualification import (
    DATASET,
    RECEIPT,
    REVISION,
    _RetryBudget,  # ruff: ignore[import-private-name] -- reuse exact verified-input route  # pyright: ignore[reportPrivateUsage]
    _verified_inputs,  # ruff: ignore[import-private-name] -- reuse exact verified-input route  # pyright: ignore[reportPrivateUsage]
    failure_report,
)
from global_medicines_atlas.pbs_xlink_reference_candidates import (
    export_pbs_xlink_reference_candidates,
)

if __package__:
    from scripts.qualify_historical_pbs_public import (
        write_qualification_receipt,
    )
else:
    from qualify_historical_pbs_public import write_qualification_receipt


def run(
    exact_commit: str, receipt_path: Path, xlink_output: Path
) -> dict[str, Any]:
    """Bind one candidate artifact and receipt to exact hosted inputs."""
    latest: dict[str, Any] = {}

    def checkpoint(report: dict[str, Any]) -> None:
        nonlocal latest
        latest = write_qualification_receipt(receipt_path, report)

    retry = _RetryBudget(progress=checkpoint)
    inputs: Any | None = None
    try:
        inputs = _verified_inputs(exact_commit, transport=None, retry=retry)
        candidate = export_pbs_xlink_reference_candidates(
            inputs.archive,
            inputs.xml,
            inputs.parent,
            inputs.binding,
            xlink_output,
        )
        report = {
            "schema_id": "global-medicines-atlas.pbs-native-xlink-candidate-screen",
            "schema_version": 1,
            "status": "passed",
            **inputs.context,
            "operation": "pbs-native-xlink-candidate-screen",
            "dataset": DATASET,
            "revision": REVISION,
            "archive_sha256": inputs.binding.archive_payload.sha256,
            "archive_size_bytes": inputs.binding.archive_payload.byte_count,
            "member_path": inputs.binding.member_path,
            "member_sha256": inputs.binding.member_payload.sha256,
            "member_size_bytes": inputs.binding.member_payload.byte_count,
            "source_receipt_sha256": inputs.parent.digest(),
            "source_receipt_file_sha256": RECEIPT.sha256,
            "candidate_artifact": candidate,
            "semantic_relationships_qualified": False,
            "source_values_emitted": False,
            "external_targets_fetched": 0,
            "admissions_created": 0,
            "publication_performed": False,
            "canaries_performed": 0,
            "new_sources_added": 0,
        }
    except Exception as error:
        report = failure_report(error)
        report.update({
            "schema_id": "global-medicines-atlas.pbs-native-xlink-candidate-screen",
            "schema_version": 1,
            "operation": "pbs-native-xlink-candidate-screen",
            "semantic_relationships_qualified": False,
            "source_values_emitted": False,
            "external_targets_fetched": 0,
            "admissions_created": 0,
            "publication_performed": False,
            "canaries_performed": 0,
            "new_sources_added": 0,
        })
        if inputs is not None:
            report.update({
                **inputs.context,
                "dataset": DATASET,
                "revision": REVISION,
                "archive_sha256": inputs.binding.archive_payload.sha256,
                "archive_size_bytes": inputs.binding.archive_payload.byte_count,
                "member_path": inputs.binding.member_path,
                "member_sha256": inputs.binding.member_payload.sha256,
                "member_size_bytes": inputs.binding.member_payload.byte_count,
                "source_receipt_sha256": inputs.parent.digest(),
                "source_receipt_file_sha256": RECEIPT.sha256,
            })
        if "progress" in latest:
            report["progress"] = latest["progress"]
    return write_qualification_receipt(receipt_path, report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--xlink-output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("existing receipt must be preserved")
    if args.xlink_output.exists():
        parser.error("existing XLink candidate artifact must be preserved")
    report = run(args.exact_commit, args.output, args.xlink_output)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
