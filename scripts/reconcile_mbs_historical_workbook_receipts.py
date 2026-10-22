"""Reconcile aggregate-only protected receipts for all frozen MBS workbooks."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from global_medicines_atlas.mbs_archive_inventory import DATASET, REVISION
from global_medicines_atlas.mbs_historical_csv_package import (
    canonical_package_json,
)

if __package__:
    from scripts.qualify_mbs_historical_workbook_packages import (
        GROUP_COUNT,
        select_group,
    )
else:
    from qualify_mbs_historical_workbook_packages import (
        GROUP_COUNT,
        select_group,
    )


def _format_profiles(root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for index in range(6):
        path = (
            root
            / "quality/qualifications"
            / f"mbs-historical-native-formats-{index}-20261022-39709530322.json"
        )
        report = json.loads(path.read_bytes())
        if report["status"] != "passed" or report["archive_index"] != index:
            raise ValueError("historical format profile state differs")
        source_sha = report["result"]["source_sha256"]
        for row in report["result"]["members"]:
            if row["declared_suffix_hint"] != ".xlsx":
                continue
            key = source_sha, row["verified_relative_path_sha256"]
            if key in found:
                raise ValueError(
                    "historical workbook format identity duplicated"
                )
            found[key] = row
    if len(found) != GROUP_COUNT:
        raise ValueError("historical workbook format denominator differs")
    return found


COMMIT_LENGTH = 40
MAX_RECEIPT_BYTES = 1_000_000


def reconcile(  # ruff: ignore[too-many-statements,too-many-locals] -- verify every frozen identity, native profile and package count in one cohort pass
    root: Path, artifact_root: Path, run_id: int, commit: str
) -> dict[str, Any]:
    """Require every exact member once, with independent format and manifest pins."""
    if not artifact_root.is_dir() or artifact_root.is_symlink():
        raise ValueError("workbook receipt directory is invalid")
    if len(commit) != COMMIT_LENGTH or any(
        ch not in "0123456789abcdef" for ch in commit
    ):
        raise ValueError("workbook workflow commit is invalid")
    profiles = _format_profiles(root)
    expected = {
        group: asdict(select_group(root, group)[0])
        for group in range(GROUP_COUNT)
    }
    paths = sorted(artifact_root.rglob("historical-workbook-packages.json"))
    if len(paths) != GROUP_COUNT:
        raise ValueError("historical workbook receipt denominator differs")
    seen: set[int] = set()
    output_ids: set[str] = set()
    member_ids: set[tuple[str, str]] = set()
    totals = {
        "records": 0,
        "cells": 0,
        "rows": 0,
        "sheets": 0,
        "native_zip_members": 0,
        "decimal_candidates": 0,
        "missing_native_values": 0,
    }
    receipt_hashes: dict[str, str] = {}
    for path in paths:
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size > MAX_RECEIPT_BYTES
        ):
            raise ValueError("historical workbook receipt file is invalid")
        raw = path.read_bytes()
        report = json.loads(raw)
        group = report["group"]
        if (
            type(group) is not int  # ruff: ignore[too-many-boolean-expressions] -- exact bound identity
            or group not in expected
            or group in seen
            or report["status"] != "passed"
            or report["workflow_commit"] != commit
            or report["dataset"] != DATASET
            or report["revision"] != REVISION
            or report["group_count"] != GROUP_COUNT
            or report["cohort_members"] != GROUP_COUNT
            or report["selected_member_bindings"] != [expected[group]]
            or len(report["members"]) != 1
        ):
            raise ValueError("historical workbook receipt identity differs")
        if (
            any(
                report[key] != 0
                for key in (
                    "new_sources",
                    "new_admissions",
                    "new_federated_canaries",
                    "publications",
                )
            )
            or report["rights_conclusion_changed"]
            or report["native_member_names_or_values_emitted"] is not False
        ):
            raise ValueError("historical workbook receipt boundary differs")
        member = expected[group]
        entry = report["members"][0]
        manifest = entry["manifest"]
        source = member["source"]
        key = source["source_sha256"], member["path_sha256"]
        profile = profiles[key]
        coverage = manifest["coverage"]
        identity = {
            name: value
            for name, value in manifest.items()
            if name != "output_id"
        }
        output_id = hashlib.sha256(canonical_package_json(identity)).hexdigest()
        if (
            manifest["member_binding"] != member  # ruff: ignore[too-many-boolean-expressions] -- exact source/package bindings
            or manifest["output_id"] != output_id
            or output_id in output_ids
            or key in member_ids
            or manifest["schema_id"]
            != "global-medicines-atlas.mbs-historical-workbook-package"
            or manifest["schema_version"] != 1
            or manifest["candidate_only"] is not True
            or any(manifest["boundaries"].values())
            or profile["bytes"] != member["byte_count"]
            or profile["sha256"] != member["sha256"]
            or profile["ordinal"] != member["ordinal"]
            or profile["status"] != "parsed"
            or profile["native_profile"]["worksheet_count"]
            != coverage["sheets"]
            or profile["native_profile"]["member_count"]
            != coverage["kinds"]["member"]
            or not entry["two_builds_equal"]
            or not entry["complete_native_restore_verified"]
            or entry["native_values_or_names_emitted"] is not False
        ):
            raise ValueError("historical workbook package identity differs")
        kinds = coverage["kinds"]
        if (
            coverage["records"] != entry["duckdb_records"]  # ruff: ignore[too-many-boolean-expressions] -- native and DuckDB denominators
            or coverage["records"] != sum(kinds.values())
            or coverage["cells"] != entry["duckdb_cells"]
            or coverage["cells"] != kinds["cell"]
            or coverage["rows"] != entry["duckdb_rows"]
            or coverage["rows"] != kinds["row"]
            or coverage["sheets"] != entry["duckdb_sheets"]
            or coverage["sheets"] != kinds["sheet"]
            or coverage["cells"] != sum(coverage["native_states"].values())
            or coverage["records"]
            != sum(coverage["conversion_statuses"].values())
        ):
            raise ValueError("historical workbook package counts differ")
        seen.add(group)
        output_ids.add(output_id)
        member_ids.add(key)
        receipt_hashes[str(group)] = hashlib.sha256(raw).hexdigest()
        totals["records"] += coverage["records"]
        totals["cells"] += coverage["cells"]
        totals["rows"] += coverage["rows"]
        totals["sheets"] += coverage["sheets"]
        totals["native_zip_members"] += kinds["member"]
        totals["decimal_candidates"] += coverage["conversion_statuses"].get(
            "converted", 0
        )
        totals["missing_native_values"] += coverage["native_states"].get(
            "null", 0
        )
    if seen != set(expected):
        raise ValueError("historical workbook group coverage differs")
    return {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-cohort-reconciliation",
        "schema_version": 1,
        "status": "passed",
        "run_id": run_id,
        "workflow_commit": commit,
        "dataset": DATASET,
        "revision": REVISION,
        "groups": GROUP_COUNT,
        "unique_member_identities": len(member_ids),
        "unique_output_ids": len(output_ids),
        "totals": totals,
        "receipt_sha256_by_group": receipt_hashes,
        "source_column_semantics_qualified": False,
        "new_admissions": 0,
        "new_federated_canaries": 0,
        "publications": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--workflow-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("existing reconciliation must be preserved")
    result = reconcile(
        Path(__file__).resolve().parents[1],
        args.artifact_root,
        args.run_id,
        args.workflow_commit,
    )
    args.output.write_bytes(canonical_package_json(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
