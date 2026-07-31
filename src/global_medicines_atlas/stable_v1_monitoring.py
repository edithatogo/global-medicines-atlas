"""Deterministic candidate evidence and post-release monitoring contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Literal

import orjson
from pydantic import Field, model_validator

from .models import FrozenModel

SCHEMA_ID = "global-medicines-atlas.stable-v1-monitoring-receipt"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class MonitoringDomain(StrEnum):
    """Evidence domains carried into stable-v1 monitoring."""

    SOURCE_HEALTH = "source_health"
    PROVENANCE = "provenance"
    SOURCE_MATURITY = "source_maturity"
    SECURITY = "security"
    PERFORMANCE = "performance"
    PUBLICATION = "publication"
    MONITORING = "monitoring"


class InputRole(StrEnum):
    """Whether an input is an existing authority or this implementation."""

    CONTRACT = "contract"
    IMPLEMENTATION = "implementation"


class AlertSeverity(StrEnum):
    """Stable alert classifications."""

    WARNING = "warning"
    CRITICAL = "critical"


class ObservationState(StrEnum):
    """Whether durable post-release observations are present."""

    NOT_OBSERVED = "not_observed"
    OBSERVED = "observed"


class FileBinding(FrozenModel):
    """Content identity for one repository input."""

    domain: MonitoringDomain
    role: InputRole
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256_PATTERN)


class AlertPolicy(FrozenModel):
    """An alert trigger that never performs an external action itself."""

    severity: AlertSeverity
    trigger: str = Field(min_length=1)
    route: Literal["maintainer-review-queue"] = "maintainer-review-queue"
    automatic_external_notification: Literal[False] = False


class RollbackPolicy(FrozenModel):
    """A fail-closed rollback decision boundary."""

    trigger: str = Field(min_length=1)
    action: str = Field(min_length=1)
    automatic_execution: Literal[False] = False
    approval_required: Literal[True] = True


class ServiceObjective(FrozenModel):
    """One measurable post-release objective with candidate-only evidence."""

    objective_id: str = Field(pattern=r"^SLO-[0-9]{3}$")
    domain: MonitoringDomain
    indicator: str = Field(min_length=1)
    comparator: Literal["eq", "gte", "lte"]
    threshold: float = Field(ge=0)
    unit: str = Field(min_length=1)
    window: str = Field(min_length=1)
    minimum_observations: int = Field(ge=1)
    candidate_evidence_only: Literal[True] = True
    post_release_observation_count: int = Field(default=0, ge=0)
    alert: AlertPolicy
    rollback: RollbackPolicy


class SourceChangeMonitoring(FrozenModel):
    """Source-change signals and their fail-closed response contract."""

    cadence: Literal["daily-and-source-declared-cadence"] = (
        "daily-and-source-declared-cadence"
    )
    signals: tuple[str, ...] = Field(min_length=1)
    baseline: Literal["last-successful-main-receipt"] = (
        "last-successful-main-receipt"
    )
    alert_after_consecutive_failures: int = Field(default=2, ge=1)
    schema_drift_action: Literal["quarantine-and-requalify-adapter"] = (
        "quarantine-and-requalify-adapter"
    )
    maturity_regression_action: Literal["withdraw-affected-claims"] = (
        "withdraw-affected-claims"
    )
    automatic_external_action: Literal[False] = False

    @model_validator(mode="after")
    def signals_are_unique(self) -> SourceChangeMonitoring:
        if len(self.signals) != len(set(self.signals)):
            raise ValueError("source-change signals must be unique")
        return self


class PostReleaseObservation(FrozenModel):
    """Identity-only record for a future durable observation."""

    observation_id: str = Field(min_length=1)
    domain: MonitoringDomain
    observed_at: datetime
    receipt_path: str = Field(min_length=1)
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)


class PostReleaseEvidence(FrozenModel):
    """Post-release truth kept separate from candidate evidence."""

    state: ObservationState
    observations: tuple[PostReleaseObservation, ...] = ()

    @model_validator(mode="after")
    def state_matches_observations(self) -> PostReleaseEvidence:
        if self.state is ObservationState.NOT_OBSERVED and self.observations:
            raise ValueError("not_observed state cannot contain observations")
        if self.state is ObservationState.OBSERVED and not self.observations:
            raise ValueError("observed state requires durable observations")
        return self


class AuthorityGates(FrozenModel):
    """Human and external authority gates for this candidate receipt."""

    signing_approved: Literal[False] = False
    publication_approved: Literal[False] = False
    release_approved: Literal[False] = False
    durable_approval_evidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def no_evidence_without_approval(self) -> AuthorityGates:
        if self.durable_approval_evidence:
            raise ValueError(
                "candidate receipt cannot contain approval evidence"
            )
        return self


class StableV1MonitoringReceipt(FrozenModel):
    """Content-bound stable-v1 candidate and monitoring-plan receipt."""

    schema_id: Literal[
        "global-medicines-atlas.stable-v1-monitoring-receipt"
    ] = SCHEMA_ID
    schema_version: Literal[1] = 1
    receipt_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    input_tree_sha256: str = Field(pattern=SHA256_PATTERN)
    mode: Literal["candidate_plan"] = "candidate_plan"
    candidate_evidence_state: Literal["contract_bindings_verified"] = (
        "contract_bindings_verified"
    )
    inputs: tuple[FileBinding, ...] = Field(min_length=1)
    service_objectives: tuple[ServiceObjective, ...] = Field(min_length=1)
    source_change_monitoring: SourceChangeMonitoring
    post_release_evidence: PostReleaseEvidence
    authority_gates: AuthorityGates = AuthorityGates()
    external_actions_performed: Literal[False] = False
    release_eligible: Literal[False] = False
    blockers: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def receipt_is_fail_closed(self) -> StableV1MonitoringReceipt:
        paths = [item.path for item in self.inputs]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise ValueError("input paths must be unique and sorted")
        contract_domains = {
            item.domain
            for item in self.inputs
            if item.role is InputRole.CONTRACT
        }
        required_domains = set(MonitoringDomain) - {MonitoringDomain.MONITORING}
        if contract_domains != required_domains:
            raise ValueError("all six existing contract domains are required")
        objective_ids = [item.objective_id for item in self.service_objectives]
        if len(objective_ids) != len(set(objective_ids)):
            raise ValueError("service objective identifiers must be unique")
        if (
            self.post_release_evidence.state
            is not ObservationState.NOT_OBSERVED
        ):
            raise ValueError(
                "candidate receipt cannot claim post-release evidence"
            )
        required_blockers = {
            "durable-post-release-observations-missing",
            "publication-approval-missing",
            "release-approval-missing",
            "signing-approval-missing",
        }
        if not required_blockers.issubset(self.blockers):
            raise ValueError("candidate receipt is missing authority blockers")
        return self

    def canonical_json(self) -> bytes:
        """Return stable receipt bytes."""
        return orjson.dumps(
            self.model_dump(mode="json"),
            option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_SORT_KEYS,
        )


INPUT_PATHS: tuple[tuple[MonitoringDomain, InputRole, str], ...] = (
    (
        MonitoringDomain.SECURITY,
        InputRole.CONTRACT,
        ".github/workflows/security-context.yml",
    ),
    (
        MonitoringDomain.PERFORMANCE,
        InputRole.CONTRACT,
        "quality/budgets.json",
    ),
    (
        MonitoringDomain.PUBLICATION,
        InputRole.CONTRACT,
        "quality/qualifications/publication-identities.json",
    ),
    (
        MonitoringDomain.SOURCE_MATURITY,
        InputRole.CONTRACT,
        "quality/qualifications/stable-v1-source-maturity.json",
    ),
    (
        MonitoringDomain.SECURITY,
        InputRole.CONTRACT,
        "schemas/protected-evidence-receipt-v1.json",
    ),
    (
        MonitoringDomain.PUBLICATION,
        InputRole.CONTRACT,
        "schemas/publication-identity-registry-v1.json",
    ),
    (
        MonitoringDomain.PROVENANCE,
        InputRole.CONTRACT,
        "schemas/release-evidence-v1.json",
    ),
    (
        MonitoringDomain.SOURCE_MATURITY,
        InputRole.CONTRACT,
        "schemas/stable-v1-source-maturity-v1.json",
    ),
    (
        MonitoringDomain.MONITORING,
        InputRole.IMPLEMENTATION,
        "schemas/stable-v1-monitoring-receipt-v1.json",
    ),
    (
        MonitoringDomain.MONITORING,
        InputRole.IMPLEMENTATION,
        "scripts/build_stable_v1_monitoring_receipt.py",
    ),
    (
        MonitoringDomain.PROVENANCE,
        InputRole.CONTRACT,
        "src/global_medicines_atlas/models.py",
    ),
    (
        MonitoringDomain.PERFORMANCE,
        InputRole.CONTRACT,
        "src/global_medicines_atlas/performance_workload.py",
    ),
    (
        MonitoringDomain.SECURITY,
        InputRole.CONTRACT,
        "src/global_medicines_atlas/protected_evidence.py",
    ),
    (
        MonitoringDomain.PUBLICATION,
        InputRole.CONTRACT,
        "src/global_medicines_atlas/publication_contracts.py",
    ),
    (
        MonitoringDomain.SOURCE_HEALTH,
        InputRole.CONTRACT,
        "src/global_medicines_atlas/source_health.py",
    ),
    (
        MonitoringDomain.MONITORING,
        InputRole.IMPLEMENTATION,
        "src/global_medicines_atlas/stable_v1_monitoring.py",
    ),
)


def _file_digest(path: Path) -> str:
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _input_tree_digest(inputs: tuple[FileBinding, ...]) -> str:
    payload = "".join(f"{item.path}\0{item.sha256}\n" for item in inputs)
    return sha256(payload.encode()).hexdigest()


def _receipt_digest(receipt: StableV1MonitoringReceipt) -> str:
    payload = receipt.model_dump(mode="json", exclude={"receipt_id"})
    return sha256(
        orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()


def _objectives() -> tuple[ServiceObjective, ...]:
    return (
        ServiceObjective(
            objective_id="SLO-001",
            domain=MonitoringDomain.SOURCE_HEALTH,
            indicator="probeable source observations available and fresh",
            comparator="gte",
            threshold=95.0,
            unit="percent",
            window="rolling-7-days",
            minimum_observations=7,
            alert=AlertPolicy(
                severity=AlertSeverity.CRITICAL,
                trigger="two consecutive unavailable or stale observations",
            ),
            rollback=RollbackPolicy(
                trigger="unverified source bytes or schema drift",
                action="quarantine source and restore last verified snapshot",
            ),
        ),
        ServiceObjective(
            objective_id="SLO-002",
            domain=MonitoringDomain.PROVENANCE,
            indicator="published assertions with complete digest-bound provenance",
            comparator="eq",
            threshold=100.0,
            unit="percent",
            window="each-candidate-and-daily-post-release",
            minimum_observations=1,
            alert=AlertPolicy(
                severity=AlertSeverity.CRITICAL,
                trigger="any assertion lacks source identity or content digest",
            ),
            rollback=RollbackPolicy(
                trigger="provenance verification failure",
                action="withdraw affected claims and restore verified predecessor",
            ),
        ),
        ServiceObjective(
            objective_id="SLO-003",
            domain=MonitoringDomain.SOURCE_MATURITY,
            indicator="unreviewed source maturity regressions",
            comparator="eq",
            threshold=0.0,
            unit="count",
            window="each-source-change",
            minimum_observations=1,
            alert=AlertPolicy(
                severity=AlertSeverity.WARNING,
                trigger="maturity or documentation readiness decreases",
            ),
            rollback=RollbackPolicy(
                trigger="maturity regression invalidates a released claim",
                action="withdraw affected claim pending requalification",
            ),
        ),
        ServiceObjective(
            objective_id="SLO-004",
            domain=MonitoringDomain.SECURITY,
            indicator="required protected security checks successful",
            comparator="eq",
            threshold=100.0,
            unit="percent",
            window="each-change-and-weekly",
            minimum_observations=1,
            alert=AlertPolicy(
                severity=AlertSeverity.CRITICAL,
                trigger="required check missing, failing, pending, or mismatched",
            ),
            rollback=RollbackPolicy(
                trigger="artifact or source compromise is confirmed",
                action="quarantine, revoke, withdraw, replace, and notify after approval",
            ),
        ),
        ServiceObjective(
            objective_id="SLO-005",
            domain=MonitoringDomain.PERFORMANCE,
            indicator="read-only request p95 latency",
            comparator="lte",
            threshold=250.0,
            unit="milliseconds",
            window="rolling-24-hours",
            minimum_observations=100,
            alert=AlertPolicy(
                severity=AlertSeverity.WARNING,
                trigger="p95 exceeds budget for two consecutive windows",
            ),
            rollback=RollbackPolicy(
                trigger="performance regression breaches the release budget",
                action="restore last qualified implementation and investigate",
            ),
        ),
        ServiceObjective(
            objective_id="SLO-006",
            domain=MonitoringDomain.PUBLICATION,
            indicator="published objects with verified identity, licence, and checksum",
            comparator="eq",
            threshold=100.0,
            unit="percent",
            window="each-publication-and-daily",
            minimum_observations=1,
            alert=AlertPolicy(
                severity=AlertSeverity.CRITICAL,
                trigger="durable identifier, licence, or checksum cannot be verified",
            ),
            rollback=RollbackPolicy(
                trigger="published bytes or identity differ from approved receipt",
                action="withdraw publication and restore approved artifact after review",
            ),
        ),
    )


def build_monitoring_receipt(root: Path) -> StableV1MonitoringReceipt:
    """Build a deterministic candidate receipt without external actions."""
    inputs = tuple(
        sorted(
            (
                FileBinding(
                    domain=domain,
                    role=role,
                    path=path,
                    sha256=_file_digest(root / path),
                )
                for domain, role, path in INPUT_PATHS
            ),
            key=lambda item: item.path,
        )
    )
    provisional = StableV1MonitoringReceipt(
        receipt_id=f"sha256:{'0' * 64}",
        input_tree_sha256=_input_tree_digest(inputs),
        inputs=inputs,
        service_objectives=_objectives(),
        source_change_monitoring=SourceChangeMonitoring(
            signals=(
                "access endpoint and access mode",
                "adapter output parity fingerprint",
                "catalog readiness and licence state",
                "declared source cadence and freshness",
                "schema fingerprint",
                "source maturity and documentation readiness",
            )
        ),
        post_release_evidence=PostReleaseEvidence(
            state=ObservationState.NOT_OBSERVED
        ),
        blockers=(
            "durable-post-release-observations-missing",
            "publication-approval-missing",
            "release-approval-missing",
            "signing-approval-missing",
        ),
        limitations=(
            "Candidate contracts and local deterministic checks are not post-release observations.",
            "No production SLO, alert delivery, rollback, signing, publication, or release action was executed.",
            "Source coverage and currency remain bounded by measured source-specific evidence.",
        ),
    )
    return provisional.model_copy(
        update={"receipt_id": f"sha256:{_receipt_digest(provisional)}"}
    )


def verify_monitoring_receipt(
    receipt: StableV1MonitoringReceipt,
    root: Path,
) -> None:
    """Fail closed when a receipt or any bound repository input changed."""
    expected = build_monitoring_receipt(root)
    if receipt.input_tree_sha256 != expected.input_tree_sha256:
        raise ValueError("monitoring input tree digest mismatch")
    if receipt.inputs != expected.inputs:
        raise ValueError("monitoring input bindings mismatch")
    if receipt.receipt_id != f"sha256:{_receipt_digest(receipt)}":
        raise ValueError("monitoring receipt digest mismatch")
    if receipt != expected:
        raise ValueError("monitoring receipt differs from deterministic plan")


def write_monitoring_receipt(
    output: Path,
    receipt: StableV1MonitoringReceipt,
) -> None:
    """Atomically write canonical receipt bytes."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_bytes(receipt.canonical_json())
    temporary.replace(output)
