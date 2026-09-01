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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--reference-shards", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        report = run_hosted_preparation(
            args.exact_commit,
            args.output,
            shard_count=args.reference_shards,
        )
    except Exception as error:  # Never serialize source-bearing exception text.
        report = failure_report(error)
        report["operation"] = "pbs-qualification-preparation"
        report["publication_performed"] = False
    _write(args.receipt, report)
    return 0 if report["status"] == "prepared" else 1


if __name__ == "__main__":
    raise SystemExit(main())
