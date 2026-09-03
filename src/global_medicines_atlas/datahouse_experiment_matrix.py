"""Fail-closed contracts for optional datahouse experiments.

The experiment matrix is evidence about optional catalogue and table-format
capabilities. It cannot promote a dependency, become Bronze evidentiary truth,
or turn an unmet prerequisite into a successful experiment.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, AwareDatetime, Field, model_validator

from .models import FrozenModel


class ExperimentId(StrEnum):
    ICEBERG_REST = "iceberg_rest"
    ICEBERG_V3 = "iceberg_v3"
    DUCKLAKE = "ducklake"
    OBJECT_VERSIONING = "object_versioning"
    BATCH_ATTESTATION = "batch_attestation"
    DELTA_HUDI = "delta_hudi"


ALL_EXPERIMENTS = tuple(ExperimentId)


class ExperimentOutcome(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    DEGRADED = "degraded"
    FAILED = "failed"
    NOT_RUN_PREREQUISITE_UNMET = "not_run_prerequisite_unmet"


class SpecificationReference(FrozenModel):
    """An authoritative specification pinned by version or revision."""

    title: str = Field(min_length=1)
    url: AnyHttpUrl
    version: str | None = Field(default=None, min_length=1)
    revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")

    @model_validator(mode="after")
    def pinned(self) -> SpecificationReference:
        if self.version is None and self.revision is None:
            raise ValueError("specification requires a version or revision")
        return self


class ExperimentResult(FrozenModel):
    """One capability-specific result or explicit not-run receipt."""

    experiment_id: ExperimentId
    unmet_requirement: str | None = Field(default=None, min_length=1)
    hypothesis: str | None = Field(default=None, min_length=1)
    baseline: str | None = Field(default=None, min_length=1)
    thresholds: tuple[str, ...] = ()
    outcome: ExperimentOutcome
    prerequisites: tuple[str, ...] = Field(min_length=1)
    prerequisites_met: bool
    specifications: tuple[SpecificationReference, ...] = Field(min_length=1)
    feature_flags: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    limitations: tuple[str, ...] = Field(min_length=1)
    rollback_procedure: str = Field(min_length=1)
    rights_review: str | None = Field(default=None, min_length=1)
    disposition: Literal[
        "promote-candidate", "retain-preview", "defer", "reject"
    ] | None = None
    optional_for_core: Literal[True] = True
    production_deployment_claimed: Literal[False] = False
    technology_promotion_claimed: Literal[False] = False

    @model_validator(mode="after")
    def outcome_matches_evidence(self) -> ExperimentResult:
        not_run = self.outcome == ExperimentOutcome.NOT_RUN_PREREQUISITE_UNMET
        if not_run and self.prerequisites_met:
            raise ValueError("not-run outcome requires an unmet prerequisite")
        if not not_run and not self.prerequisites_met:
            raise ValueError(
                "executed outcome requires satisfied prerequisites"
            )
        if not not_run and not self.evidence:
            raise ValueError("executed outcome requires measured evidence")
        if self.disposition == "promote-candidate" and self.outcome not in {
            ExperimentOutcome.SUPPORTED,
            ExperimentOutcome.DEGRADED,
        }:
            raise ValueError(
                "only a successful outcome can be a promotion candidate"
            )
        return self


class ExperimentMatrix(FrozenModel):
    """Complete disposition of all approved datahouse experiments."""

    schema_id: Literal["global-medicines-atlas.datahouse-experiment-matrix"]
    schema_version: Literal[1]
    generated_at: AwareDatetime
    fixture_path: str = Field(
        pattern=r"^tests/fixtures/datahouse/[a-z0-9_.-]+$"
    )
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dependency_lock_path: Literal["uv.lock"]
    dependency_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    python_reference: Literal["3.14"]
    bronze_completion_blocking: Literal[False]
    payload_receipts_remain_authoritative: Literal[True]
    experiments: tuple[ExperimentResult, ...]

    @model_validator(mode="after")
    def complete_experiment_set(self) -> ExperimentMatrix:
        observed = tuple(item.experiment_id for item in self.experiments)
        if len(observed) != len(set(observed)) or set(observed) != set(
            ALL_EXPERIMENTS
        ):
            raise ValueError(
                "every approved experiment must occur exactly once"
            )
        return self


def matrix_bytes(matrix: ExperimentMatrix) -> bytes:
    """Serialize a validated matrix deterministically."""

    return json.dumps(
        matrix.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def matrix_digest(matrix: ExperimentMatrix) -> str:
    """Return a deterministic digest for a validated matrix."""

    return hashlib.sha256(matrix_bytes(matrix)).hexdigest()


def verify_matrix_inputs(matrix: ExperimentMatrix, root: Path) -> None:
    """Fail when the governed fixture or dependency lock has drifted."""

    expected = (
        (matrix.fixture_path, matrix.fixture_sha256),
        (matrix.dependency_lock_path, matrix.dependency_lock_sha256),
    )
    for relative_path, expected_digest in expected:
        path = root / relative_path
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected_digest:
            raise ValueError(f"digest mismatch for {relative_path}")
