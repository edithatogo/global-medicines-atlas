"""Evidence contracts for optional remote-query and Xet experiments."""

from __future__ import annotations

from itertools import product
from typing import Literal, Self

from pydantic import Field, model_validator

from .models import FrozenModel

Digest = str
Engine = Literal["python_fallback", "duckdb", "polars", "arrow"]
Scenario = Literal[
    "cold", "warm", "concurrent", "interrupted_resume", "offline"
]
Outcome = Literal["passed", "resumed", "offline_rejected"]

_ENGINES = ("python_fallback", "duckdb", "polars", "arrow")
_SCENARIOS = (
    "cold",
    "warm",
    "concurrent",
    "interrupted_resume",
    "offline",
)
_XET_REVISION_COUNT = 2


class ExactPublicObject(FrozenModel):
    """An anonymously verified immutable public object."""

    dataset: str = Field(pattern=r"^edithatogo/[a-z0-9_.-]+$")
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(min_length=1, max_length=1024)
    sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(strict=True, gt=0, le=2_147_483_648)
    anonymously_verified: bool

    @model_validator(mode="after")
    def requires_anonymous_verification(self) -> Self:
        if not self.anonymously_verified:
            raise ValueError("exact object requires anonymous verification")
        return self


class RemoteQueryProfile(FrozenModel):
    """Resource ceilings fixed before an experiment runs."""

    maximum_rows: int = Field(strict=True, gt=0, le=10_000_000)
    maximum_source_bytes: int = Field(strict=True, gt=0, le=2_147_483_648)
    maximum_requests: int = Field(strict=True, gt=0, le=10_000)
    maximum_memory_bytes: int = Field(strict=True, gt=0, le=4_294_967_296)


class RemoteQueryObservation(FrozenModel):
    """One engine/scenario observation without URLs or returned values."""

    engine: Engine
    scenario: Scenario
    outcome: Outcome
    result_sha256: Digest | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    request_count: int = Field(strict=True, ge=0)
    transferred_bytes: int = Field(strict=True, ge=0)
    peak_memory_bytes: int = Field(strict=True, ge=0)
    cache_bytes: int = Field(strict=True, ge=0)
    latency_ns: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def scenario_semantics(self) -> Self:
        if self.scenario == "offline":
            if (
                self.outcome != "offline_rejected"
                or self.request_count != 0
                or self.transferred_bytes != 0
                or self.result_sha256 is not None
            ):
                raise ValueError("offline observation must perform no request")
        elif self.scenario == "interrupted_resume":
            if self.outcome != "resumed" or self.result_sha256 is None:
                raise ValueError("interrupted observation must resume exactly")
        elif self.outcome != "passed" or self.result_sha256 is None:
            raise ValueError("online observation must pass with a result")
        return self


class RemoteQueryQualification(FrozenModel):
    """Complete bounded parity envelope for four optional query engines."""

    schema_id: Literal["global-medicines-atlas.frontier-remote-query"]
    schema_version: Literal[1]
    public_object: ExactPublicObject
    profile: RemoteQueryProfile
    expected_result_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    observations: tuple[RemoteQueryObservation, ...]
    production_dependency_adopted: Literal[False]
    technology_promotion_claimed: Literal[False]

    @model_validator(mode="after")
    def complete_bounded_parity(self) -> Self:
        identities = {
            (item.engine, item.scenario) for item in self.observations
        }
        expected = set(product(_ENGINES, _SCENARIOS))
        if identities != expected or len(self.observations) != len(expected):
            raise ValueError("remote query engine/scenario denominator differs")
        for item in self.observations:
            if item.request_count > self.profile.maximum_requests:
                raise ValueError("remote query request bound exceeded")
            if item.transferred_bytes > self.profile.maximum_source_bytes:
                raise ValueError("remote query source-byte bound exceeded")
            if item.peak_memory_bytes > self.profile.maximum_memory_bytes:
                raise ValueError("remote query memory bound exceeded")
            if (
                item.scenario != "offline"
                and item.result_sha256 != self.expected_result_sha256
            ):
                raise ValueError("remote query result parity differs")
        return self


class XetRestoreObservation(ExactPublicObject):
    """Bounded restore metrics whose chunks never replace source identity."""

    restored_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    request_count: int = Field(strict=True, ge=0, le=10_000)
    transferred_bytes: int = Field(strict=True, ge=0, le=2_147_483_648)
    reused_chunk_count: int = Field(strict=True, ge=0)
    new_chunk_count: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def restored_object_is_exact(self) -> Self:
        if self.restored_sha256 != self.sha256:
            raise ValueError("restored digest differs from source identity")
        if self.reused_chunk_count + self.new_chunk_count == 0:
            raise ValueError("Xet chunk denominator is empty")
        return self


class XetRestoreQualification(FrozenModel):
    """Two-revision restore evidence with non-authoritative chunk metrics."""

    schema_id: Literal["global-medicines-atlas.frontier-xet-restore"]
    schema_version: Literal[1]
    objects: tuple[XetRestoreObservation, ...] = Field(
        min_length=2, max_length=2
    )
    source_identity_basis: Literal["per_object_sha256"]
    chunk_identity_is_evidence_truth: Literal[False]
    production_dependency_adopted: Literal[False]
    technology_promotion_claimed: Literal[False]

    @model_validator(mode="after")
    def requires_two_exact_revisions(self) -> Self:
        identities = {
            (item.dataset, item.revision, item.path, item.sha256)
            for item in self.objects
        }
        revisions = {(item.dataset, item.revision) for item in self.objects}
        if (
            len(identities) != _XET_REVISION_COUNT
            or len(revisions) != _XET_REVISION_COUNT
        ):
            raise ValueError("Xet qualification requires two exact revisions")
        return self
