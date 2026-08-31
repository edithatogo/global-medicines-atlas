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
    run_hosted_qualification,
)


def _write(output: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Atomically replace one bounded receipt; interrupted writes keep the old."""
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    if len(payload) > MAX_REPORT_BYTES:
        report = failure_report()
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
    parser.add_argument("--failure-only", action="store_true")
    args = parser.parse_args(argv)
    report = failure_report()
    latest: dict[str, Any] = {}

    def checkpoint(value: dict[str, Any]) -> None:
        nonlocal latest
        latest = _write(args.output, value)

    if not args.failure_only:
        try:
            report = run_hosted_qualification(
                args.exact_commit, progress=checkpoint
            )
        except Exception as error:  # Never log source-bearing exception text.
            report = failure_report(error)
            if "progress" in latest:
                report["progress"] = latest["progress"]
    report = _write(args.output, report)
    return 0 if report["status"] == "passed" or args.failure_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
