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
    assert result["silver_field_state_coverage"]["native_unresolved_cells"] == 3
    assert result["silver_field_state_coverage"]["interpreted_cells"] == 0
    assert (
        result["silver_field_state_coverage"]["unavailable_patient_rates"]
        is True
    )
    assert result["source_column_semantics_qualified"] is False
    assert (
        result["receipt_sha256_by_group"]["0"]
        == hashlib.sha256(artifact.read_bytes()).hexdigest()
    )
    assert receipt["members"][0]["complete_native_restore_verified"] is True
    assert result["receipt_origin_by_group"]["0"] == {
        "run_id": 123,
        "workflow_commit": COMMIT,
    }
    assert result["retry_groups"] == []
    output = result["candidate_outputs_by_group"]["0"]
    manifest = receipt["members"][0]["manifest"]
    assert output["output_id"] == manifest["output_id"]
    assert output["parquet_sha256"] == manifest["parquet"]["sha256"]
    assert output["parquet_bytes"] == manifest["parquet"]["bytes"]
    assert output["member_sha256"] == manifest["member_binding"]["sha256"]
    assert output["field_state"] == "native_unresolved"
    assert output["rights_qualified"] is False
    assert output["admitted"] is False
    assert output["published"] is False


def retry_fixture(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline"
    retry_root = tmp_path / "retry"
    baseline.mkdir()
    retry_root.mkdir()
    artifact, complete = fixture_receipt(baseline, monkeypatch)
    retry_artifact = retry_root / "group-0" / artifact.name
    retry_artifact.parent.mkdir()
    retried = dict(complete, workflow_commit="b" * 40)
    retry_artifact.write_text(json.dumps(retried))
    incomplete = {
        "status": "incomplete",
        "workflow_commit": COMMIT,
        "group": 0,
        "phase": "member-native-check",
        "completed_members": 0,
        "native_member_names_or_values_emitted": False,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
    }
    artifact.write_text(json.dumps(incomplete))
    return baseline, retry_root, artifact, retry_artifact


def test_exact_retry_reconciles_without_double_counting(tmp_path, monkeypatch):
    baseline, retry_root, incomplete, retried = retry_fixture(
        tmp_path, monkeypatch
    )
    result = module.reconcile(
        ROOT,
        baseline,
        123,
        COMMIT,
        retry_artifact_root=retry_root,
        retry_run_id=456,
        retry_commit="b" * 40,
        retry_groups=(0,),
    )
    assert result["groups"] == 1
    assert result["unique_member_identities"] == 1
    assert result["retry_groups"] == [0]
    assert result["receipt_origin_by_group"]["0"] == {
        "run_id": 456,
        "workflow_commit": "b" * 40,
    }
    assert (
        result["receipt_sha256_by_group"]["0"]
        == hashlib.sha256(retried.read_bytes()).hexdigest()
    )
    assert result["baseline_incomplete_receipt_sha256_by_group"]["0"] == (
        hashlib.sha256(incomplete.read_bytes()).hexdigest()
    )
    assert result["silver_field_state_coverage"]["native_unresolved_cells"] == 3


@pytest.mark.parametrize("change", ["baseline", "retry", "identity", "groups"])
def test_retry_rejects_incomplete_or_misaligned_inputs(
    tmp_path, monkeypatch, change
):
    baseline, retry_root, incomplete, retried = retry_fixture(
        tmp_path, monkeypatch
    )
    groups = (0,)
    if change == "baseline":
        report = json.loads(incomplete.read_text())
        report["phase"] = "not-started"
        incomplete.write_text(json.dumps(report))
    elif change == "retry":
        report = json.loads(retried.read_text())
        report["status"] = "incomplete"
        retried.write_text(json.dumps(report))
    elif change == "identity":
        report = json.loads(retried.read_text())
        report["workflow_commit"] = COMMIT
        retried.write_text(json.dumps(report))
    else:
        groups = (0, 0)
    with pytest.raises(ValueError, match=r"retry|identity"):
        module.reconcile(
            ROOT,
            baseline,
            123,
            COMMIT,
            retry_artifact_root=retry_root,
            retry_run_id=456,
            retry_commit="b" * 40,
            retry_groups=groups,
        )


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
        lambda report: report["members"][0]["manifest"]["parquet"].update(
            bytes=0
        ),
        lambda report: report["members"][0]["manifest"]["parquet"].update(
            sha256="invalid"
        ),
    ],
)
def test_reject_drift_and_promotion(tmp_path, monkeypatch, mutate):
    artifact, report = fixture_receipt(tmp_path, monkeypatch)
    mutate(report)
    artifact.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="differ"):
        module.reconcile(ROOT, tmp_path, 123, COMMIT)


@pytest.mark.parametrize("change", ["bytes", "digest"])
def test_reject_invalid_candidate_fingerprint_even_with_rehashed_output_id(
    tmp_path, monkeypatch, change
):
    artifact, report = fixture_receipt(tmp_path, monkeypatch)
    manifest = report["members"][0]["manifest"]
    if change == "bytes":
        manifest["parquet"]["bytes"] = 0
    else:
        manifest["parquet"]["sha256"] = "invalid"
    identity = {
        key: value for key, value in manifest.items() if key != "output_id"
    }
    manifest["output_id"] = hashlib.sha256(
        canonical_package_json(identity)
    ).hexdigest()
    artifact.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="package identity"):
        module.reconcile(ROOT, tmp_path, 123, COMMIT)


def test_require_every_group(tmp_path):
    with pytest.raises(ValueError, match="denominator"):
        module.reconcile(ROOT, tmp_path, 123, COMMIT)


def test_reject_invalid_input_boundary(tmp_path):
    with pytest.raises(ValueError, match="commit"):
        module.reconcile(ROOT, tmp_path, 123, "short")
    with pytest.raises(ValueError, match="directory"):
        module.reconcile(ROOT, tmp_path / "missing", 123, COMMIT)
    with pytest.raises(ValueError, match="run id"):
        module.reconcile(ROOT, tmp_path, 0, COMMIT)


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


def test_cli_binds_retry_run_and_groups(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline"
    retry_root = tmp_path / "retry"
    baseline.mkdir()
    retry_root.mkdir()
    output = tmp_path / "result.json"
    calls = []

    def capture(_root, _baseline, _run_id, _commit, **kwargs):
        calls.append(kwargs)
        return {"status": "passed"}

    monkeypatch.setattr(module, "reconcile", capture)
    assert (
        module.main([
            "--artifact-root",
            str(baseline),
            "--run-id",
            "123",
            "--workflow-commit",
            COMMIT,
            "--retry-artifact-root",
            str(retry_root),
            "--retry-run-id",
            "456",
            "--retry-workflow-commit",
            "b" * 40,
            "--retry-group",
            "0",
            "--output",
            str(output),
        ])
        == 0
    )
    assert calls == [
        {
            "retry_artifact_root": retry_root,
            "retry_run_id": 456,
            "retry_commit": "b" * 40,
            "retry_groups": (0,),
        }
    ]


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
