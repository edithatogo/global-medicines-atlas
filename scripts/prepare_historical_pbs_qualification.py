"""Prepare transient same-run PBS qualification inputs on main Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from global_medicines_atlas.pbs_hosted_qualification import (
    failure_report,
    run_hosted_preparation,
)


def _write(path: Path, report: dict[str, Any]) -> None:
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    path.write_text(
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


def _write_atomic(path: Path, report: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    _write(temporary, report)
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--reference-shards", required=True, type=int)
    args = parser.parse_args(argv)
    checkpoints: list[dict[str, Any]] = []

    def persist(report: dict[str, Any]) -> None:
        checkpoints.append(report)
        bounded = dict(report)
        bounded["operation"] = "pbs-qualification-preparation"
        bounded["publication_performed"] = False
        _write_atomic(args.receipt, bounded)

    try:
        report = run_hosted_preparation(
            args.exact_commit,
            args.output,
            shard_count=args.reference_shards,
            progress=persist,
        )
    except Exception as error:  # Never serialize source-bearing exception text.
        report = failure_report(error)
        report["operation"] = "pbs-qualification-preparation"
        report["publication_performed"] = False
        if checkpoints and isinstance(
            progress_value := checkpoints[-1].get("progress"), dict
        ):
            report["progress"] = progress_value
            stage = progress_value.get("stage")
            if isinstance(stage, str):
                report["failure_stage"] = stage
    _write_atomic(args.receipt, report)
    return 0 if report["status"] == "prepared" else 1


if __name__ == "__main__":
    raise SystemExit(main())
