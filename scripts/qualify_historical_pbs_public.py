"""Write only a bounded aggregate receipt for the main-Actions PBS qualifier."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from global_medicines_atlas.pbs_hosted_qualification import (
    MAX_REPORT_BYTES,
    failure_report,
    metadata_probe_report,
    run_hosted_metadata_probe,
    run_hosted_qualification,
)


def _write(output: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Atomically replace one bounded receipt; interrupted writes keep the old."""
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    if len(payload) > MAX_REPORT_BYTES:
        report = (
            metadata_probe_report(failure_report())
            if report.get("operation") == "pbs-public-metadata-diagnostic"
            else failure_report()
        )
        payload = json.dumps(
            report, sort_keys=True, separators=(",", ":")
        ).encode()
    envelope = {
        "report_sha256": hashlib.sha256(payload).hexdigest(),
        "report": report,
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(envelope, sort_keys=True) + "\n")
    temporary.replace(output)
    return report


def main(argv: list[str] | None = None) -> int:
    """Emit aggregate checkpoints and a final receipt without source text."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--projection",
        choices=("native", "domain", "entities", "references", "dates"),
    )
    parser.add_argument("--reference-shard-index", type=int)
    parser.add_argument("--reference-shard-count", type=int)
    parser.add_argument("--failure-only", action="store_true")
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args(argv)
    shard_values = (args.reference_shard_index, args.reference_shard_count)
    if (None in shard_values) != (shard_values == (None, None)):
        parser.error(
            "reference shard index and count must be supplied together"
        )
    reference_shard = (
        None
        if shard_values == (None, None)
        else (args.reference_shard_index, args.reference_shard_count)
    )
    if reference_shard is not None and args.projection != "references":
        parser.error("reference shards require the references projection")
    report = failure_report()
    if args.metadata_only:
        report = metadata_probe_report(report)
    latest: dict[str, Any] = {}

    def checkpoint(value: dict[str, Any]) -> None:
        nonlocal latest
        latest = _write(args.output, value)

    if not args.failure_only:
        try:  # ruff: ignore[too-many-statements-in-try-clause] -- one bounded runner transaction
            runner = (
                run_hosted_metadata_probe
                if args.metadata_only
                else run_hosted_qualification
            )
            runner_kwargs: dict[str, Any] = {"progress": checkpoint}
            if not args.metadata_only:
                runner_kwargs["projection"] = args.projection
                runner_kwargs["reference_shard"] = reference_shard
            report = runner(args.exact_commit, **runner_kwargs)
        except Exception as error:  # Never log source-bearing exception text.
            report = failure_report(error)
            if "progress" in latest:
                report["progress"] = latest["progress"]
    if args.projection is not None:
        report["projection_shard"] = args.projection
    if reference_shard is not None and "reference_window" not in report:
        report["reference_shard"] = {
            "index": reference_shard[0],
            "count": reference_shard[1],
        }
    if args.metadata_only:
        report = metadata_probe_report(report)
    report = _write(args.output, report)
    expected = "metadata_verified" if args.metadata_only else "passed"
    return 0 if report["status"] == expected or args.failure_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
