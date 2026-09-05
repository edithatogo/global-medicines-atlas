"""Deterministic, fail-closed temporal release qualification evidence."""

from __future__ import annotations

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed git executable
from collections import Counter
from collections.abc import Iterable, Mapping
from enum import StrEnum
from hashlib import sha256
from operator import itemgetter
from pathlib import Path
from typing import Literal

import orjson
from pydantic import Field, model_validator

from .coverage import CoverageObservation
from .models import FrozenModel
from .receipts import (
    EvidenceClass,
    FailureReceipt,
    RightsState,
    SourceReceipt,
)
from .snapshots import SnapshotManifest, canonical_json_bytes

RELEASE_EVIDENCE_SCHEMA_ID = "global-medicines-atlas.release-evidence"
RELEASE_EVIDENCE_SCHEMA_VERSION = 1
REQUIREMENT_IDS = (
    "M-001",
    "M-002",
    "M-003",
    "M-004",
    "M-005",
    "M-030",
    "M-035",
    "M-071",
    "M-078",
)


class GateStatus(StrEnum):
    """Outcome supplied by an independently executable qualification gate."""

    PASSED = "passed"
    FAILED = "failed"
    UNVERIFIED = "unverified"


class ReleaseState(StrEnum):
    """Maximum qualification state supported by the supplied evidence."""

    FIXTURE_QUALIFIED = "fixture-qualified"
    LIVE_QUALIFIED = "live-qualified"
    BLOCKED = "blocked"
    APPROVED = "approved"


class GitState(FrozenModel):
    """Exact repository identity used to build the evidence."""

    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    dirty: bool


class RequirementEvidence(FrozenModel):
    """Trace one required MoSCoW identifier to named executable gates."""

    requirement_id: str
    gates: tuple[str, ...] = Field(min_length=1)
    satisfied: bool


class InputEvidenceDigests(FrozenModel):
    """Content identities for every qualification input collection."""

    receipts_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    coverage_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshots_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    gates_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReleaseEvidence(FrozenModel):
    """Canonical release decision with explicit unresolved gates."""

    schema_id: Literal["global-medicines-atlas.release-evidence"] = (
        RELEASE_EVIDENCE_SCHEMA_ID
    )
    schema_version: Literal[1] = RELEASE_EVIDENCE_SCHEMA_VERSION
    git: GitState
    requirement_map: tuple[RequirementEvidence, ...]
    dataset_schema_versions: tuple[str, ...]
    migration_versions: tuple[str, ...]
    input_evidence: InputEvidenceDigests
    receipt_digests: tuple[str, ...]
    snapshot_manifest_digests: tuple[str, ...]
    gate_outcomes: dict[str, GateStatus]
    receipt_counts: dict[EvidenceClass, int]
    coverage_unknown_denominators: int = Field(ge=0)
    rights_states: dict[RightsState, int]
    snapshot_scopes: tuple[str, ...]
    release_state: ReleaseState
    unresolved_gates: tuple[str, ...]

    @model_validator(mode="after")
    def qualification_is_fail_closed(  # ruff: ignore[too-many-branches]
        self,
    ) -> ReleaseEvidence:
        required_gates = {gate for gates in _REQUIREMENT_GATES.values() for gate in gates}
        missing_gates = required_gates.difference(self.gate_outcomes)
        if missing_gates:
            raise ValueError("gate outcomes are missing required gates")
        requirement_ids = tuple(item.requirement_id for item in self.requirement_map)
        if len(set(requirement_ids)) != len(requirement_ids):
            raise ValueError("requirement map must not contain duplicate identifiers")
        unknown = set(requirement_ids).difference(REQUIREMENT_IDS)
        if unknown:
            raise ValueError("requirement map contains unknown identifiers")
        missing = set(REQUIREMENT_IDS).difference(requirement_ids)
        if missing:
            raise ValueError("requirement map is missing required identifiers")
        if requirement_ids != REQUIREMENT_IDS:
            raise ValueError("requirement map must use canonical order")
        if self.dataset_schema_versions != tuple(sorted(set(self.dataset_schema_versions))):
            raise ValueError("dataset schema versions must be unique and sorted")
        if self.migration_versions != tuple(sorted(set(self.migration_versions))):
            raise ValueError("migration versions must be unique and sorted")
        if any(count < 0 for count in self.receipt_counts.values()) or any(
            count < 0 for count in self.rights_states.values()
        ):
            raise ValueError("evidence counts must be nonnegative")
        for item in self.requirement_map:
            expected_gates = _REQUIREMENT_GATES[item.requirement_id]
            if item.gates != expected_gates:
                raise ValueError("requirement map gates do not match contract")
        non_live = sum(
            count
            for evidence_class, count in self.receipt_counts.items()
            if evidence_class is not EvidenceClass.LIVE
        )
        if self.release_state in {
            ReleaseState.LIVE_QUALIFIED,
            ReleaseState.APPROVED,
        }:
            if non_live:
                raise ValueError(
                    "live-qualified evidence cannot contain non-live receipts"
                )
            if self.snapshot_scopes:
                raise ValueError(
                    "fixture snapshots cannot qualify a live release"
                )
            if (
                self.gate_outcomes.get("live_lineage_verification")
                is not GateStatus.PASSED
            ):
                raise ValueError(
                    "live-qualified requires verified live lineage"
                )
        if self.release_state is ReleaseState.APPROVED:
            raise ValueError(
                "ordinary release qualification cannot produce approved evidence"
            )
        unresolved = set(self.unresolved_gates)
        if len(unresolved) != len(self.unresolved_gates):
            raise ValueError("unresolved gates must be unique")
        if self.unresolved_gates != tuple(sorted(self.unresolved_gates)):
            raise ValueError("unresolved gates must be sorted")
        omitted = {
            gate
            for gate, status in self.gate_outcomes.items()
            if status is not GateStatus.PASSED and gate not in unresolved
        }
        if omitted:
            raise ValueError("unresolved gates omit non-passed outcomes")
        for item in self.requirement_map:
            expected_satisfied = all(
                self.gate_outcomes.get(gate) is GateStatus.PASSED
                for gate in item.gates
            )
            if item.satisfied != expected_satisfied:
                raise ValueError("requirement satisfaction does not match gates")
        return self

    def canonical_json(self) -> bytes:
        """Serialize to stable JSON suitable for content-addressed build output."""
        return orjson.dumps(
            self.model_dump(mode="json"),
            option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_SORT_KEYS,
        )


_REQUIREMENT_GATES: dict[str, tuple[str, ...]] = {
    "M-001": ("dimension_separation",),
    "M-002": ("jurisdiction_identity",),
    "M-003": ("bitemporal_model",),
    "M-004": ("source_provenance", "live_lineage_verification"),
    "M-005": ("rights_review",),
    "M-030": ("canonical_schema",),
    "M-035": ("coverage_denominators",),
    "M-071": ("deterministic_migration",),
    "M-078": ("traceability",),
}


def _canonical_digest(items: Iterable[object]) -> str:
    payload = orjson.dumps(
        list(items),
        option=orjson.OPT_SORT_KEYS,
    )
    return sha256(payload).hexdigest()


def _coverage_matches_receipt(
    observation: CoverageObservation,
    receipt: SourceReceipt,
) -> bool:
    receipt_id = getattr(observation, "receipt_id", None)
    if (
        receipt_id != receipt.receipt_id
        or observation.source_id != receipt.source.source_id
        or observation.jurisdiction != receipt.source.jurisdiction
        or not observation.assertion_type.startswith(
            f"{observation.dimension.value}:"
        )
    ):
        return False
    if receipt.effective_from is None:
        return False
    if observation.valid_time.start < receipt.effective_from:
        return False
    if receipt.effective_to is None:
        return True
    return (
        observation.valid_time.end is not None
        and observation.valid_time.end <= receipt.effective_to
    )


def inspect_git_state(repository: Path) -> GitState:
    """Inspect commit and dirty state without modifying the repository."""

    def run(*arguments: str) -> str:
        git_executable = shutil.which("git")
        if git_executable is None:
            raise RuntimeError(
                "git executable is required for release evidence"
            )
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [git_executable, "-C", str(repository.resolve()), *arguments],
            check=True,
            capture_output=True,
            shell=False,
            text=True,
        )
        return result.stdout.strip()

    return GitState(
        commit=run("rev-parse", "HEAD"),
        dirty=bool(run("status", "--porcelain=v1", "--untracked-files=all")),
    )


def qualify_release(  # ruff: ignore[too-many-branches, too-many-locals, too-many-statements]
    *,
    git: GitState,
    receipts: Iterable[SourceReceipt | FailureReceipt],
    coverage: Iterable[CoverageObservation],
    snapshots: Iterable[SnapshotManifest],
    gate_outcomes: Mapping[str, GateStatus],
    dataset_schema_versions: Iterable[str],
    migration_versions: Iterable[str],
    request_approval: bool = False,
    input_evidence: InputEvidenceDigests | None = None,
) -> ReleaseEvidence:
    """Evaluate supplied evidence without tagging, publishing, or inventing gates."""
    receipt_items = tuple(receipts)
    coverage_items = tuple(coverage)
    snapshot_items = tuple(snapshots)
    outcomes = dict(sorted(gate_outcomes.items()))
    schema_versions = tuple(sorted(set(dataset_schema_versions)))
    migrations = tuple(sorted(set(migration_versions)))

    required_gates = sorted({
        gate for gates in _REQUIREMENT_GATES.values() for gate in gates
    })
    unresolved = {
        gate
        for gate in required_gates
        if outcomes.get(gate, GateStatus.UNVERIFIED) is not GateStatus.PASSED
    }
    unresolved.update(
        gate
        for gate, status in outcomes.items()
        if status is not GateStatus.PASSED
    )

    receipt_counts = Counter(
        receipt.evidence_class for receipt in receipt_items
    )
    rights_counts = Counter(receipt.rights_state for receipt in receipt_items)
    unknown_denominators = sum(
        observation.eligible_denominator is None
        for observation in coverage_items
    )
    source_receipts = tuple(
        receipt
        for receipt in receipt_items
        if isinstance(receipt, SourceReceipt)
    )
    failure_count = sum(
        isinstance(receipt, FailureReceipt) for receipt in receipt_items
    )
    if not source_receipts:
        unresolved.add("source_receipts")
    if not schema_versions:
        unresolved.add("dataset_schema_versions")
    if not migrations:
        unresolved.add("migration_versions")
    if failure_count:
        unresolved.add("successful_retrievals")
    if unknown_denominators:
        unresolved.add("known_coverage_denominators")
    if any(state is RightsState.PROHIBITED for state in rights_counts):
        unresolved.add("rights_not_prohibited")
    qualifying_receipts = {
        receipt.receipt_id: receipt
        for receipt in source_receipts
        if receipt.satisfies_live_gate
    }
    unreconciled_coverage = [
        observation
        for observation in coverage_items
        if (
            (
                matched := qualifying_receipts.get(
                    getattr(observation, "receipt_id", "")
                )
            )
            is None
            or not _coverage_matches_receipt(observation, matched)
        )
    ]
    if unreconciled_coverage:
        unresolved.add("coverage_receipt_reconciliation")

    has_non_live = any(
        receipt.evidence_class is not EvidenceClass.LIVE
        for receipt in receipt_items
    )
    all_live = (
        bool(source_receipts)
        and not failure_count
        and all(receipt.satisfies_live_gate for receipt in source_receipts)
    )
    fixture_lineage = bool(snapshot_items) and all(
        snapshot.qualification_scope == "fixture_only_not_live_evidence"
        for snapshot in snapshot_items
    )

    live_blockers = set(unresolved)
    if has_non_live:
        live_blockers.add("live_evidence_only")
    if fixture_lineage:
        live_blockers.add("no_fixture_only_snapshots")
    if any(state is not RightsState.PERMITTED for state in rights_counts):
        live_blockers.add("rights_permitted")
    if git.dirty:
        live_blockers.add("clean_repository")
    if outcomes.get("live_lineage_verification") is not GateStatus.PASSED:
        live_blockers.add("live_lineage_verification")

    fixture_ready = (
        not (unresolved - {"coverage_receipt_reconciliation"})
        and bool(source_receipts)
        and has_non_live
        and fixture_lineage
    )
    live_ready = (
        all_live
        and bool(schema_versions)
        and bool(migrations)
        and not live_blockers
    )
    if request_approval and live_ready:
        state = ReleaseState.BLOCKED
        live_blockers.add("external_approval_receipt")
    elif live_ready:
        state = ReleaseState.LIVE_QUALIFIED
    elif fixture_ready:
        state = ReleaseState.FIXTURE_QUALIFIED
    else:
        state = ReleaseState.BLOCKED

    effective_unresolved = (
        live_blockers if (request_approval or all_live) else unresolved
    )
    requirement_map = tuple(
        RequirementEvidence(
            requirement_id=requirement,
            gates=gates,
            satisfied=all(
                outcomes.get(gate) is GateStatus.PASSED for gate in gates
            ),
        )
        for requirement, gates in _REQUIREMENT_GATES.items()
    )
    receipt_digests = tuple(
        sorted(receipt.digest() for receipt in receipt_items)
    )
    snapshot_digests = tuple(
        sorted(
            sha256(canonical_json_bytes(snapshot)).hexdigest()
            for snapshot in snapshot_items
        )
    )
    if input_evidence is None:
        input_evidence = InputEvidenceDigests(
            receipts_sha256=_canonical_digest(
                receipt.model_dump(mode="json", exclude_none=False)
                for receipt in sorted(
                    receipt_items,
                    key=lambda item: item.receipt_id,
                )
            ),
            coverage_sha256=_canonical_digest(
                observation.model_dump(mode="json", exclude_none=False)
                for observation in sorted(
                    coverage_items,
                    key=lambda item: (
                        item.receipt_id,
                        item.observation_id,
                    ),
                )
            ),
            snapshots_sha256=_canonical_digest(
                snapshot.model_dump(mode="json", exclude_none=False)
                for snapshot in sorted(
                    snapshot_items,
                    key=lambda item: (
                        item.dataset_schema_id,
                        item.dataset_schema_version,
                    ),
                )
            ),
            gates_sha256=_canonical_digest([
                {"gate": gate, "status": status.value}
                for gate, status in outcomes.items()
            ]),
        )
    return ReleaseEvidence(
        git=git,
        requirement_map=requirement_map,
        dataset_schema_versions=schema_versions,
        migration_versions=migrations,
        input_evidence=input_evidence,
        receipt_digests=receipt_digests,
        snapshot_manifest_digests=snapshot_digests,
        gate_outcomes=outcomes,
        receipt_counts=dict(sorted(receipt_counts.items(), key=itemgetter(0))),
        coverage_unknown_denominators=unknown_denominators,
        rights_states=dict(sorted(rights_counts.items(), key=itemgetter(0))),
        snapshot_scopes=tuple(
            sorted(snapshot.qualification_scope for snapshot in snapshot_items)
        ),
        release_state=state,
        unresolved_gates=tuple(sorted(effective_unresolved)),
    )
