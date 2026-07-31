"""Exact, fail-closed qualification of hosted protected evidence."""

from __future__ import annotations

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed git executable
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Literal

import orjson
from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel

SHA40 = r"^[0-9a-f]{40}$"
SHA256 = r"^[0-9a-f]{64}$"
SCHEMA_ID = "global-medicines-atlas.protected-evidence-receipt"


class CheckCategory(StrEnum):
    """Protected evidence class."""

    CI = "ci"
    SECURITY = "security"


class EvidenceVerification(StrEnum):
    """Whether supplied identities prove the protected evidence."""

    VERIFIED = "verified"
    REJECTED = "rejected"


class PublicationState(StrEnum):
    """Observed durable publication state."""

    NOT_ATTEMPTED = "not_attempted"
    BLOCKED = "blocked"
    VERIFIED = "verified"


class ReleaseEligibility(StrEnum):
    """Maximum release conclusion supported by this receipt."""

    BLOCKED = "blocked"
    ELIGIBLE = "eligible"


class ProtectedTarget(FrozenModel):
    """Repository, commit, and pull request that evidence must identify."""

    repository: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")
    commit_sha: str = Field(pattern=SHA40)
    pull_request_number: int = Field(gt=0)


class RequiredCheck(FrozenModel):
    """One protected check and its expected producer identity."""

    name: str = Field(min_length=1)
    category: CheckCategory
    app_slug: str = Field(min_length=1)
    workflow_name: str | None = Field(default=None, min_length=1)


class ProtectedEvidencePolicy(FrozenModel):
    """Pinned target and complete required-check enumeration."""

    target: ProtectedTarget
    required_checks: tuple[RequiredCheck, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def checks_are_unique_and_cover_ci_and_security(
        self,
    ) -> ProtectedEvidencePolicy:
        identities = [
            (item.name, item.app_slug) for item in self.required_checks
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("required check identities must be unique")
        categories = {item.category for item in self.required_checks}
        if categories != {CheckCategory.CI, CheckCategory.SECURITY}:
            raise ValueError("required checks must enumerate CI and security")
        return self


class LocalTruth(FrozenModel):
    """Local Git observation, kept separate from hosted evidence."""

    commit_sha: str = Field(pattern=SHA40)
    dirty: bool


class PullRequestObservation(FrozenModel):
    """Hosted pull-request identity returned by GitHub."""

    number: int = Field(gt=0)
    head_sha: str = Field(pattern=SHA40)
    state: Literal["open", "closed"]
    url: AnyHttpUrl


class WorkflowRunObservation(FrozenModel):
    """Exact hosted workflow-run identity."""

    run_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    head_sha: str = Field(pattern=SHA40)
    status: str = Field(min_length=1)
    conclusion: str | None = None
    url: AnyHttpUrl


class CheckRunObservation(FrozenModel):
    """Exact hosted check-run identity."""

    check_run_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    head_sha: str = Field(pattern=SHA40)
    status: str = Field(min_length=1)
    conclusion: str | None = None
    app_slug: str = Field(min_length=1)
    workflow_run_id: int | None = Field(default=None, gt=0)
    details_url: AnyHttpUrl


class PublicationReceipt(FrozenModel):
    """Durable identity for one externally published intellectual object."""

    surface: str = Field(min_length=1)
    object_identity: str = Field(min_length=1)
    durable_url: AnyHttpUrl
    commit_sha: str = Field(pattern=SHA40)
    artifact_sha256: str = Field(pattern=SHA256)


class PublicationEvidence(FrozenModel):
    """Publication truth that cannot promote itself without a receipt."""

    state: PublicationState
    blockers: tuple[str, ...] = ()
    receipts: tuple[PublicationReceipt, ...] = ()

    @model_validator(mode="after")
    def durable_evidence_matches_state(self) -> PublicationEvidence:
        if self.state is PublicationState.VERIFIED and not self.receipts:
            raise ValueError("verified publication requires a durable receipt")
        if self.state is not PublicationState.VERIFIED and self.receipts:
            raise ValueError("unverified publication cannot carry receipts")
        if self.state is PublicationState.BLOCKED and not self.blockers:
            raise ValueError("blocked publication requires a blocker")
        if self.state is not PublicationState.BLOCKED and self.blockers:
            raise ValueError("publication blockers require blocked state")
        return self


class HostedEvidenceSnapshot(FrozenModel):
    """Normalized, offline-verifiable GitHub evidence snapshot."""

    repository: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")
    commit_sha: str = Field(pattern=SHA40)
    pull_request: PullRequestObservation
    workflow_runs: tuple[WorkflowRunObservation, ...]
    check_runs: tuple[CheckRunObservation, ...]
    publication: PublicationEvidence


class RequiredCheckVerification(FrozenModel):
    """Resolution of one required check to exact hosted identities."""

    name: str
    category: CheckCategory
    app_slug: str
    check_run_id: int | None = None
    workflow_run_id: int | None = None
    details_url: AnyHttpUrl | None = None
    verified: bool
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def verified_check_has_exact_identity(self) -> RequiredCheckVerification:
        if self.verified and (
            self.blockers
            or self.check_run_id is None
            or self.details_url is None
        ):
            raise ValueError("verified check requires exact identity")
        if not self.verified and not self.blockers:
            raise ValueError("rejected check requires a blocker")
        return self


class HostedIdentity(FrozenModel):
    """Hosted repository and pull-request identity bound into the receipt."""

    repository: str
    commit_sha: str = Field(pattern=SHA40)
    pull_request_number: int = Field(gt=0)
    pull_request_url: AnyHttpUrl


class ProtectedEvidenceReceipt(FrozenModel):
    """Deterministic result without inferred hosted or publication claims."""

    schema_id: Literal["global-medicines-atlas.protected-evidence-receipt"] = (
        SCHEMA_ID
    )
    schema_version: Literal[1] = 1
    receipt_id: str = Field(min_length=1)
    input_sha256: str = Field(pattern=SHA256)
    target: ProtectedTarget
    local_truth: LocalTruth
    hosted_identity: HostedIdentity
    required_checks: tuple[RequiredCheckVerification, ...]
    hosted_truth_verified: bool
    evidence_verification: EvidenceVerification
    publication: PublicationEvidence
    release_eligibility: ReleaseEligibility
    blockers: tuple[str, ...]
    release_blockers: tuple[str, ...]

    @model_validator(mode="after")
    def conclusions_match_evidence(self) -> ProtectedEvidenceReceipt:
        checks_verified = all(item.verified for item in self.required_checks)
        if self.evidence_verification is EvidenceVerification.VERIFIED and (
            self.blockers
            or not self.hosted_truth_verified
            or not checks_verified
        ):
            raise ValueError("verified evidence cannot contain rejected facts")
        if self.evidence_verification is EvidenceVerification.REJECTED and (
            not self.blockers
        ):
            raise ValueError("rejected evidence requires blockers")
        if self.release_eligibility is ReleaseEligibility.ELIGIBLE and (
            self.evidence_verification is not EvidenceVerification.VERIFIED
            or self.publication.state is not PublicationState.VERIFIED
            or self.release_blockers
        ):
            raise ValueError(
                "eligible release requires verified durable evidence"
            )
        if self.release_eligibility is ReleaseEligibility.BLOCKED and (
            not self.release_blockers
        ):
            raise ValueError("blocked release requires release blockers")
        return self

    def canonical_json(self) -> bytes:
        """Return stable receipt bytes."""
        return orjson.dumps(
            self.model_dump(mode="json"),
            option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_SORT_KEYS,
        )

    def digest(self) -> str:
        """Return the SHA-256 identity of canonical receipt bytes."""
        return sha256(self.canonical_json()).hexdigest()


def _input_digest(
    policy: ProtectedEvidencePolicy,
    local: LocalTruth,
    hosted: HostedEvidenceSnapshot,
) -> str:
    payload = {
        "hosted": hosted.model_dump(mode="json"),
        "local": local.model_dump(mode="json"),
        "policy": policy.model_dump(mode="json"),
    }
    return sha256(
        orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()


def _verify_workflow(
    *,
    requirement: RequiredCheck,
    observation: CheckRunObservation,
    hosted: HostedEvidenceSnapshot,
    target_sha: str,
) -> tuple[str, ...]:
    if observation.workflow_run_id is None:
        return (
            (f"hosted:check:{requirement.name}:workflow-missing",)
            if requirement.workflow_name is not None
            else ()
        )
    runs = tuple(
        run
        for run in hosted.workflow_runs
        if run.run_id == observation.workflow_run_id
    )
    prefix = f"hosted:check:{requirement.name}"
    if len(runs) != 1:
        return (f"{prefix}:workflow-identity-count:{len(runs)}",)
    run = runs[0]
    blockers: list[str] = []
    if requirement.workflow_name is not None and (
        run.name != requirement.workflow_name
    ):
        blockers.append(f"{prefix}:workflow-name-mismatch")
    if run.head_sha != target_sha:
        blockers.append(f"{prefix}:workflow-commit-mismatch")
    if run.status != "completed":
        blockers.append(f"{prefix}:workflow-status:{run.status}")
    if run.conclusion != "success":
        blockers.append(f"{prefix}:workflow-conclusion:{run.conclusion}")
    return tuple(blockers)


def _verify_required_check(
    requirement: RequiredCheck,
    hosted: HostedEvidenceSnapshot,
    target_sha: str,
) -> RequiredCheckVerification:
    matches = tuple(
        check
        for check in hosted.check_runs
        if check.name == requirement.name
        and check.app_slug == requirement.app_slug
    )
    prefix = f"hosted:check:{requirement.name}"
    if len(matches) != 1:
        kind = "missing" if not matches else "duplicate"
        return RequiredCheckVerification(
            name=requirement.name,
            category=requirement.category,
            app_slug=requirement.app_slug,
            verified=False,
            blockers=(f"{prefix}:{kind}",),
        )
    observation = matches[0]
    blockers: list[str] = []
    if observation.head_sha != target_sha:
        blockers.append(f"{prefix}:commit-mismatch")
    if observation.status != "completed":
        blockers.append(f"{prefix}:status:{observation.status}")
    if observation.conclusion != "success":
        blockers.append(f"{prefix}:conclusion:{observation.conclusion}")
    blockers.extend(
        _verify_workflow(
            requirement=requirement,
            observation=observation,
            hosted=hosted,
            target_sha=target_sha,
        )
    )
    return RequiredCheckVerification(
        name=requirement.name,
        category=requirement.category,
        app_slug=requirement.app_slug,
        check_run_id=observation.check_run_id,
        workflow_run_id=observation.workflow_run_id,
        details_url=observation.details_url,
        verified=not blockers,
        blockers=tuple(blockers),
    )


def verify_protected_evidence(
    *,
    policy: ProtectedEvidencePolicy,
    local: LocalTruth,
    hosted: HostedEvidenceSnapshot,
) -> ProtectedEvidenceReceipt:
    """Verify exact local and hosted identities without contacting a service."""
    target = policy.target
    blockers: list[str] = []
    if local.commit_sha != target.commit_sha:
        blockers.append("local:commit-mismatch")
    if local.dirty:
        blockers.append("local:dirty-worktree")
    if hosted.repository != target.repository:
        blockers.append("hosted:repository-mismatch")
    if hosted.commit_sha != target.commit_sha:
        blockers.append("hosted:snapshot-commit-mismatch")
    if hosted.pull_request.number != target.pull_request_number:
        blockers.append("hosted:pull-request-mismatch")
    if hosted.pull_request.head_sha != target.commit_sha:
        blockers.append("hosted:pr-head-mismatch")

    checks = tuple(
        _verify_required_check(item, hosted, target.commit_sha)
        for item in policy.required_checks
    )
    for check in checks:
        blockers.extend(check.blockers)
    blockers.extend(
        f"publication:receipt:{publication.surface}:commit-mismatch"
        for publication in hosted.publication.receipts
        if publication.commit_sha != target.commit_sha
    )

    unique_blockers = tuple(sorted(set(blockers)))
    hosted_blockers = tuple(
        item for item in unique_blockers if item.startswith("hosted:")
    )
    verification = (
        EvidenceVerification.REJECTED
        if unique_blockers
        else EvidenceVerification.VERIFIED
    )
    release_blockers = list(unique_blockers)
    if hosted.publication.state is not PublicationState.VERIFIED:
        release_blockers.append(f"publication:{hosted.publication.state.value}")
        release_blockers.extend(
            f"publication:{item}" for item in hosted.publication.blockers
        )
    unique_release_blockers = tuple(sorted(set(release_blockers)))
    release_eligibility = (
        ReleaseEligibility.ELIGIBLE
        if not unique_release_blockers
        else ReleaseEligibility.BLOCKED
    )
    digest = _input_digest(policy, local, hosted)
    return ProtectedEvidenceReceipt(
        receipt_id=f"protected-evidence-{target.commit_sha[:12]}-{digest[:12]}",
        input_sha256=digest,
        target=target,
        local_truth=local,
        hosted_identity=HostedIdentity(
            repository=hosted.repository,
            commit_sha=hosted.commit_sha,
            pull_request_number=hosted.pull_request.number,
            pull_request_url=hosted.pull_request.url,
        ),
        required_checks=checks,
        hosted_truth_verified=not hosted_blockers
        and all(item.verified for item in checks),
        evidence_verification=verification,
        publication=hosted.publication,
        release_eligibility=release_eligibility,
        blockers=unique_blockers,
        release_blockers=unique_release_blockers,
    )


def inspect_local_truth(repository: Path) -> LocalTruth:
    """Inspect local Git identity without treating it as hosted truth."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is required")

    def run(*arguments: str) -> str:
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [executable, "-C", str(repository.resolve()), *arguments],
            check=True,
            capture_output=True,
            shell=False,
            text=True,
        )
        return result.stdout.strip()

    return LocalTruth(
        commit_sha=run("rev-parse", "HEAD"),
        dirty=bool(run("status", "--porcelain=v1", "--untracked-files=all")),
    )


def write_protected_evidence_receipt(
    output: Path,
    receipt: ProtectedEvidenceReceipt,
) -> Path:
    """Atomically write canonical receipt bytes and their digest sidecar."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_bytes(receipt.canonical_json())
    temporary.replace(output)
    digest_path = output.with_suffix(f"{output.suffix}.sha256")
    digest_temporary = digest_path.with_suffix(f"{digest_path.suffix}.tmp")
    digest_temporary.write_text(f"{receipt.digest()}\n", encoding="ascii")
    digest_temporary.replace(digest_path)
    return digest_path
