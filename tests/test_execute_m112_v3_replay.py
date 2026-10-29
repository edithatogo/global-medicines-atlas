"""Hosted replay executor verifies bytes only and removes its temporary input."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import scripts.execute_m112_v3_replay as executor
import scripts.qualify_m112_v3_replay as qualification


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _small_plan(
    payload: bytes, *, target_path: str = qualification.TARGET_PATH
) -> dict[str, Any]:
    plan = qualification.qualify(target_path=target_path, allow_existing=True)
    snapshot = plan["snapshots"][0]
    step = plan["replay_plan"]["steps"][0]
    digest = hashlib.sha256(payload).hexdigest()
    snapshot["payload_sha256"] = digest
    snapshot["snapshot_id"] = hashlib.sha256(
        _canonical([
            snapshot["partition_id"],
            digest,
            snapshot["metadata_sha256"],
        ])
    ).hexdigest()
    snapshot["idempotency_key"] = hashlib.sha256(
        _canonical([snapshot["partition_id"], snapshot["snapshot_id"]])
    ).hexdigest()
    step["snapshot_id"] = snapshot["snapshot_id"]
    step["expected_payload_sha256"] = digest
    step["expected_byte_count"] = len(payload)
    replay_plan = plan["replay_plan"]
    plan_content = {
        key: replay_plan[key]
        for key in (
            "schema_version",
            "deterministic",
            "eligible_snapshot_count",
            "steps",
        )
    }
    replay_plan["plan_sha256"] = hashlib.sha256(
        _canonical(plan_content)
    ).hexdigest()
    return plan


def _fake_download(payload: bytes):
    def download(**kwargs: Any) -> str:
        assert kwargs["repo_id"] == executor.DATASET
        assert kwargs["repo_type"] == "dataset"
        assert kwargs["revision"] == executor.REVISION
        assert kwargs["filename"].startswith("raw/mbs/utilisation/")
        assert kwargs["token"] is False
        local_dir = Path(kwargs["local_dir"])
        path = local_dir / kwargs["filename"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return str(path)

    return download


def test_replay_receipt_contains_only_identity_and_proves_cleanup(
    tmp_path: Path,
) -> None:
    payload = b"synthetic bytes for digest-only executor test"
    plan = _small_plan(payload)
    work_dir = tmp_path / "work"
    output_path = tmp_path / "receipt.json"

    receipt = executor.execute(
        plan,
        work_dir=work_dir,
        output_path=output_path,
        workflow_commit="a" * 40,
        workflow_run_id="123",
        workflow_run_attempt="1",
        download=_fake_download(payload),
    )

    assert receipt["status"] == "passed"
    assert receipt["candidate_only"] is True
    assert receipt["scope"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert receipt["scope"]["byte_count"] == len(payload)
    assert receipt["replay"]["registration"]["payload_values_read"] is False
    assert receipt["verification"]["token_free"] is True
    assert receipt["verification"]["temporary_source_bytes_removed"] is True
    assert receipt["boundaries"]["v4_admission_performed"] is False
    assert receipt["boundaries"]["m112_consumer_canary_performed"] is False
    assert not work_dir.exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == receipt


def test_executor_replays_another_pinned_raw_mbs_object(
    tmp_path: Path,
) -> None:
    target_path = "raw/mbs/utilisation/group/mbs-group-2016-july.csv"
    payload = b"second object synthetic bytes for digest-only executor test"
    plan = _small_plan(payload, target_path=target_path)
    work_dir = tmp_path / "work"
    output_path = tmp_path / "receipt.json"

    receipt = executor.execute(
        plan,
        work_dir=work_dir,
        output_path=output_path,
        workflow_commit="a" * 40,
        workflow_run_id="124",
        workflow_run_attempt="1",
        download=_fake_download(payload),
    )

    assert receipt["scope"]["path"] == target_path
    assert receipt["scope"]["byte_count"] == len(payload)
    assert receipt["verification"]["temporary_source_bytes_removed"] is True
    assert not work_dir.exists()


def test_executor_replays_pinned_demographics_source(
    tmp_path: Path,
) -> None:
    target_path = (
        "raw/mbs/utilisation/demographics/mbs-demographics-2016-qtr-3-july.csv"
    )
    payload = b"demographics replay synthetic bytes"
    plan = _small_plan(payload, target_path=target_path)
    work_dir = tmp_path / "work"
    output_path = tmp_path / "receipt.json"

    receipt = executor.execute(
        plan,
        work_dir=work_dir,
        output_path=output_path,
        workflow_commit="a" * 40,
        workflow_run_id="126",
        workflow_run_attempt="1",
        download=_fake_download(payload),
    )

    assert receipt["scope"]["path"] == target_path
    assert receipt["replay"]["registration"]["source_id"] == (
        "au-data-gov-mbs-demographics"
    )
    assert receipt["verification"]["temporary_source_bytes_removed"] is True
    assert not work_dir.exists()


def test_executor_rejects_source_id_drift_between_contract_and_snapshot(
    tmp_path: Path,
) -> None:
    plan = _small_plan(b"synthetic bytes")
    plan["contracts"][0]["source_id"] = "au-data-gov-mbs-demographics"

    with pytest.raises(ValueError, match="not eligible for hosted replay"):
        executor.execute(
            plan,
            work_dir=tmp_path / "work",
            output_path=tmp_path / "receipt.json",
            workflow_commit="a" * 40,
            workflow_run_id="127",
            workflow_run_attempt="1",
            download=_fake_download(b"synthetic bytes"),
        )


def test_executor_rejects_non_mbs_or_unapproved_path_from_plan(
    tmp_path: Path,
) -> None:
    plan = _small_plan(b"test")
    plan["snapshots"][0]["partition_value"] = (
        f"{executor.DATASET}@{executor.REVISION}:raw/pbs/test.pdf"
    )

    with pytest.raises(ValueError, match="approved raw B2 path"):
        executor.execute(
            plan,
            work_dir=tmp_path / "work",
            output_path=tmp_path / "receipt.json",
            workflow_commit="a" * 40,
            workflow_run_id="125",
            workflow_run_attempt="1",
            download=_fake_download(b"test"),
        )


def test_replay_digest_mismatch_fails_closed_and_removes_temporary_bytes(
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "work"
    output_path = tmp_path / "receipt.json"

    with pytest.raises(ValueError, match="digest or byte count differs"):
        executor.execute(
            qualification.qualify(allow_existing=True),
            work_dir=work_dir,
            output_path=output_path,
            workflow_commit="a" * 40,
            workflow_run_id="123",
            workflow_run_attempt="1",
            download=_fake_download(b"different bytes"),
        )

    assert not work_dir.exists()
    assert not output_path.exists()
