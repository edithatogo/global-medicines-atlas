"""Write only a bounded aggregate receipt for the main-Actions PBS qualifier."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from global_medicines_atlas.pbs_hosted_qualification import (
    MAX_REPORT_BYTES,
    failure_report,
    run_hosted_qualification,
)


def main(argv: list[str] | None = None) -> int:
    """Emit an aggregate receipt; failures never expose source/error text."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--failure-only", action="store_true")
    args = parser.parse_args(argv)
    report = failure_report()
    if not args.failure_only:
        try:
            report = run_hosted_qualification(args.exact_commit)
        except Exception:  # Never log signed URLs or source-bearing exceptions.
            report = failure_report()
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
    args.output.write_text(json.dumps(envelope, sort_keys=True) + "\n")
    return 0 if report["status"] == "passed" or args.failure_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
