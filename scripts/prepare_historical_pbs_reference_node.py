"""Prepare one bounded transient PBS reference DAG node on main Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_hosted_qualification import (
    failure_report,
    run_hosted_reference_node,
)


def _write(path: Path, report: dict[str, Any]) -> None:
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "report": report,
                "report_sha256": hashlib.sha256(payload).hexdigest(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--reference-shards", required=True, type=int)
    parser.add_argument("--shard-index", type=int)
    args = parser.parse_args(argv)
    checkpoints: list[dict[str, Any]] = []

    def checkpoint(report: dict[str, Any]) -> None:
        checkpoints.append(report)
        bounded = dict(report)
        bounded.update({
            "operation": "pbs-reference-node-preparation",
            "publication_performed": False,
        })
        _write(args.receipt, bounded)

    try:
        report = run_hosted_reference_node(
            args.exact_commit,
            args.output,
            shard_count=args.reference_shards,
            shard_index=args.shard_index,
            progress=checkpoint,
        )
    except Exception as error:  # Never serialize source-bearing exception text.
        report = failure_report(error)
        report.update({
            "operation": "pbs-reference-node-preparation",
            "publication_performed": False,
        })
        if checkpoints and isinstance(
            progress := checkpoints[-1].get("progress"), dict
        ):
            progress = cast("dict[str, Any]", progress)
            report["progress"] = progress
            stage = progress.get("stage")
            if isinstance(stage, str):
                report["failure_stage"] = stage
    _write(args.receipt, report)
    return 0 if report["status"] == "prepared" else 1


if __name__ == "__main__":
    raise SystemExit(main())
