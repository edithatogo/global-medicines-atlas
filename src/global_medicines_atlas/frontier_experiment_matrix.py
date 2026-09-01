"""Fail-closed prerequisites for optional federated frontier experiments."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from .models import FrozenModel


class WorkloadSize(StrEnum):
    TINY = "tiny"
    MEDIUM = "medium"
    LARGE = "large"


class FrontierDisposition(StrEnum):
    REUSED = "reused"
    DEFER = "defer"


_REQUIRED_PREREQUISITES: dict[str, frozenset[str]] = {
    "remote_query_streaming": frozenset({
        "exact_public_object",
        "anonymous_digest",
        "request_instrumentation",
    }),
    "xet_object_mechanics": frozenset({
        "two_exact_revisions",
        "anonymous_digest",
    }),
    "iceberg_catalogue": frozenset({
        "prior_matrix_verified",
        "changed_workload",
    }),
    "batch_attestation": frozenset({
        "prior_fixture_verified",
        "cross_dataset_revisions",
    }),
    "graph_semantic_projection": frozenset({
        "gold_fixture",
        "rights_controls",
        "negative_controls",
    }),
    "transactional_alternatives": frozenset({
        "prior_decision_verified",
        "high_update_workload",
    }),
}


class ImportedEvidence(FrozenModel):
    path: str = Field(
        pattern=r"^(quality/qualifications|tests/fixtures)/[a-z0-9_./-]+\.json$"
    )
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class WorkloadProfile(FrozenModel):
    size: WorkloadSize
    maximum_rows: int = Field(strict=True, gt=0, le=10_000_000)
    maximum_source_bytes: int = Field(strict=True, gt=0, le=2_147_483_648)
    maximum_requests: int = Field(strict=True, gt=0, le=10_000)
    maximum_memory_bytes: int = Field(strict=True, gt=0, le=4_294_967_296)


class PublicObjectPrerequisite(FrozenModel):
    dataset: str = Field(pattern=r"^edithatogo/[a-z0-9_.-]+$")
    revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    path: str | None = Field(default=None, min_length=1, max_length=1024)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    anonymously_verified: bool = False

    @model_validator(mode="after")
    def complete_identity_or_absent(self) -> Self:
        identity = (self.revision, self.path, self.sha256)
        if any(item is not None for item in identity) != all(
            item is not None for item in identity
        ):
            raise ValueError("public object identity must be complete")
        if self.anonymously_verified and not all(
            item is not None for item in identity
        ):
            raise ValueError("anonymous verification requires exact identity")
        return self


class FrontierExperiment(FrozenModel):
    experiment_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    hypothesis: str = Field(min_length=1)
    unmet_requirement: str = Field(min_length=1)
    baseline: str = Field(min_length=1)
    threshold: str = Field(min_length=1)
    rights_sensitivity_review: str = Field(min_length=1)
    profile: WorkloadSize
    prerequisite_evidence: dict[str, bool] = Field(min_length=1, max_length=16)
    public_object: PublicObjectPrerequisite | None = None
    reused_evidence: tuple[str, ...] = ()
    controls: tuple[str, ...] = Field(min_length=4)
    fallback: str = Field(min_length=1)
    rollback: str = Field(min_length=1)
    disposition: FrontierDisposition
    experiment_started: bool = False
    production_dependency_adopted: Literal[False] = False
    technology_promotion_claimed: Literal[False] = False

    @model_validator(mode="after")
    def prerequisites_control_execution(self) -> Self:
        required = _REQUIRED_PREREQUISITES.get(self.experiment_id)
        if required is None:
            raise ValueError("unknown frontier experiment family")
        if set(self.prerequisite_evidence) != set(required):
            raise ValueError("frontier prerequisite denominator differs")
        ready = all(self.prerequisite_evidence.values())
        if self.experiment_started and (
            not ready
            or self.public_object is None
            or not self.public_object.anonymously_verified
        ):
            raise ValueError(
                "experiment started without complete prerequisites"
            )
        if (
            self.disposition is FrontierDisposition.REUSED
            and not self.reused_evidence
        ):
            raise ValueError("reused experiment requires imported evidence")
        return self


class FrontierExperimentMatrix(FrozenModel):
    schema_id: Literal["global-medicines-atlas.frontier-experiment-matrix"]
    schema_version: Literal[1]
    imported_evidence: tuple[ImportedEvidence, ...] = Field(min_length=4)
    workloads: tuple[WorkloadProfile, ...] = Field(min_length=3, max_length=3)
    experiments: tuple[FrontierExperiment, ...] = Field(min_length=6)
    non_promotion: Literal[True]

    @model_validator(mode="after")
    def complete_matrix(self) -> Self:
        sizes = tuple(item.size for item in self.workloads)
        if set(sizes) != set(WorkloadSize) or len(sizes) != len(set(sizes)):
            raise ValueError("tiny, medium and large workloads required once")
        by_size = {item.size: item for item in self.workloads}
        ordered = [by_size[size] for size in WorkloadSize]
        dimensions = (
            "maximum_rows",
            "maximum_source_bytes",
            "maximum_requests",
            "maximum_memory_bytes",
        )
        if any(
            not all(
                getattr(left, dimension) < getattr(right, dimension)
                for left, right in pairwise(ordered)
            )
            for dimension in dimensions
        ):
            raise ValueError("workload bounds must increase by profile")
        ids = {item.experiment_id for item in self.experiments}
        if ids != set(_REQUIRED_PREREQUISITES):
            raise ValueError("frontier experiment family denominator differs")
        imported = {item.path for item in self.imported_evidence}
        for experiment in self.experiments:
            if not set(experiment.reused_evidence) <= imported:
                raise ValueError("experiment cites unimported evidence")
        return self


def verify_imported_evidence(
    matrix: FrontierExperimentMatrix, root: Path
) -> None:
    """Verify reused decisions and fixtures without executing an experiment."""
    checked = FrontierExperimentMatrix.model_validate(matrix.model_dump())
    for evidence in checked.imported_evidence:
        path = root / evidence.path
        if not path.is_file():
            raise FileNotFoundError(evidence.path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence.sha256:
            raise ValueError(
                f"imported evidence digest mismatch: {evidence.path}"
            )
