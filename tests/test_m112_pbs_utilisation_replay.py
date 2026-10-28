"""Bound PBS replay plans to existing evidence before any anonymous read."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import scripts.execute_m112_v3_replay as executor
import scripts.m112_pbs_utilisation_replay as pbs
import scripts.qualify_m112_v3_replay as qualification


def _paths() -> list[str]:
    report = json.loads((pbs.ROOT / pbs.RIGHTS_LINEAGE).read_text())
    return [row["path"] for row in report["objects"]]


@pytest.mark.parametrize("target_path", _paths())
def test_each_exact_pbs_object_has_a_deterministic_metadata_plan(
    target_path: str,
) -> None:
    plan = qualification.qualify(target_path=target_path)
    assert plan == qualification.qualify(target_path=target_path)
    snapshot = plan["snapshots"][0]
    assert snapshot["partition_value"] == (
        f"{pbs.DATASET}@{pbs.REVISION}:{target_path}"
    )
    assert snapshot["source_id"] in pbs.SOURCE_IDS
    assert snapshot["rights_state"] == pbs.RIGHTS_STATE
    assert snapshot["archive_period"].startswith("filename-derived:")
    step = plan["replay_plan"]["steps"][0]
    assert step["candidate_only"] is True
    assert step["source_payload_values"] == "not_read"
    assert step["v4_admission_performed"] is False
    assert step["m112_consumer_canary_performed"] is False


@pytest.mark.parametrize(
    "target_path",
    [
        "raw/pbs/unknown.csv",
        "raw/pbs/../secret.csv",
        "raw/pbs/utilisation/reference/pbs-item-drug-map.csv/extra",
    ],
)
def test_pbs_plan_rejects_paths_outside_exact_six(target_path: str) -> None:
    with pytest.raises(ValueError, match="exact PBS replay target"):
        qualification.qualify(target_path=target_path)


@pytest.fixture
def evidence_root(tmp_path: Path) -> Path:
    lineage = json.loads((pbs.ROOT / pbs.LINEAGE).read_text())
    for relative in (*pbs.INPUT_DIGESTS, *lineage["output_bindings"]):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pbs.ROOT / relative, destination)
    return tmp_path


@pytest.mark.parametrize(
    "relative",
    [
        pbs.RIGHTS_LINEAGE,
        pbs.RIGHTS_ATTESTATION,
        pbs.FROZEN,
    ],
)
def test_pbs_plan_rejects_changed_approval_or_inventory_evidence(
    evidence_root: Path,
    relative: str,
) -> None:
    path = evidence_root / relative
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="evidence digest mismatch"):
        qualification.qualify(evidence_root, target_path=_paths()[0])


@pytest.mark.parametrize(
    "field",
    [
        "acquisition_event_path",
        "b2_manifest_path",
        "landed_admission_path",
    ],
)
def test_pbs_plan_rejects_changed_lifecycle_bytes(
    evidence_root: Path,
    field: str,
) -> None:
    lineage = json.loads((evidence_root / pbs.LINEAGE).read_text())
    path = evidence_root / lineage["objects"][0][field]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="lifecycle digest mismatch"):
        qualification.qualify(evidence_root, target_path=_paths()[0])


def test_pbs_executor_checks_pinned_scope_and_cleans_synthetic_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = qualification.qualify(target_path=_paths()[0])
    step = plan["replay_plan"]["steps"][0]
    expected_identity = (
        step["expected_payload_sha256"],
        step["expected_byte_count"],
    )

    def download(**kwargs: Any) -> str:
        assert kwargs["repo_id"] == pbs.DATASET
        assert kwargs["revision"] == pbs.REVISION
        assert kwargs["filename"] == _paths()[0]
        assert kwargs["token"] is False
        path = Path(kwargs["local_dir"]) / "synthetic-payload"
        path.write_bytes(b"synthetic digest-only I/O control")
        return str(path)

    def file_identity(_: Path) -> tuple[str, int]:
        return expected_identity

    # Simulate verified file I/O without reading or retaining any real source.
    monkeypatch.setattr(executor, "_file_identity", file_identity)
    receipt = executor.execute(
        plan,
        work_dir=tmp_path / "work",
        output_path=tmp_path / "receipt.json",
        workflow_commit="a" * 40,
        workflow_run_id="123",
        workflow_run_attempt="1",
        download=download,
    )
    assert receipt["scope"]["dataset"] == pbs.DATASET
    assert receipt["verification"]["temporary_source_bytes_removed"] is True
    assert receipt["boundaries"]["v4_admission_performed"] is False
    assert not (tmp_path / "work").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rights_state", "unknown"),
        ("source_id", "au-data-gov-mbs-group"),
        ("payload_sha256", "a" * 64),
        ("metadata_sha256", "b" * 64),
    ],
)
def test_pbs_executor_rejects_forged_plan_before_downloading(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    plan = copy.deepcopy(qualification.qualify(target_path=_paths()[0]))
    plan["snapshots"][0][field] = value

    def download(**_: Any) -> str:
        pytest.fail("forged PBS plan reached the download boundary")

    with pytest.raises(ValueError, match="bound PBS replay evidence"):
        executor.execute(
            plan,
            work_dir=tmp_path / "work",
            output_path=tmp_path / "receipt.json",
            workflow_commit="a" * 40,
            workflow_run_id="123",
            workflow_run_attempt="1",
            download=download,
        )
    assert not (tmp_path / "receipt.json").exists()


@pytest.mark.parametrize(
    "partition_value",
    [
        f"{pbs.DATASET}@{'f' * 40}:raw/pbs/unknown.csv",
        f"{pbs.DATASET}@{pbs.REVISION}:raw/pbs/unknown.csv",
    ],
)
def test_pbs_executor_rejects_unapproved_locator_before_downloading(
    tmp_path: Path,
    partition_value: str,
) -> None:
    plan = qualification.qualify(target_path=_paths()[0])
    plan["snapshots"][0]["partition_value"] = partition_value

    def download(**_: Any) -> str:
        pytest.fail("unapproved PBS locator reached the download boundary")

    with pytest.raises(ValueError, match="approved|exact PBS replay target"):
        executor.execute(
            plan,
            work_dir=tmp_path / "work",
            output_path=tmp_path / "receipt.json",
            workflow_commit="a" * 40,
            workflow_run_id="123",
            workflow_run_attempt="1",
            download=download,
        )
