"""Deterministic, fail-closed v0.6 product qualification evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenModel
from .product_contracts import (
    API_BASE_PATH,
    API_VERSION,
    MAX_EXPORT_ROWS,
    MAX_PAGE_SIZE,
    PRODUCT_EVIDENCE_VERSION,
)


class ProductReleaseState(StrEnum):
    BLOCKED = "blocked"
    FIXTURE_QUALIFIED = "fixture_qualified"
    RELEASE_QUALIFIED = "release_qualified"


class VerificationState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_VERIFIED = "not_verified"


class ReceiptResult(FrozenModel):
    passed: bool
    observed_ms: float | None = Field(default=None, ge=0)
    sample_size: int | None = Field(default=None, ge=1)
    detail: str = Field(min_length=1)


class QualificationReceipt(FrozenModel):
    """Machine-verifiable receipt produced by an executed workload or control."""

    schema_version: Literal["1"] = "1"
    receipt_id: str = Field(min_length=1)
    kind: Literal["performance", "threat"]
    subject_id: str = Field(min_length=1)
    executed_at: datetime
    product_version: str = PRODUCT_EVIDENCE_VERSION
    api_version: str = API_VERSION
    implementation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    result: ReceiptResult
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    def unsigned_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"payload_digest"})

    def calculated_digest(self) -> str:
        payload = json.dumps(
            self.unsigned_payload(), sort_keys=True, separators=(",", ":")
        ).encode()
        return sha256(payload).hexdigest()

    @model_validator(mode="after")
    def validate_integrity(self) -> QualificationReceipt:
        if self.executed_at.tzinfo is None:
            raise ValueError("Receipt timestamp must be timezone-aware")
        if self.product_version != PRODUCT_EVIDENCE_VERSION:
            raise ValueError("Receipt product version does not match")
        if self.api_version != API_VERSION:
            raise ValueError("Receipt API version does not match")
        if self.payload_digest != self.calculated_digest():
            raise ValueError("Receipt payload digest does not match")
        return self


def create_qualification_receipt(
    *,
    receipt_id: str,
    kind: Literal["performance", "threat"],
    subject_id: str,
    executed_at: datetime,
    implementation_digest: str,
    result: ReceiptResult,
) -> QualificationReceipt:
    """Create a self-digesting receipt only after a check has executed."""
    unsigned = QualificationReceipt.model_construct(
        schema_version="1",
        receipt_id=receipt_id,
        kind=kind,
        subject_id=subject_id,
        executed_at=executed_at,
        product_version=PRODUCT_EVIDENCE_VERSION,
        api_version=API_VERSION,
        implementation_digest=implementation_digest,
        result=result,
        payload_digest="0" * 64,
    )
    return QualificationReceipt.model_validate({
        **unsigned.model_dump(mode="json", exclude={"payload_digest"}),
        "payload_digest": unsigned.calculated_digest(),
    })


class PerformanceResult(FrozenModel):
    scenario_id: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    budget_ms: float = Field(gt=0)
    observed_ms: float | None = Field(default=None, ge=0)
    sample_size: int | None = Field(default=None, ge=1)
    verification: VerificationState = VerificationState.NOT_VERIFIED
    reason: str = Field(min_length=1)
    receipt_id: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.verification is VerificationState.PASSED
            and self.observed_ms is not None
            and self.observed_ms <= self.budget_ms
        )


class ThreatCase(FrozenModel):
    threat_id: str = Field(pattern=r"^THREAT-[0-9]{3}$")
    description: str = Field(min_length=1)
    control: str = Field(min_length=1)
    verification: VerificationState
    reason: str = Field(min_length=1)
    receipt_id: str | None = None


class DeploymentEvidence(FrozenModel):
    clean_start: VerificationState
    live_deployment: VerificationState
    accessibility_conformance: VerificationState
    production_data: VerificationState
    detail: str = Field(min_length=1)


REQUIRED_GATES = frozenset({
    "api_contract_verified",
    "bounded_queries_verified",
    "abuse_cases_verified",
    "performance_budgets_verified",
    "clean_start_verified",
    "live_deployment_verified",
    "accessibility_conformance_verified",
    "production_data_verified",
})
FIXTURE_GATES = frozenset({
    "api_contract_verified",
    "bounded_queries_verified",
    "abuse_cases_verified",
    "performance_budgets_verified",
})
REQUIRED_LIMITATIONS = frozenset({
    "Fixture-only evidence; no live source coverage is claimed.",
    "No production deployment has been verified.",
    "Accessibility conformance has not been established.",
})


class ProductReleaseEvidence(FrozenModel):
    version: str = PRODUCT_EVIDENCE_VERSION
    api_version: str = API_VERSION
    api_base_path: str = API_BASE_PATH
    max_page_size: int = MAX_PAGE_SIZE
    max_export_rows: int = MAX_EXPORT_ROWS
    state: ProductReleaseState
    performance: tuple[PerformanceResult, ...] = Field(min_length=1)
    threats: tuple[ThreatCase, ...] = Field(min_length=1)
    deployment: DeploymentEvidence
    limitations: tuple[str, ...] = Field(min_length=1)
    gates: dict[str, bool]
    unresolved_gates: tuple[str, ...]

    @model_validator(mode="after")
    def validate_qualification(self) -> ProductReleaseEvidence:
        if (
            self.version != PRODUCT_EVIDENCE_VERSION
            or self.api_version != API_VERSION
            or self.api_base_path != API_BASE_PATH
        ):
            raise ValueError("Product evidence must bind the frozen v0.6 API")
        if (
            self.max_page_size != MAX_PAGE_SIZE
            or self.max_export_rows != MAX_EXPORT_ROWS
        ):
            raise ValueError("Product evidence must bind contract limits")
        missing = sorted(REQUIRED_GATES - self.gates.keys())
        if missing:
            raise ValueError(f"Missing qualification gates: {missing}")
        if not REQUIRED_LIMITATIONS.issubset(self.limitations):
            raise ValueError("Fixture and unverified claims must be disclosed")
        expected = tuple(
            sorted(gate for gate in REQUIRED_GATES if not self.gates[gate])
        )
        if self.unresolved_gates != expected:
            raise ValueError("Unresolved gates do not match gate evidence")
        if self.state is not _state_for(self.gates):
            raise ValueError(
                f"Evidence state must be {_state_for(self.gates).value} for its gates"
            )
        if self.gates["performance_budgets_verified"] != all(
            result.passed for result in self.performance
        ):
            raise ValueError("Performance gate disagrees with measurements")
        if self.gates["abuse_cases_verified"] != all(
            case.verification is VerificationState.PASSED
            for case in self.threats
        ):
            raise ValueError("Abuse-case gate disagrees with threat evidence")
        deployment_gates = {
            "clean_start_verified": self.deployment.clean_start,
            "live_deployment_verified": self.deployment.live_deployment,
            "accessibility_conformance_verified": self.deployment.accessibility_conformance,
            "production_data_verified": self.deployment.production_data,
        }
        for gate, verification in deployment_gates.items():
            if self.gates[gate] != (verification is VerificationState.PASSED):
                raise ValueError(f"{gate} disagrees with deployment evidence")
        return self

    def canonical_json(self) -> bytes:
        return (
            json.dumps(
                self.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()

    def digest(self) -> str:
        return sha256(self.canonical_json()).hexdigest()


def validate_receipt(
    receipt: QualificationReceipt,
    *,
    kind: Literal["performance", "threat"],
    subject_id: str,
    implementation_digest: str,
    now: datetime,
    max_age: timedelta = timedelta(days=7),
) -> str | None:
    if now.tzinfo is None:
        raise ValueError("Qualification clock must be timezone-aware")
    if receipt.kind != kind or receipt.subject_id != subject_id:
        return "receipt subject does not match the required check"
    if receipt.implementation_digest != implementation_digest:
        return "receipt implementation digest does not match"
    age = now.astimezone(UTC) - receipt.executed_at.astimezone(UTC)
    if age < timedelta() or age > max_age:
        return "receipt is stale or dated in the future"
    return None


def _state_for(gates: dict[str, bool]) -> ProductReleaseState:
    if all(gates[gate] for gate in REQUIRED_GATES):
        return ProductReleaseState.RELEASE_QUALIFIED
    if all(gates[gate] for gate in FIXTURE_GATES):
        return ProductReleaseState.FIXTURE_QUALIFIED
    return ProductReleaseState.BLOCKED


def qualify_product_release(
    *,
    performance: tuple[PerformanceResult, ...],
    threats: tuple[ThreatCase, ...],
    deployment: DeploymentEvidence,
    limitations: tuple[str, ...],
    api_contract_verified: bool,
    bounded_queries_verified: bool,
) -> ProductReleaseEvidence:
    gates = {
        "api_contract_verified": api_contract_verified,
        "bounded_queries_verified": bounded_queries_verified,
        "abuse_cases_verified": all(
            case.verification is VerificationState.PASSED for case in threats
        ),
        "performance_budgets_verified": all(
            result.passed for result in performance
        ),
        "clean_start_verified": deployment.clean_start
        is VerificationState.PASSED,
        "live_deployment_verified": deployment.live_deployment
        is VerificationState.PASSED,
        "accessibility_conformance_verified": (
            deployment.accessibility_conformance is VerificationState.PASSED
        ),
        "production_data_verified": deployment.production_data
        is VerificationState.PASSED,
    }
    unresolved = tuple(
        sorted(gate for gate in REQUIRED_GATES if not gates[gate])
    )
    return ProductReleaseEvidence(
        state=_state_for(gates),
        performance=performance,
        threats=threats,
        deployment=deployment,
        limitations=limitations,
        gates=dict(sorted(gates.items())),
        unresolved_gates=unresolved,
    )
