"""Reconcile value-free field states for current MBS workbook receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scripts.profile_mbs_historical_workbook_value_shapes import (  # ruff: ignore[module-import-not-at-top-of-file]
    FIELD_STATE_SHA256,
)

from global_medicines_atlas.mbs_workbook_field_reconciliation import (  # ruff: ignore[module-import-not-at-top-of-file]
    HEADER_PATH,
    P7_DATE_PROFILE_PATH,
    P7_RULES_PATH,
    P7_RUN_RECEIPT_PATH,
    P7_TYPED_PATH,
    PACKAGE_PATH,
    bind_historical_workbook_value_shapes,
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
    parser.add_argument("--p7-inferred-candidate-typed", type=Path)
    parser.add_argument(
        "--p7-inferred-candidate-qualification-receipt", type=Path
    )
    parser.add_argument("--p7-inferred-candidate-date-inference", type=Path)
    parser.add_argument(
        "--p7-value-era-rules", type=Path, default=ROOT / P7_RULES_PATH
    )
    parser.add_argument(
        "--value-shape-cohort",
        type=Path,
        help="bind the completed six-archive historical workbook value-shape receipt",
    )
    parser.add_argument(
        "--value-shape-run-id",
        type=int,
        help="exact GitHub Actions run that produced the value-shape cohort receipt",
    )
    parser.add_argument(
        "--output", type=Path, help="write the report here; stdout by default"
    )
    args = parser.parse_args()
    candidate_args = (
        args.p7_inferred_candidate_typed,
        args.p7_inferred_candidate_qualification_receipt,
        args.p7_inferred_candidate_date_inference,
    )
    if any(candidate_args) and not all(candidate_args):
        parser.error(
            "inferred-candidate mode requires typed output, hosted qualification receipt, and inference receipt"
        )
    if (args.value_shape_cohort is None) != (args.value_shape_run_id is None):
        parser.error(
            "value-shape cohort and exact workflow run ID are required together"
        )
    paths = {
        "package_cohort": args.package_cohort,
        "header_cohort": args.header_cohort,
        "p7_typed": args.p7_inferred_candidate_typed or args.p7_typed,
        "p7_date_profile": args.p7_date_profile,
        "p7_value_era_rules": args.p7_value_era_rules,
    }
    candidate_artifact_path = None
    if all(candidate_args):
        receipt_path = args.p7_inferred_candidate_qualification_receipt
        paths["p7_candidate_qualification_receipt"] = receipt_path
        paths["p7_date_inference"] = args.p7_inferred_candidate_date_inference
        candidate_artifact_path = str(
            args.p7_inferred_candidate_typed.resolve().relative_to(
                ROOT.resolve()
            )
        )
    else:
        paths["p7_run_receipt"] = args.p7_run_receipt
    report = reconcile_from_paths(
        paths, candidate_artifact_path=candidate_artifact_path
    )
    if args.value_shape_cohort is not None:
        if args.output is None:
            parser.error("value-shape successor requires an explicit --output")
        value_shape_bytes = args.value_shape_cohort.read_bytes()
        value_shape_report = json.loads(value_shape_bytes)
        if not isinstance(value_shape_report, dict):
            parser.error("value-shape cohort receipt must be an object")
        value_shape_report = cast("dict[str, Any]", value_shape_report)
        report = bind_historical_workbook_value_shapes(
            report,
            value_shape_report,
            value_shape_path=str(
                args.value_shape_cohort.resolve().relative_to(ROOT.resolve())
            ),
            value_shape_sha256=hashlib.sha256(value_shape_bytes).hexdigest(),
            expected_field_state_sha256=FIELD_STATE_SHA256,
            value_shape_workflow_run_id=args.value_shape_run_id,
        )
    rendered = canonical_json(report)
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        if args.value_shape_cohort is not None and (
            args.output.exists() or args.output.is_symlink()
        ):
            raise FileExistsError(
                "existing value-shape field-state successor must be preserved"
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
