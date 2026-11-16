"""Frozen schedule replay candidates preserve exact lineage and fail closed."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import scripts.execute_m112_v3_replay as executor
import scripts.qualify_m112_v3_replay as v3
import scripts.qualify_mbs_frozen_raw_replay as qualification


@pytest.fixture(scope="module")
def evidence() -> dict[str, dict[str, Any]]:
    return qualification.load()


def test_candidates_bind_frozen_identity_and_preserve_original_reference() -> (
    None
):
    crosswalk, conformance, plans = qualification.build()
    assert len(crosswalk["objects"]) == len(conformance["artifacts"]) == 3
    assert set(plans) == set(qualification.PATHS)
    assert all(
        row["status"] == "blocked" for row in conformance["promotion_decisions"]
    )
    for row in crosswalk["objects"]:
        provenance = row["provenance"]
        target = provenance["target"]
        source = provenance["historical_b1_b2"]
        snapshot = plans[target["path"]]["snapshots"][0]
        assert target["revision"] == qualification.REVISION
        assert qualification.REVISION not in source["original_b2_reference"]
        assert snapshot["partition_value"] == (
            f"{qualification.DATASET}@{qualification.REVISION}:{target['path']}"
        )
        assert snapshot["metadata_sha256"] == row["provenance_sha256"]
        assert (
            plans[target["path"]]["replay_plan"]["steps"][0][
                "hosted_replay_status"
            ]
            == "pending"
        )
    alias = next(
        row
        for row in crosswalk["objects"]
        if row["path"] == qualification.ALIAS
    )
    assert alias["provenance"]["alias_of_historical_b2_path"] is True
    assert crosswalk["boundaries"]["replay_executed"] is False
    assert crosswalk["boundaries"]["v4_admission_or_consumer_canary"] is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("revision", "frozen identity"),
        ("digest", "frozen identity"),
        ("old_reference", "historical MBS B1/B2"),
        ("alias_content", "frozen identity"),
        ("rights", "attestation"),
        ("sensitivity", "historical MBS B1/B2"),
    ],
)
def test_crosswalk_rejects_misbound_evidence(
    evidence: dict[str, dict[str, Any]], mutation: str, message: str
) -> None:
    altered = copy.deepcopy(evidence)
    if mutation == "revision":
        next(
            x
            for x in altered["digest"]["objects"]
            if x["path"] == qualification.JULY
        )["revision"] = "0" * 40
    elif mutation == "digest":
        next(
            x
            for x in altered["digest"]["objects"]
            if x["path"] == qualification.JULY
        )["sha256"] = "0" * 64
    elif mutation == "old_reference":
        altered["august_b2"]["rows"][0]["external_reference"] += "?changed=1"
    elif mutation == "alias_content":
        next(
            x
            for x in altered["digest"]["objects"]
            if x["path"] == qualification.ALIAS
        )["sha256"] = "0" * 64
    elif mutation == "rights":
        altered["july_rights"]["decision"]["public_release_rights_attested"] = (
            False
        )
    else:
        altered["july_receipt"]["sensitivity"]["data_sensitivity"] = "unknown"
    with pytest.raises(ValueError, match=message):
        qualification.reconcile(altered)


@pytest.mark.parametrize("path", qualification.PATHS)
def test_schedule_replay_uses_exact_plan_and_does_not_persist_payload(
    path: str, tmp_path: Path
) -> None:
    plan = v3.qualify(target_path=path)
    calls: list[tuple[str, str, str, str, int]] = []

    def verify(
        dataset: str, revision: str, target: str, digest: str, size: int
    ) -> tuple[str, int]:
        calls.append((dataset, revision, target, digest, size))
        return digest, size

    receipt = executor.execute(
        plan,
        work_dir=tmp_path / "payload",
        output_path=tmp_path / "receipt.json",
        workflow_commit="a" * 40,
        workflow_run_id="123",
        workflow_run_attempt="1",
        stream_verify=verify,
    )
    assert len(calls) == 1
    assert calls[0][:3] == (qualification.DATASET, qualification.REVISION, path)
    assert receipt["scope"]["path"] == path
    assert receipt["verification"]["payload_values_read"] is False
    assert receipt["verification"]["temporary_source_bytes_removed"] is True
    assert receipt["verification"]["payload_storage"] == "never_materialized"
    assert (
        receipt["verification"]["digest_method"] == "bounded_anonymous_stream"
    )
    assert receipt["boundaries"]["v4_admission_performed"] is False
    assert not (tmp_path / "payload").exists()


def test_schedule_replay_rejects_changed_plan_before_stream(
    tmp_path: Path,
) -> None:
    plan = v3.qualify(target_path=qualification.JULY)
    plan["snapshots"][0]["source_version_id"] = "unbound"

    def unexpected(*_args: Any) -> tuple[str, int]:
        raise AssertionError("unbound plan must not read bytes")

    with pytest.raises(ValueError, match="bound frozen MBS"):
        executor.execute(
            plan,
            work_dir=tmp_path / "payload",
            output_path=tmp_path / "receipt.json",
            workflow_commit="a" * 40,
            workflow_run_id="123",
            workflow_run_attempt="1",
            stream_verify=unexpected,
        )


def test_schedule_replay_rejects_stream_digest_mismatch(tmp_path: Path) -> None:
    plan = v3.qualify(target_path=qualification.JULY)

    def mismatch(*_args: Any) -> tuple[str, int]:
        return "0" * 64, 1

    with pytest.raises(ValueError, match="digest or byte count differs"):
        executor.execute(
            plan,
            work_dir=tmp_path / "payload",
            output_path=tmp_path / "receipt.json",
            workflow_commit="a" * 40,
            workflow_run_id="123",
            workflow_run_attempt="1",
            stream_verify=mismatch,
        )
    assert not (tmp_path / "receipt.json").exists()


def test_schedule_cli_rejects_mismatched_hosted_run_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(v3.qualify(target_path=qualification.JULY)))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "replay",
            "--plan",
            str(plan_path),
            "--work-dir",
            str(tmp_path / "payload"),
            "--output",
            str(tmp_path / "receipt.json"),
            "--workflow-commit",
            "a" * 40,
            "--workflow-run-id",
            "124",
            "--workflow-run-attempt",
            "1",
        ],
    )
    with pytest.raises(ValueError, match="run identity differs"):
        executor.main()
    assert not (tmp_path / "receipt.json").exists()
