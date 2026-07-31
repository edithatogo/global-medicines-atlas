"""Immutable Phase 3 mutation and performance baseline contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCORE_TOLERANCE = 0.000001


class FrozenModel(BaseModel):
    """Strict immutable baseline model."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class HostedEvidence(FrozenModel):
    """Identity of one GitHub-hosted observation."""

    repository: Literal["edithatogo/global-medicines-atlas"]
    run_id: int = Field(gt=0)
    head_sha: str = Field(min_length=7)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_id: int | None = Field(default=None, gt=0)


class MutationObservations(FrozenModel):
    """Authoritative aggregate Mutmut observations."""

    killed: int = Field(ge=0)
    survived: int = Field(ge=0)
    untested: int = Field(ge=0)
    skipped: int = Field(ge=0)
    suspicious: int = Field(ge=0)
    timeout: int = Field(ge=0)
    interrupted: int = Field(ge=0)
    segfault: int = Field(ge=0)
    total: int = Field(gt=0)
    score_percent: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def counts_and_score_agree(self) -> MutationObservations:
        classified = (
            self.killed
            + self.survived
            + self.untested
            + self.skipped
            + self.suspicious
            + self.timeout
            + self.interrupted
            + self.segfault
        )
        if classified != self.total:
            raise ValueError("mutation status counts must equal total")
        score_denominator = self.total - self.skipped
        calculated = self.killed / score_denominator * 100
        if abs(calculated - self.score_percent) > SCORE_TOLERANCE:
            raise ValueError("mutation score does not match counts")
        return self


class MutationBaseline(FrozenModel):
    """Mutation debt baseline and independent promotion target."""

    source: HostedEvidence
    observations: MutationObservations
    promotion_minimum_percent: float = Field(gt=0, le=100)
    promotion_status: Literal["blocked_survivor_debt", "qualified"]

    @model_validator(mode="after")
    def status_matches_target(self) -> MutationBaseline:
        qualified = (
            self.observations.score_percent >= self.promotion_minimum_percent
        )
        expected = "qualified" if qualified else "blocked_survivor_debt"
        if self.promotion_status != expected:
            raise ValueError("mutation promotion status contradicts score")
        return self


class PerformanceWorkload(FrozenModel):
    """Stable identity of the representative synthetic workload."""

    row_count: int = Field(gt=0)
    seed: int
    readers: int = Field(gt=0)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PerformanceObservations(FrozenModel):
    """Hosted reference observations used only for regression detection."""

    cold_p95_ms: float = Field(gt=0)
    warm_p95_ms: float = Field(gt=0)
    concurrent_p95_ms: float = Field(gt=0)
    concurrent_records_per_second: float = Field(gt=0)
    process_peak_memory_mib: float = Field(gt=0)


class PerformanceBaseline(FrozenModel):
    """Representative workload baseline."""

    source: HostedEvidence
    workload: PerformanceWorkload
    observations: PerformanceObservations
    maximum_regression_ratio: float = Field(ge=1)


class Phase3Baselines(FrozenModel):
    """Content-bound Phase 3 baseline document."""

    schema_version: Literal["1.0.0"]
    mutation: MutationBaseline
    performance: PerformanceBaseline


class SurvivorGroup(FrozenModel):
    """Deterministic module-level mutation survivor classification."""

    module: str = Field(min_length=1)
    count: int = Field(gt=0)
    disposition: Literal["open_test_gap"]
    priority: int = Field(gt=0)


class MutationSurvivorReview(FrozenModel):
    """Reviewed mutation survivor inventory without unsupported waivers."""

    schema_version: Literal["1.0.0"]
    reviewed_run_id: int = Field(gt=0)
    head_sha: str = Field(min_length=7)
    artifact_id: int = Field(gt=0)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    survived: int = Field(gt=0)
    promotion_survivor_maximum: int = Field(ge=0)
    promotion_status: Literal["blocked_survivor_debt"]
    groups: tuple[SurvivorGroup, ...] = Field(min_length=1)
    review_decision: str = Field(min_length=1)

    @model_validator(mode="after")
    def groups_reconcile_to_hosted_total(self) -> MutationSurvivorReview:
        if sum(group.count for group in self.groups) != self.survived:
            raise ValueError("survivor groups must reconcile to hosted total")
        priorities = [group.priority for group in self.groups]
        if priorities != list(range(1, len(self.groups) + 1)):
            raise ValueError("survivor priorities must be contiguous")
        if self.survived <= self.promotion_survivor_maximum:
            raise ValueError("blocked status requires survivor debt")
        return self


def load_phase3_baselines(path: Path) -> Phase3Baselines:
    """Load and strictly validate a committed baseline."""

    return Phase3Baselines.model_validate_json(path.read_text(encoding="utf-8"))


def load_survivor_review(path: Path) -> MutationSurvivorReview:
    """Load the hosted survivor review ledger."""

    return MutationSurvivorReview.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def mutation_regressed(
    baseline: MutationBaseline,
    current: MutationObservations,
) -> bool:
    """Return whether survivor debt or score worsened."""

    return (
        current.survived > baseline.observations.survived
        or current.score_percent < baseline.observations.score_percent
    )


def performance_regressions(
    baseline: PerformanceBaseline,
    current: dict[str, float],
) -> tuple[str, ...]:
    """Return metrics outside the allowed baseline-relative envelope."""

    reference = baseline.observations.model_dump()
    maximum_ratio = baseline.maximum_regression_ratio
    comparable_maximums = (
        "cold_p95_ms",
        "warm_p95_ms",
        "concurrent_p95_ms",
        "process_peak_memory_mib",
    )
    regressions = [
        metric
        for metric in comparable_maximums
        if metric in current
        if current[metric] > cast("float", reference[metric]) * maximum_ratio
    ]
    throughput = "concurrent_records_per_second"
    if current[throughput] < (
        cast("float", reference[throughput]) / maximum_ratio
    ):
        regressions.append(throughput)
    return tuple(regressions)


def load_performance_receipt(path: Path) -> dict[str, Any]:
    """Load a representative receipt for baseline comparison."""

    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("performance receipt must be an object")
    return cast("dict[str, Any]", payload)
