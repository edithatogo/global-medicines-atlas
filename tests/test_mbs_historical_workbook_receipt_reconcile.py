"""Cohort reconciliation rejects missing and identity-drifted aggregate receipts."""

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest
from scripts import reconcile_mbs_historical_workbook_receipts as module

from global_medicines_atlas.mbs_historical_csv_package import (
    canonical_package_json,
)

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40


def fixture_receipt(tmp_path, monkeypatch):
    original_member = module.select_group(ROOT, 0)[0]
    member = asdict(original_member)
    source = member["source"]
    key = source["source_sha256"], member["path_sha256"]
    profile = module._format_profiles(ROOT)[key]
    monkeypatch.setattr(module, "GROUP_COUNT", 1)
    monkeypatch.setattr(
        module, "_format_profiles", lambda _root: {key: profile}
    )
    monkeypatch.setattr(
        module, "select_group", lambda _root, _group: (original_member,)
    )
    coverage = {
        "records": 6 + profile["native_profile"]["member_count"],
        "cells": 3,
        "rows": 2,
        "sheets": profile["native_profile"]["worksheet_count"],
        "kinds": {
            "binding": 1,
            "cell": 3,
            "row": 2,
            "sheet": profile["native_profile"]["worksheet_count"],
            "member": profile["native_profile"]["member_count"],
        },
        "native_states": {"value": 2, "null": 1},
        "conversion_statuses": {
            "converted": 2,
            "missing_value": 1,
            "not_numeric_cell": 0,
        },
    }
    coverage["records"] = sum(coverage["kinds"].values())
    coverage["conversion_statuses"]["not_numeric_cell"] = (
        coverage["records"] - 3
    )
    manifest = {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-package",
        "schema_version": 1,
        "candidate_only": True,
        "member_binding": member,
        "coverage": coverage,
        "parquet": {"bytes": 20, "sha256": "b" * 64},
        "boundaries": {
            "admitted": False,
            "published": False,
            "rights_qualified": False,
            "semantics_qualified": False,
        },
    }
    manifest["output_id"] = hashlib.sha256(
        canonical_package_json(manifest)
    ).hexdigest()
    receipt = {
        "status": "passed",
        "workflow_commit": COMMIT,
        "dataset": module.DATASET,
        "revision": module.REVISION,
        "group": 0,
        "group_count": 1,
        "cohort_members": 1,
        "selected_member_bindings": [member],
        "members": [
            {
                "manifest": manifest,
                "duckdb_records": coverage["records"],
                "duckdb_cells": 3,
                "duckdb_rows": 2,
                "duckdb_sheets": coverage["sheets"],
                "two_builds_equal": True,
                "complete_native_restore_verified": True,
                "native_values_or_names_emitted": False,
            }
        ],
        "new_sources": 0,
        "new_admissions": 0,
        "new_federated_canaries": 0,
        "publications": 0,
        "rights_conclusion_changed": False,
        "native_member_names_or_values_emitted": False,
    }
    artifact = tmp_path / "group-0" / "historical-workbook-packages.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(receipt))
    return artifact, receipt


def test_complete_aggregate_identity_and_counts(tmp_path, monkeypatch):
    artifact, receipt = fixture_receipt(tmp_path, monkeypatch)
    result = module.reconcile(ROOT, tmp_path, 123, COMMIT)
    assert result["status"] == "passed"
    assert result["groups"] == 1
    assert result["totals"]["cells"] == 3
    assert result["source_column_semantics_qualified"] is False
    assert (
        result["receipt_sha256_by_group"]["0"]
        == hashlib.sha256(artifact.read_bytes()).hexdigest()
    )
    assert receipt["members"][0]["complete_native_restore_verified"] is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda report: report.update(status="incomplete"),
        lambda report: report["members"][0]["manifest"].update(
            output_id="0" * 64
        ),
        lambda report: report["members"][0].update(duckdb_cells=4),
        lambda report: report["members"][0]["manifest"]["boundaries"].update(
            admitted=True
        ),
        lambda report: report.update(new_admissions=1),
    ],
)
def test_reject_drift_and_promotion(tmp_path, monkeypatch, mutate):
    artifact, report = fixture_receipt(tmp_path, monkeypatch)
    mutate(report)
    artifact.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="differ"):
        module.reconcile(ROOT, tmp_path, 123, COMMIT)


def test_require_every_group(tmp_path):
    with pytest.raises(ValueError, match="denominator"):
        module.reconcile(ROOT, tmp_path, 123, COMMIT)


def test_reject_invalid_input_boundary(tmp_path):
    with pytest.raises(ValueError, match="commit"):
        module.reconcile(ROOT, tmp_path, 123, "short")
    with pytest.raises(ValueError, match="directory"):
        module.reconcile(ROOT, tmp_path / "missing", 123, COMMIT)


def test_reject_symlink_receipt(tmp_path, monkeypatch):
    artifact, _ = fixture_receipt(tmp_path, monkeypatch)
    target = tmp_path / "saved.json"
    artifact.replace(target)
    artifact.symlink_to(target)
    with pytest.raises(ValueError, match="file"):
        module.reconcile(ROOT, tmp_path, 123, COMMIT)


def test_cli_writes_once_and_preserves_existing(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    output = tmp_path / "result.json"
    monkeypatch.setattr(
        module,
        "reconcile",
        lambda _root, _artifacts, _run_id, _commit: {"status": "passed"},
    )
    args = [
        "--artifact-root",
        str(artifact_root),
        "--run-id",
        "123",
        "--workflow-commit",
        COMMIT,
        "--output",
        str(output),
    ]
    assert module.main(args) == 0
    assert json.loads(output.read_bytes()) == {"status": "passed"}
    with pytest.raises(SystemExit):
        module.main(args)
    assert json.loads(output.read_bytes()) == {"status": "passed"}


@pytest.mark.parametrize("change", ["state", "duplicate", "denominator"])
def test_format_profiles_reject_stale_or_incomplete_snapshot(tmp_path, change):
    destination = tmp_path / "quality" / "qualifications"
    destination.mkdir(parents=True)
    for index in range(6):
        name = (
            f"mbs-historical-native-formats-{index}-20261022-39709530322.json"
        )
        shutil.copyfile(
            ROOT / "quality" / "qualifications" / name, destination / name
        )
    first = (
        destination
        / "mbs-historical-native-formats-0-20261022-39709530322.json"
    )
    report = json.loads(first.read_bytes())
    if change == "state":
        report["status"] = "failed"
    else:
        workbook = next(
            row
            for row in report["result"]["members"]
            if row["declared_suffix_hint"] == ".xlsx"
        )
        if change == "duplicate":
            report["result"]["members"].append(workbook)
        else:
            report["result"]["members"].remove(workbook)
    first.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="historical"):
        module._format_profiles(tmp_path)
