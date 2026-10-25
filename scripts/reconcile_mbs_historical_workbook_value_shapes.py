"""Reconcile six exact-main MBS workbook value-shape reports."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

if __package__:
    from scripts.profile_frozen_mbs_sidecars import require_main_actions
    from scripts.profile_mbs_historical_workbook_value_shapes import (
        ARCHIVE_COUNT,
        COHORT_REPORT,
        COHORT_SHA256,
        FIELD_STATE_REPORT,
        FIELD_STATE_SHA256,
        HEADER_REPORT,
        HEADER_SHA256,
        WORKBOOK_COUNT,
    )
else:
    from profile_frozen_mbs_sidecars import require_main_actions
    from profile_mbs_historical_workbook_value_shapes import (
        ARCHIVE_COUNT,
        COHORT_REPORT,
        COHORT_SHA256,
        FIELD_STATE_REPORT,
        FIELD_STATE_SHA256,
        HEADER_REPORT,
        HEADER_SHA256,
        WORKBOOK_COUNT,
    )

from global_medicines_atlas.mbs_archive_inventory import (
    DATASET,
    REVISION,
    load_archives,
)
from global_medicines_atlas.mbs_historical_workbook_value_shapes import (
    merge_archive_profiles,
)

HEADER_WORKFLOW_COMMIT = "43f72eb7844a1f3adf13ec1fb34788c1bb8faf71"
COHORT_RUN_ID = 39724026209


def _read_bound(path: Path, expected_sha256: str) -> dict[str, Any]:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError(f"bound input digest differs: {path.name}")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError(f"bound input report malformed: {path.name}")
    return cast("dict[str, Any]", value)


def _source_record(source: Any) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "source_path": source.source_path,
        "source_sha256": source.source_sha256,
        "source_bytes": source.source_bytes,
        "acquisition_id": source.acquisition_id,
        "b1_sha256": source.b1_sha256,
        "b2_sha256": source.b2_sha256,
    }


def reconcile(exact_commit: str, input_dir: Path) -> dict[str, Any]:  # ruff: ignore[too-many-branches] -- validate six archive partitions against 91 exact candidate identities
    require_main_actions(exact_commit)
    header, cohort, field_state = (
        _read_bound(HEADER_REPORT, HEADER_SHA256),
        _read_bound(COHORT_REPORT, COHORT_SHA256),
        _read_bound(FIELD_STATE_REPORT, FIELD_STATE_SHA256),
    )
    reports: list[dict[str, Any]] = []
    for index in range(ARCHIVE_COUNT):
        path = input_dir / f"historical-workbook-value-shapes-{index}.json"
        payload = path.read_bytes()
        report_value = json.loads(payload)
        if not isinstance(report_value, dict):
            raise TypeError("MBS archive value-shape report malformed")
        report = cast("dict[str, Any]", report_value)
        if (
            report.get("status") != "passed"
            or report.get("workflow_commit") != exact_commit
        ):
            raise ValueError(
                "MBS archive value-shape report failed or commit differs"
            )
        if report.get("archive_index") != index:
            raise ValueError("MBS archive value-shape report index differs")
        reports.append(report)
    if header.get("workflow_commit") != HEADER_WORKFLOW_COMMIT:
        raise ValueError("bound MBS header cohort main commit differs")
    if (
        cohort.get("run_id") != COHORT_RUN_ID
        or field_state.get("status")
        != "field_states_reconciled_with_semantic_limits"
    ):
        raise ValueError("bound MBS field-state and candidate evidence differs")
    archives = load_archives(Path(__file__).resolve().parents[1])
    if len(archives) != ARCHIVE_COUNT:
        raise ValueError("MBS frozen archive denominator differs")
    for index, report in enumerate(reports):
        if (
            report.get("dataset") != DATASET
            or report.get("revision") != REVISION
        ):
            raise ValueError("MBS archive dataset/revision differs")
        if report.get("source") != _source_record(archives[index]):
            raise ValueError("MBS source B1/B2 identity differs")
        if report.get("input_report_digests") != {
            "header_cohort_sha256": HEADER_SHA256,
            "candidate_cohort_sha256": COHORT_SHA256,
            "field_state_sha256": FIELD_STATE_SHA256,
        }:
            raise ValueError("MBS value-shape bound input digest differs")
    merged = merge_archive_profiles(reports, ARCHIVE_COUNT)
    if merged["workbook_count"] != WORKBOOK_COUNT:
        raise ValueError("MBS value-shape workbook denominator differs")
    expected: dict[int, dict[str, Any]] = {}
    for group, candidate in cohort["candidate_outputs_by_group"].items():
        expected[int(group)] = candidate
    observed = {
        row["candidate_group"]: row for row in merged["workbook_bindings"]
    }
    if len(expected) != WORKBOOK_COUNT or set(observed) != set(expected):
        raise ValueError("MBS value-shape candidate group set differs")
    for group, candidate in expected.items():
        row = observed[group]
        observed_identity = (
            row["candidate_output_id"],
            row["candidate_parquet_sha256"],
            row["candidate_parquet_bytes"],
            row["member_sha256"],
            row["member_path_sha256"],
            row["source_sha256"],
        )
        expected_identity = (
            candidate["output_id"],
            candidate["parquet_sha256"],
            candidate["parquet_bytes"],
            candidate["member_sha256"],
            candidate["member_path_sha256"],
            candidate["source_sha256"],
        )
        if observed_identity != expected_identity:
            raise ValueError("MBS value-shape candidate binding differs")
    return {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-value-shape-cohort",
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": exact_commit,
        "dataset": DATASET,
        "revision": REVISION,
        "input_digests": {
            "header_cohort_sha256": HEADER_SHA256,
            "candidate_cohort_sha256": COHORT_SHA256,
            "field_state_sha256": FIELD_STATE_SHA256,
        },
        "candidate_cohort_run_id": cohort["run_id"],
        "header_cohort_workflow_commit": header["workflow_commit"],
        "field_state_report_sha256": FIELD_STATE_SHA256,
        **merged,
        "source_values_emitted": False,
        "source_column_meanings_qualified": False,
        "calendar_year_vs_service_year_resolved": False,
        "calendar_month_vs_processing_month_resolved": False,
        "date_interpreted": False,
        "p7_workbook_in_scope": False,
        "p7_date_inference_applied": False,
        "p7_domain_date_semantics_qualified": False,
        "currency_interpreted": False,
        "cross_era_equivalence_claimed": False,
        "new_sources": 0,
        "new_admissions": 0,
        "consumer_canaries": 0,
        "publications": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = reconcile(args.exact_commit, args.input_dir)
    payload = (
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError(
            "existing MBS value-shape cohort report must be preserved"
        )
    args.output.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
