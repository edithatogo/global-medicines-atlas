"""Tests for bounded operational exercise qualification."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import global_medicines_atlas.operational_exercises as exercises
from global_medicines_atlas.data_integrity import run_data_integrity_exercises
from global_medicines_atlas.operational_exercises import (
    SCALENE_RUN_URL,
    HostedArtifact,
    OperationalExerciseReceipt,
    ScaleneEvidence,
    inject_tampered_backup_fault,
    run_operational_exercises,
)

NOW = datetime(2026, 7, 31, 8, tzinfo=UTC)


def _workload(*, warm_samples: int = 25, passed: bool = True) -> dict[str, Any]:
    return {
        "passed": passed,
        "measurements": [
            {"scenario": "cold", "samples": 1},
            {"scenario": "warm", "samples": warm_samples},
            {"scenario": "concurrent", "samples": 4},
        ],
    }


def test_tampered_backup_is_rejected_before_publication() -> None:
    result = inject_tampered_backup_fault()

    assert result.passed
    assert result.canonical_destination_absent
    assert "payload digest does not match" in result.observed_error


def test_fault_exercise_fails_if_tampering_is_not_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def accept_tampered_backup(_bundle: Path, _destination: Path) -> None:
        return None

    monkeypatch.setattr(exercises, "restore_backup", accept_tampered_backup)

    with pytest.raises(
        AssertionError, match="Tampered backup unexpectedly restored"
    ):
        inject_tampered_backup_fault()


def test_exercises_emit_bounded_non_production_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_workload(
        _output: Path,
        *,
        budgets_path: Path,
        row_count: int,
        batch_size: int,
        readers: int,
        warm_runs: int,
    ) -> dict[str, Any]:
        del budgets_path, row_count, batch_size, readers
        return _workload(warm_samples=warm_runs)

    monkeypatch.setattr(
        "global_medicines_atlas.operational_exercises.run_workload",
        fake_workload,
    )
    output = tmp_path / "receipt.json"

    receipt = run_operational_exercises(
        output,
        budgets_path=Path("quality/budgets.json"),
        executed_at=NOW,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert receipt.passed
    assert not receipt.production_qualified
    assert payload["evidence_class"] == "synthetic_non_production"
    assert payload["scalene"]["profile"]["artifact_id"] == 8783359527
    assert all(
        result["passed"] for result in payload["threat_model"]["results"]
    )


@pytest.mark.parametrize(
    ("workload", "soak_iterations", "passed"),
    [
        (_workload(warm_samples=24), 25, True),
        (_workload(passed=False), 25, True),
        (_workload(), 25, False),
    ],
)
def test_receipt_rejects_inconsistent_pass_or_soak_evidence(
    workload: dict[str, Any],
    soak_iterations: int,
    *,
    passed: bool,
) -> None:
    with pytest.raises(ValidationError):
        OperationalExerciseReceipt(
            executed_at=NOW,
            threat_model=run_data_integrity_exercises(executed_at=NOW),
            workload=workload,
            soak_iterations=soak_iterations,
            fault_injection=inject_tampered_backup_fault(),
            scalene=ScaleneEvidence(
                run_url=SCALENE_RUN_URL,
                profile=HostedArtifact(
                    artifact_id=1,
                    name="profile",
                    sha256=f"sha256:{'0' * 64}",
                    size_bytes=1,
                ),
                quality_receipt=HostedArtifact(
                    artifact_id=2,
                    name="receipt",
                    sha256=f"sha256:{'1' * 64}",
                    size_bytes=1,
                ),
            ),
            passed=passed,
        )
