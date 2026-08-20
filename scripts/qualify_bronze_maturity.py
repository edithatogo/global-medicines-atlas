"""Emit the bronze maturity qualification report from repository evidence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from global_medicines_atlas.bronze_maturity import (
    REPORT_RELATIVE,
    SCHEMA_RELATIVE,
    dump_report,
    evaluate_repository,
)

ROOT = Path(__file__).resolve().parents[1]


def _git_commit(root: Path) -> str:
    git_entry = root / ".git"
    if git_entry.is_file():
        marker = git_entry.read_text(encoding="utf-8").strip()
        _, _, locator = marker.partition(":")
        git_dir = Path(locator.strip())
        if not git_dir.is_absolute():
            git_dir = (root / git_dir).resolve()
    elif git_entry.is_dir():
        git_dir = git_entry
    else:
        return "unspecified"
    head_path = git_dir / "HEAD"
    if not head_path.is_file():
        return "unspecified"
    head = head_path.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        ref_path = git_dir / ref
        if not ref_path.is_file():
            common_dir_path = git_dir / "commondir"
            if common_dir_path.is_file():
                common_dir = Path(
                    common_dir_path.read_text(encoding="utf-8").strip()
                )
                if not common_dir.is_absolute():
                    common_dir = (git_dir / common_dir).resolve()
                ref_path = common_dir / ref
        if ref_path.is_file():
            return ref_path.read_text(encoding="utf-8").strip()
        return "unspecified"
    return head


def main(argv: list[str] | None = None) -> int:
    """Write and validate the bronze maturity report."""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / REPORT_RELATIVE,
        help="Report JSON path",
    )
    args = parser.parse_args(argv)
    report = evaluate_repository(
        ROOT,
        clock=lambda: datetime.now(UTC),
        git_commit=_git_commit(ROOT),
    )
    schema = json.loads((ROOT / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
        report
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dump_report(report), encoding="utf-8")
    state = report["qualification_state"]
    mature = report["bronze_mature"]
    print(
        f"wrote {args.output.relative_to(ROOT)} "
        f"qualification_state={state} bronze_mature={mature}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
