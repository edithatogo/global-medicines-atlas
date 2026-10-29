"""Screen source-local PBS reference literals and retain an aggregate receipt."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from global_medicines_atlas.pbs_hosted_qualification import (
    failure_report,
    run_hosted_native_reference_screen,
)

if __package__:
    from scripts.qualify_historical_pbs_public import (
        write_qualification_receipt,
    )
else:
    from qualify_historical_pbs_public import write_qualification_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("existing receipt must be preserved")
    latest: dict[str, Any] = {}

    def checkpoint(report: dict[str, Any]) -> None:
        nonlocal latest
        latest = write_qualification_receipt(args.output, report)

    try:
        report = run_hosted_native_reference_screen(
            args.exact_commit, progress=checkpoint
        )
    except Exception as error:
        report = failure_report(error)
        if "progress" in latest:
            report["progress"] = latest["progress"]
    report = write_qualification_receipt(args.output, report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
