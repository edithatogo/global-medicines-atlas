"""Fail-closed medicine-data integrity qualification exercises."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from .models import AssertionKind, EvidenceStatus, FrozenModel

RECEIPT_SCHEMA_ID = "global-medicines-atlas.data-integrity-exercise"
RECEIPT_SCHEMA_VERSION = 1
SHA256_HEXDIGEST_LENGTH = 64


class IntegrityThreat(StrEnum):
    """Medicine-data integrity threats that must fail closed."""

    POISONED_DOWNLOAD = "poisoned_download"
    STALE_SNAPSHOT = "stale_snapshot"
    IDENTIFIER_COLLISION = "identifier_collision"
    FALSE_STATUS_INFERENCE = "false_status_inference"


class IntegrityDisposition(StrEnum):
    """Permitted outcome of an integrity check."""

    ACCEPT = "accept"
    QUARANTINE = "quarantine"
    BLOCK = "block"


class IdentifierClaim(FrozenModel):
    """A source-scoped identifier that cannot imply global identity."""

    jurisdiction: str = Field(min_length=2, max_length=3)
    source_id: str = Field(min_length=1)
    system: str = Field(min_length=1)
    value: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)

    @property
    def scoped_key(self) -> tuple[str, str, str, str]:
        return (self.jurisdiction, self.source_id, self.system, self.value)


class IntegrityExerciseResult(FrozenModel):
    """Evidence for one deterministic threat exercise."""

    threat: IntegrityThreat
    disposition: IntegrityDisposition
    control: str = Field(min_length=1)
    observed: str = Field(min_length=1)
    passed: bool

    @model_validator(mode="after")
    def unsafe_acceptance_cannot_pass(self) -> IntegrityExerciseResult:
        if self.passed and self.disposition is IntegrityDisposition.ACCEPT:
            raise ValueError("Threat exercises must prove a blocking control")
        return self


class DataIntegrityReceipt(FrozenModel):
    """Machine-readable result of the medicine-data threat exercise."""

    schema_id: Literal["global-medicines-atlas.data-integrity-exercise"] = (
        RECEIPT_SCHEMA_ID
    )
    schema_version: Literal[1] = RECEIPT_SCHEMA_VERSION
    executed_at: AwareDatetime
    results: tuple[IntegrityExerciseResult, ...] = Field(min_length=4)

    @model_validator(mode="after")
    def every_required_threat_is_proven(self) -> DataIntegrityReceipt:
        observed = {result.threat for result in self.results}
        required = set(IntegrityThreat)
        if observed != required:
            raise ValueError("Receipt must contain every integrity threat once")
        if len(self.results) != len(required):
            raise ValueError("Receipt contains duplicate integrity threats")
        if not all(result.passed for result in self.results):
            raise ValueError("Every integrity threat exercise must pass")
        return self


def qualify_payload(
    payload: bytes, expected_sha256: str
) -> IntegrityDisposition:
    """Quarantine content whose digest differs from trusted metadata."""

    if len(expected_sha256) != SHA256_HEXDIGEST_LENGTH:
        raise ValueError("Expected SHA256 must contain 64 hexadecimal digits")
    try:
        bytes.fromhex(expected_sha256)
    except ValueError as error:
        raise ValueError(
            "Expected SHA256 must contain 64 hexadecimal digits"
        ) from error
    actual = sha256(payload).hexdigest()
    if actual != expected_sha256.lower():
        return IntegrityDisposition.QUARANTINE
    return IntegrityDisposition.ACCEPT


def qualify_snapshot_freshness(
    *,
    retrieved_at: datetime,
    current_at: datetime,
    maximum_age: timedelta,
) -> IntegrityDisposition:
    """Block current-state promotion for stale or future-dated snapshots."""

    if retrieved_at.tzinfo is None or current_at.tzinfo is None:
        raise ValueError("Snapshot timestamps must be timezone-aware")
    if maximum_age <= timedelta(0):
        raise ValueError("maximum_age must be positive")
    age = current_at - retrieved_at
    if age < timedelta(0) or age > maximum_age:
        return IntegrityDisposition.BLOCK
    return IntegrityDisposition.ACCEPT


def colliding_identifier_claims(
    claims: Iterable[IdentifierClaim],
) -> tuple[IdentifierClaim, ...]:
    """Return claims whose unscoped identifier maps to multiple concepts."""

    grouped: dict[tuple[str, str], list[IdentifierClaim]] = {}
    scoped_keys: set[tuple[str, str, str, str]] = set()
    for claim in claims:
        if claim.scoped_key in scoped_keys:
            raise ValueError("Duplicate source-scoped identifier claim")
        scoped_keys.add(claim.scoped_key)
        grouped.setdefault((claim.system, claim.value), []).append(claim)
    collisions = [
        claim
        for group in grouped.values()
        if len({claim.concept_id for claim in group}) > 1
        for claim in group
    ]
    return tuple(
        sorted(
            collisions,
            key=lambda claim: (*claim.scoped_key, claim.concept_id),
        )
    )


def qualify_status_claim(
    *,
    source_dimension: AssertionKind,
    asserted_dimension: AssertionKind,
    evidence_status: EvidenceStatus,
) -> IntegrityDisposition:
    """Block cross-dimension or inferred medicine-status promotion."""

    if source_dimension is not asserted_dimension:
        return IntegrityDisposition.BLOCK
    if evidence_status is not EvidenceStatus.CONFIRMED:
        return IntegrityDisposition.BLOCK
    return IntegrityDisposition.ACCEPT


def run_data_integrity_exercises(
    *,
    executed_at: datetime | None = None,
) -> DataIntegrityReceipt:
    """Run deterministic adversarial exercises against all required controls."""

    now = executed_at or datetime.now(UTC)
    trusted = b'{"medicine":"example","status":"approved"}'
    poisoned = trusted.replace(b"approved", b"funded")
    expected_digest = sha256(trusted).hexdigest()
    payload_outcome = qualify_payload(poisoned, expected_digest)

    stale_outcome = qualify_snapshot_freshness(
        retrieved_at=now - timedelta(days=31),
        current_at=now,
        maximum_age=timedelta(days=30),
    )

    collision_claims = colliding_identifier_claims((
        IdentifierClaim(
            jurisdiction="NZ",
            source_id="nzulm",
            system="local-product-id",
            value="42",
            concept_id="nz:42",
        ),
        IdentifierClaim(
            jurisdiction="AU",
            source_id="artg",
            system="local-product-id",
            value="42",
            concept_id="au:42",
        ),
    ))
    collision_outcome = (
        IntegrityDisposition.BLOCK
        if collision_claims
        else IntegrityDisposition.ACCEPT
    )

    status_outcome = qualify_status_claim(
        source_dimension=AssertionKind.FUNDING,
        asserted_dimension=AssertionKind.REGULATORY,
        evidence_status=EvidenceStatus.INFERRED,
    )
    return DataIntegrityReceipt(
        executed_at=now,
        results=(
            IntegrityExerciseResult(
                threat=IntegrityThreat.POISONED_DOWNLOAD,
                disposition=payload_outcome,
                control="content-addressed payload qualification",
                observed="digest mismatch quarantined before parsing",
                passed=payload_outcome is IntegrityDisposition.QUARANTINE,
            ),
            IntegrityExerciseResult(
                threat=IntegrityThreat.STALE_SNAPSHOT,
                disposition=stale_outcome,
                control="bounded snapshot freshness",
                observed="31-day snapshot blocked by 30-day maximum age",
                passed=stale_outcome is IntegrityDisposition.BLOCK,
            ),
            IntegrityExerciseResult(
                threat=IntegrityThreat.IDENTIFIER_COLLISION,
                disposition=collision_outcome,
                control="jurisdiction and source-scoped identifiers",
                observed="same local identifier mapped to distinct concepts",
                passed=collision_outcome is IntegrityDisposition.BLOCK,
            ),
            IntegrityExerciseResult(
                threat=IntegrityThreat.FALSE_STATUS_INFERENCE,
                disposition=status_outcome,
                control="dimension and evidence-status qualification",
                observed="funding evidence could not imply regulatory approval",
                passed=status_outcome is IntegrityDisposition.BLOCK,
            ),
        ),
    )
