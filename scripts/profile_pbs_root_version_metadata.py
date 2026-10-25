"""Write a value-free receipt for the pinned PBS root version metadata."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.pbs_hosted_qualification import (
    failure_report,
    run_hosted_root_schema_version_metadata,
)

if __package__:
    from scripts.qualify_historical_pbs_public import (
        write_qualification_receipt,
    )
else:
    from qualify_historical_pbs_public import write_qualification_receipt


def main(argv: list[str] | None = None) -> int:
    """Run only in exact-main Actions and persist a bounded metadata receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output already exists")
    try:
        report = run_hosted_root_schema_version_metadata(
            args.exact_commit, args.output
        )
    except Exception as error:
        report = failure_report(error)
    write_qualification_receipt(args.output, report)
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
