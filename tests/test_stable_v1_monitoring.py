"""Stable-v1 candidate evidence and monitoring-plan qualification."""

from __future__ import annotations

import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed Python executable
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import ValidationError

from global_medicines_atlas import stable_v1_monitoring as monitoring
from global_medicines_atlas.stable_v1_monitoring import (
    INPUT_PATHS,
    AuthorityGates,
    MonitoringDomain,
    ObservationState,
    PostReleaseEvidence,
    PostReleaseObservation,
    SourceChangeMonitoring,
    StableV1MonitoringReceipt,
    build_monitoring_receipt,
    verify_monitoring_receipt,
    write_monitoring_receipt,
)


def test_monitoring_input_digest_is_checkout_newline_portable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "policy.json"
    path.write_bytes(b'{"state": "candidate"}\r\n')

    assert (
        monitoring._file_digest(path)
        == monitoring.sha256(b'{"state": "candidate"}\n').hexdigest()
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/stable-v1-monitoring-receipt-v1.json"
RECEIPT_PATH = (
    ROOT / "quality/qualifications/stable-v1-evidence-monitoring.json"
)


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _payload() -> dict[str, Any]:
    return build_monitoring_receipt(ROOT).model_dump(mode="json")


def _copy_inputs(destination: Path) -> None:
    for _, _, relative in INPUT_PATHS:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)


def test_receipt_is_deterministic_canonical_and_schema_valid() -> None:
    first = build_monitoring_receipt(ROOT)
    second = build_monitoring_receipt(ROOT)
    assert first == second
    assert first.canonical_json() == second.canonical_json()
    assert first.canonical_json().endswith(b"\n")

    schema = _schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first.model_dump(mode="json"))
    verify_monitoring_receipt(first, ROOT)


def test_committed_receipt_is_current_and_canonical() -> None:
    observed = StableV1MonitoringReceipt.model_validate_json(
        RECEIPT_PATH.read_bytes()
    )
    assert observed.canonical_json() == RECEIPT_PATH.read_bytes()
    verify_monitoring_receipt(observed, ROOT)


def test_every_required_contract_domain_is_content_bound() -> None:
    receipt = build_monitoring_receipt(ROOT)
    contract_domains = {
        item.domain for item in receipt.inputs if item.role == "contract"
    }
    assert contract_domains == {
        MonitoringDomain.SOURCE_HEALTH,
        MonitoringDomain.PROVENANCE,
        MonitoringDomain.SOURCE_MATURITY,
        MonitoringDomain.SECURITY,
        MonitoringDomain.PERFORMANCE,
        MonitoringDomain.PUBLICATION,
    }
    for item in receipt.inputs:
        assert (ROOT / item.path).is_file()
        assert len(item.sha256) == 64


def test_candidate_and_post_release_evidence_cannot_be_conflated() -> None:
    receipt = build_monitoring_receipt(ROOT)
    assert receipt.mode == "candidate_plan"
    assert receipt.candidate_evidence_state == "contract_bindings_verified"
    assert receipt.post_release_evidence.state is ObservationState.NOT_OBSERVED
    assert receipt.post_release_evidence.observations == ()
    assert all(
        objective.candidate_evidence_only
        and objective.post_release_observation_count == 0
        for objective in receipt.service_objectives
    )

    observation = PostReleaseObservation(
        observation_id="future-observation",
        domain=MonitoringDomain.SOURCE_HEALTH,
        observed_at=datetime(2026, 8, 1, tzinfo=UTC),
        receipt_path="durable/source-health.json",
        receipt_sha256="a" * 64,
    )
    with pytest.raises(ValidationError, match="not_observed"):
        PostReleaseEvidence(
            state=ObservationState.NOT_OBSERVED,
            observations=(observation,),
        )
    with pytest.raises(ValidationError, match="requires durable"):
        PostReleaseEvidence(state=ObservationState.OBSERVED)


def test_authority_and_external_action_gates_remain_false() -> None:
    receipt = build_monitoring_receipt(ROOT)
    assert receipt.authority_gates == AuthorityGates()
    assert receipt.external_actions_performed is False
    assert receipt.release_eligible is False
    assert set(receipt.blockers) >= {
        "durable-post-release-observations-missing",
        "publication-approval-missing",
        "release-approval-missing",
        "signing-approval-missing",
    }
    with pytest.raises(ValidationError, match="candidate receipt"):
        AuthorityGates(durable_approval_evidence=("unverified",))


def test_schema_rejects_approval_and_observation_claims() -> None:
    validator = Draft202012Validator(_schema())
    approved = _payload()
    approved["authority_gates"]["release_approved"] = True
    with pytest.raises(SchemaValidationError):
        validator.validate(approved)

    observed = _payload()
    observed["post_release_evidence"] = {
        "state": "observed",
        "observations": [
            {
                "observation_id": "invented",
                "domain": "source_health",
                "observed_at": "2026-08-01T00:00:00Z",
                "receipt_path": "invented.json",
                "receipt_sha256": "a" * 64,
            }
        ],
    }
    with pytest.raises(SchemaValidationError):
        validator.validate(observed)


def test_slos_define_alert_and_approval_gated_rollback() -> None:
    receipt = build_monitoring_receipt(ROOT)
    assert len(receipt.service_objectives) == 6
    assert {item.domain for item in receipt.service_objectives} == {
        MonitoringDomain.SOURCE_HEALTH,
        MonitoringDomain.PROVENANCE,
        MonitoringDomain.SOURCE_MATURITY,
        MonitoringDomain.SECURITY,
        MonitoringDomain.PERFORMANCE,
        MonitoringDomain.PUBLICATION,
    }
    for objective in receipt.service_objectives:
        assert objective.alert.automatic_external_notification is False
        assert objective.rollback.automatic_execution is False
        assert objective.rollback.approval_required is True
        assert objective.minimum_observations > 0

    latency = next(
        item
        for item in receipt.service_objectives
        if item.domain is MonitoringDomain.PERFORMANCE
    )
    assert (latency.comparator, latency.threshold, latency.unit) == (
        "lte",
        250.0,
        "milliseconds",
    )


def test_source_change_monitor_is_deterministic_and_fail_closed() -> None:
    monitor = build_monitoring_receipt(ROOT).source_change_monitoring
    assert monitor.baseline == "last-successful-main-receipt"
    assert monitor.alert_after_consecutive_failures == 2
    assert "schema fingerprint" in monitor.signals
    assert "adapter output parity fingerprint" in monitor.signals
    assert monitor.schema_drift_action == "quarantine-and-requalify-adapter"
    assert monitor.maturity_regression_action == "withdraw-affected-claims"
    assert monitor.automatic_external_action is False

    with pytest.raises(ValidationError, match="signals must be unique"):
        SourceChangeMonitoring(signals=("schema fingerprint",) * 2)


def test_tampering_with_receipt_or_bound_input_fails_closed(
    tmp_path: Path,
) -> None:
    receipt = build_monitoring_receipt(ROOT)
    tampered = StableV1MonitoringReceipt.model_validate({
        **receipt.model_dump(mode="json"),
        "limitations": ["tampered limitation"],
    })
    with pytest.raises(ValueError, match="receipt digest mismatch"):
        verify_monitoring_receipt(tampered, ROOT)

    _copy_inputs(tmp_path)
    copied = build_monitoring_receipt(tmp_path)
    (tmp_path / "quality/budgets.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="input tree digest mismatch"):
        verify_monitoring_receipt(copied, tmp_path)


def test_missing_contract_domain_is_rejected() -> None:
    payload = _payload()
    payload["inputs"] = [
        item for item in payload["inputs"] if item["domain"] != "security"
    ]
    with pytest.raises(ValidationError, match="all six"):
        StableV1MonitoringReceipt.model_validate(payload)


def test_write_is_atomic_and_script_check_is_executable(tmp_path: Path) -> None:
    receipt = build_monitoring_receipt(ROOT)
    output = tmp_path / "receipt.json"
    write_monitoring_receipt(output, receipt)
    assert output.read_bytes() == receipt.canonical_json()
    assert not output.with_suffix(".json.tmp").exists()

    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [
            sys.executable,
            str(ROOT / "scripts/build_stable_v1_monitoring_receipt.py"),
            "--check",
            "--output",
            str(RECEIPT_PATH),
        ],
        cwd=ROOT,
        check=True,
    )
