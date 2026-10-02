"""Emit the versioned Bronze receipt cohort and deferred-source list."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from global_medicines_atlas.bronze_receipt_cohort import (
    MARKDOWN_RELATIVE,
    REPORT_RELATIVE,
    SCHEMA_RELATIVE,
    build_bronze_receipt_cohort,
    dump_report,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    """Build, validate, and write both cohort projections."""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        help="Qualification JSON path",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        help="Human-readable cohort and future-source list",
    )
    args = parser.parse_args(argv)
    root = args.root
    report_output = args.report_output or root / REPORT_RELATIVE
    markdown_output = args.markdown_output or root / MARKDOWN_RELATIVE
    report = build_bronze_receipt_cohort(root)
    schema = json.loads((root / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
        report
    )
    report_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(dump_report(report), encoding="utf-8")
    markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"wrote {report_output} "
        f"cohort={report['qualified_cohort']['source_count']} "
        f"deferred={report['deferred_source_ledger']['source_count']}"
    )
    print(f"wrote {markdown_output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
