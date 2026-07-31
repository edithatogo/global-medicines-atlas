"""Bounded release-candidate operational exercise qualification."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from .data_integrity import DataIntegrityReceipt, run_data_integrity_exercises
from .models import FrozenModel
from .performance_workload import run_workload
from .recovery import RecoveryError, create_backup, restore_backup

SCALENE_RUN_URL = (
    "https://github.com/edithatogo/global-medicines-atlas/"
    "actions/runs/30605249629"
)


class HostedArtifact(FrozenModel):
    """Immutable identity of an independently hosted exercise artifact."""

    artifact_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)


class FaultInjectionResult(FrozenModel):
    """Result of corrupting a recovery payload before publication."""

    fault: Literal["tampered_backup_payload"] = "tampered_backup_payload"
    expected_error: Literal["RecoveryError"] = "RecoveryError"
    observed_error: str = Field(min_length=1)
    canonical_destination_absent: bool
    passed: bool


class ScaleneEvidence(FrozenModel):
    """Hosted profile identity without overstating profile interpretation."""

    run_url: str = Field(pattern=r"^https://github\.com/")
    profile: HostedArtifact
    quality_receipt: HostedArtifact
    workload: Literal["deterministic_network_free_smoke"] = (
        "deterministic_network_free_smoke"
    )
    regression_claim: Literal["artifact_present_not_hotspot_qualified"] = (
        "artifact_present_not_hotspot_qualified"
    )


class OperationalExerciseReceipt(FrozenModel):
    """Machine-readable evidence for the bounded Phase 3 exercises."""

    schema_id: Literal["global-medicines-atlas.operational-exercises"] = (
        "global-medicines-atlas.operational-exercises"
    )
    schema_version: Literal[1] = 1
    executed_at: AwareDatetime
    evidence_class: Literal["synthetic_non_production"] = (
        "synthetic_non_production"
    )
    threat_model: DataIntegrityReceipt
    workload: dict[str, Any]
    soak_iterations: int = Field(ge=20)
    fault_injection: FaultInjectionResult
    scalene: ScaleneEvidence
    production_qualified: Literal[False] = False
    passed: bool

    @model_validator(mode="after")
    def validate_disposition(self) -> OperationalExerciseReceipt:
        workload_passed = self.workload.get("passed") is True
        expected_samples = next(
            (
                measurement.get("samples")
                for measurement in self.workload.get("measurements", [])
                if measurement.get("scenario") == "warm"
            ),
            None,
        )
        if expected_samples != self.soak_iterations:
            raise ValueError("Warm workload samples must equal soak iterations")
        expected = workload_passed and self.fault_injection.passed
        if self.passed != expected:
            raise ValueError("Receipt pass state disagrees with exercises")
        return self


def inject_tampered_backup_fault() -> FaultInjectionResult:
    with tempfile.TemporaryDirectory(prefix="gma-fault-injection-") as root:
        workspace = Path(root)
        source = workspace / "source"
        bundle = workspace / "bundle"
        destination = workspace / "canonical"
        source.mkdir()
        (source / "snapshot.json").write_text(
            '{"status":"approved"}\n', encoding="utf-8"
        )
        create_backup(source, bundle)
        (bundle / "payload" / "snapshot.json").write_text(
            '{"status":"funded"}\n', encoding="utf-8"
        )
        try:
            restore_backup(bundle, destination)
        except RecoveryError as error:
            return FaultInjectionResult(
                observed_error=str(error),
                canonical_destination_absent=not destination.exists(),
                passed=not destination.exists(),
            )
    raise AssertionError("Tampered backup unexpectedly restored")


def run_operational_exercises(
    output: Path,
    *,
    budgets_path: Path,
    row_count: int = 100_000,
    batch_size: int = 25_000,
    readers: int = 4,
    soak_iterations: int = 25,
    executed_at: datetime | None = None,
) -> OperationalExerciseReceipt:
    """Run bounded synthetic threat, load, soak, and fault exercises."""

    executed = executed_at or datetime.now(UTC)
    workload = run_workload(
        output.parent / "workload",
        budgets_path=budgets_path,
        row_count=row_count,
        batch_size=batch_size,
        readers=readers,
        warm_runs=soak_iterations,
    )
    fault = inject_tampered_backup_fault()
    receipt = OperationalExerciseReceipt(
        executed_at=executed,
        threat_model=run_data_integrity_exercises(executed_at=executed),
        workload=workload,
        soak_iterations=soak_iterations,
        fault_injection=fault,
        scalene=ScaleneEvidence(
            run_url=SCALENE_RUN_URL,
            profile=HostedArtifact(
                artifact_id=8783359527,
                name="scalene-profile",
                sha256=(
                    "sha256:68e3f8237df822f30083c5010c613e663822b358"
                    "f746e5b2760d4788d902dca1"
                ),
                size_bytes=397_192,
            ),
            quality_receipt=HostedArtifact(
                artifact_id=8783359333,
                name="quality-receipt-profile",
                sha256=(
                    "sha256:4a1886c228d5450bf4cfa5959e1576bb9ae76644"
                    "d717e7408fd07d4b3c2c9c68"
                ),
                size_bytes=548,
            ),
        ),
        passed=workload.get("passed") is True and fault.passed,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            receipt.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt
