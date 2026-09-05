"""Fail-closed schema evolution and REST observation contracts.

This module is intentionally a preview contract.  It records compatibility
decisions over synthetic or already admitted schemas; it does not fetch a
catalogue, mutate a table, or make a schema authoritative.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Self

from pydantic import Field, model_validator

from .models import FrozenModel

SchemaType = Literal["string", "integer", "number", "boolean", "date", "bytes"]
Compatibility = Literal["compatible", "breaking"]
RestMethod = Literal["GET", "HEAD"]
RestOutcome = Literal["passed", "rejected"]
_SUCCESS_MIN = 200
_SUCCESS_MAX = 300


class SchemaField(FrozenModel):
    """A source-faithful field declaration with an explicit nullability."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")
    field_type: SchemaType
    nullable: bool


class SchemaDescriptor(FrozenModel):
    """Canonical schema identity used for comparison, never for admission."""

    schema_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,127}$")
    major: int = Field(strict=True, ge=1, le=999)
    minor: int = Field(strict=True, ge=0, le=999)
    fields: tuple[SchemaField, ...] = Field(min_length=1, max_length=512)
    canonical_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def binds_canonical_schema(self) -> Self:
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("schema fields repeat")
        payload = self.model_dump(exclude={"canonical_sha256"}, mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        if hashlib.sha256(encoded).hexdigest() != self.canonical_sha256:
            raise ValueError("schema canonical identity differs")
        return self


class SchemaEvolutionDecision(FrozenModel):
    """Comparison of two exact schemas with explicit migration semantics."""

    schema_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,127}$")
    before: SchemaDescriptor
    after: SchemaDescriptor
    compatibility: Compatibility
    migration_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_.-]{0,127}$")
    migration_reviewed: bool = False
    authority_promoted: Literal[False] = False

    @model_validator(mode="after")
    def validates_transition(self) -> Self:
        if self.before.schema_id != self.schema_id or self.after.schema_id != self.schema_id:
            raise ValueError("schema transition identity differs")
        if self.after.major < self.before.major or (
            self.after.major == self.before.major and self.after.minor < self.before.minor
        ):
            raise ValueError("schema transition moves backwards")
        old = {field.name: field for field in self.before.fields}
        new = {field.name: field for field in self.after.fields}
        additive_nullable = all(
            field.nullable for name, field in new.items() if name not in old
        )
        unchanged = all(
            new[name].field_type == field.field_type
            and (field.nullable or not new[name].nullable)
            for name, field in old.items()
            if name in new
        )
        naturally_compatible = self.after.major == self.before.major and additive_nullable and unchanged
        if self.compatibility == "compatible" and not naturally_compatible:
            raise ValueError("compatible transition is not additive and nullable")
        if self.compatibility == "breaking" and (
            self.migration_id is None or not self.migration_reviewed or self.after.major == self.before.major
        ):
            raise ValueError("breaking transition requires reviewed major migration")
        if self.compatibility == "compatible" and (self.migration_id is not None or self.migration_reviewed):
            raise ValueError("compatible transition cannot claim a migration")
        return self


class RestObservation(FrozenModel):
    """Payload-free REST lifecycle observation pinned to an exact schema."""

    method: RestMethod
    path: str = Field(pattern=r"^/v[0-9]+/[a-z0-9][a-z0-9_.-]{0,127}/[a-z0-9][a-z0-9_.-]{0,127}$")
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status_code: int = Field(strict=True, ge=100, le=599)
    outcome: RestOutcome
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    payload_retained: Literal[False] = False
    request_count: int = Field(strict=True, ge=0, le=1)

    @model_validator(mode="after")
    def validates_payload_free_lifecycle(self) -> Self:
        success = _SUCCESS_MIN <= self.status_code < _SUCCESS_MAX
        if self.outcome == "passed" and (
            not success
            or self.request_count != 1
            or (self.method == "GET" and self.response_sha256 is None)
        ):
            raise ValueError("passed REST observation must be one successful request")
        if self.outcome == "rejected" and success:
            raise ValueError("rejected REST observation cannot be successful")
        if self.method == "HEAD" and self.response_sha256 is not None:
            raise ValueError("HEAD observation cannot retain a response digest")
        return self


class RestSchemaQualification(FrozenModel):
    """Bounded REST/schema envelope; no live service or catalogue is implied."""

    schema_id: Literal["global-medicines-atlas.frontier-schema-rest"]
    schema_version: Literal[1]
    transition: SchemaEvolutionDecision
    observations: tuple[RestObservation, ...] = Field(min_length=2, max_length=8)
    production_dependency_adopted: Literal[False]
    technology_promotion_claimed: Literal[False]

    @model_validator(mode="after")
    def requires_version_pinned_lifecycle(self) -> Self:
        paths = {item.path for item in self.observations}
        if len(paths) != len(self.observations):
            raise ValueError("REST observation paths repeat")
        if any(f"/v{self.transition.after.major}/" not in path for path in paths):
            raise ValueError("REST path is not pinned to target schema major")
        if any(item.schema_sha256 != self.transition.after.canonical_sha256 for item in self.observations):
            raise ValueError("REST schema identity differs")
        return self
