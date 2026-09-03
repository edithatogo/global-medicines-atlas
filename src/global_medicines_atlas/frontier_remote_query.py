"""Evidence contracts for optional remote-query and Xet experiments."""

from __future__ import annotations

import hashlib
import json
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
_MIN_RESUME_REQUESTS = 2


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
    maximum_cache_bytes: int = Field(strict=True, ge=0, le=4_294_967_296)


class RemoteQueryIdentity(FrozenModel):
    """Content-bound semantics for the exact workload under comparison."""

    query_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,127}$")
    predicate: str = Field(min_length=1, max_length=2048)
    projected_columns: tuple[str, ...] = Field(min_length=1, max_length=128)
    order_by: tuple[str, ...] = Field(min_length=1, max_length=128)
    limit: int = Field(strict=True, gt=0, le=10_000_000)
    canonical_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def binds_canonical_query(self) -> Self:
        if len(set(self.projected_columns)) != len(self.projected_columns):
            raise ValueError("remote query projected columns repeat")
        if len(set(self.order_by)) != len(self.order_by):
            raise ValueError("remote query ordering columns repeat")
        encoded = json.dumps(
            self.model_dump(exclude={"canonical_sha256"}, mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if hashlib.sha256(encoded).hexdigest() != self.canonical_sha256:
            raise ValueError("remote query canonical identity differs")
        return self


class RemoteQueryObservation(FrozenModel):
    """One engine/scenario observation without URLs or returned values."""

    engine: Engine
    scenario: Scenario
    outcome: Outcome
    query_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: Digest | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    request_count: int = Field(strict=True, ge=0)
    transferred_bytes: int = Field(strict=True, ge=0)
    peak_memory_bytes: int = Field(strict=True, ge=0)
    cache_bytes: int = Field(strict=True, ge=0)
    scanned_rows: int = Field(strict=True, ge=0)
    returned_rows: int = Field(strict=True, ge=0)
    interrupted_after_bytes: int | None = Field(default=None, strict=True, gt=0)
    resumed_from_byte: int | None = Field(default=None, strict=True, gt=0)
    latency_ns: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def scenario_semantics(self) -> Self:
        if self.scenario == "offline":
            request_or_result_present = (
                self.outcome != "offline_rejected"
                or self.request_count != 0
                or self.transferred_bytes != 0
                or self.result_sha256 is not None
            )
            rows_present = self.scanned_rows != 0 or self.returned_rows != 0
            if request_or_result_present or rows_present:
                raise ValueError("offline observation must perform no request")
        elif self.scenario == "interrupted_resume":
            if (
                self.outcome != "resumed"
                or self.result_sha256 is None
                or self.request_count < _MIN_RESUME_REQUESTS
                or self.interrupted_after_bytes is None
                or self.resumed_from_byte != self.interrupted_after_bytes
            ):
                raise ValueError("interrupted observation must resume exactly")
        elif self.outcome != "passed" or self.result_sha256 is None:
            raise ValueError("online observation must pass with a result")
        elif (
            self.interrupted_after_bytes is not None
            or self.resumed_from_byte is not None
        ):
            raise ValueError("non-interrupted observation has resume offsets")
        if self.returned_rows > self.scanned_rows:
            raise ValueError("remote query returned rows exceed scanned rows")
        return self


class RemoteQueryQualification(FrozenModel):
    """Complete bounded parity envelope for four optional query engines."""

    schema_id: Literal["global-medicines-atlas.frontier-remote-query"]
    schema_version: Literal[1]
    public_object: ExactPublicObject
    profile: RemoteQueryProfile
    query: RemoteQueryIdentity
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
        if self.query.limit > self.profile.maximum_rows:
            raise ValueError("remote query limit exceeds row bound")
        for item in self.observations:
            if item.query_sha256 != self.query.canonical_sha256:
                raise ValueError("remote query observation identity differs")
            if item.request_count > self.profile.maximum_requests:
                raise ValueError("remote query request bound exceeded")
            if item.transferred_bytes > self.profile.maximum_source_bytes:
                raise ValueError("remote query source-byte bound exceeded")
            if item.peak_memory_bytes > self.profile.maximum_memory_bytes:
                raise ValueError("remote query memory bound exceeded")
            if item.cache_bytes > self.profile.maximum_cache_bytes:
                raise ValueError("remote query cache bound exceeded")
            if (
                item.scanned_rows > self.profile.maximum_rows
                or item.returned_rows > self.profile.maximum_rows
            ):
                raise ValueError("remote query row bound exceeded")
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
