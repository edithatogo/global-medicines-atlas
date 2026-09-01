"""Prepare one bounded transient PBS reference DAG node on main Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_hosted_qualification import (
    failure_report,
    run_hosted_reference_group,
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


def _run(
    args: argparse.Namespace,
    checkpoint: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    if args.global_index:
        if args.group_index is not None:
            raise ValueError("invalid PBS global index arguments")
        return run_hosted_reference_node(
            args.exact_commit,
            args.output,
            shard_count=args.reference_shards,
            progress=checkpoint,
        )
    if args.group_index is None:
        raise ValueError("PBS partition group index is required")
    return run_hosted_reference_group(
        args.exact_commit,
        args.output,
        shard_count=args.reference_shards,
        group_index=args.group_index,
        group_count=args.group_count,
        progress=checkpoint,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--reference-shards", required=True, type=int)
    parser.add_argument("--global-index", action="store_true")
    parser.add_argument("--group-index", type=int)
    parser.add_argument("--group-count", type=int, default=4)
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
        report = _run(args, checkpoint)
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
