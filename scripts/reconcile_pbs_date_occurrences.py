"""Run the value-free PBS date occurrence crosswalk on pinned Actions input."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from qualify_historical_pbs_public import write_qualification_receipt

from global_medicines_atlas.pbs_date_occurrence_reconciliation import (
    run_hosted_date_occurrence_reconciliation,
)
from global_medicines_atlas.pbs_hosted_qualification import failure_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report: dict[str, Any]
    try:
        report = run_hosted_date_occurrence_reconciliation(args.exact_commit)
    except Exception as error:
        report = failure_report(error)
    write_qualification_receipt(args.output, report)
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
