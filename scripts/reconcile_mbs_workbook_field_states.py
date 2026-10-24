"""Reconcile value-free field states for current MBS workbook receipts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from global_medicines_atlas.mbs_workbook_field_reconciliation import (  # ruff: ignore[module-import-not-at-top-of-file]
    HEADER_PATH,
    P7_DATE_INFERENCE_PATH,
    P7_DATE_PROFILE_PATH,
    P7_RULES_PATH,
    P7_RUN_RECEIPT_PATH,
    P7_TYPED_PATH,
    PACKAGE_PATH,
    canonical_json,
    reconcile_from_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-cohort", type=Path, default=ROOT / PACKAGE_PATH
    )
    parser.add_argument(
        "--header-cohort", type=Path, default=ROOT / HEADER_PATH
    )
    parser.add_argument("--p7-typed", type=Path, default=ROOT / P7_TYPED_PATH)
    parser.add_argument(
        "--p7-run-receipt", type=Path, default=ROOT / P7_RUN_RECEIPT_PATH
    )
    parser.add_argument(
        "--p7-date-profile", type=Path, default=ROOT / P7_DATE_PROFILE_PATH
    )
    parser.add_argument(
        "--p7-date-inference",
        type=Path,
        default=ROOT / P7_DATE_INFERENCE_PATH,
    )
    parser.add_argument(
        "--p7-value-era-rules", type=Path, default=ROOT / P7_RULES_PATH
    )
    parser.add_argument(
        "--output", type=Path, help="write the report here; stdout by default"
    )
    args = parser.parse_args()
    paths = {
        "package_cohort": args.package_cohort,
        "header_cohort": args.header_cohort,
        "p7_typed": args.p7_typed,
        "p7_run_receipt": args.p7_run_receipt,
        "p7_date_profile": args.p7_date_profile,
        "p7_date_inference": args.p7_date_inference,
        "p7_value_era_rules": args.p7_value_era_rules,
    }
    report = reconcile_from_paths(paths)
    rendered = canonical_json(report)
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
