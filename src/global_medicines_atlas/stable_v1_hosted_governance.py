"""Offline-verifiable qualification of hosted GitHub governance evidence."""

# ruff: file-ignore[too-many-branches, too-many-locals]

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from typing import Literal, cast

import orjson
from pydantic import Field, JsonValue, model_validator

from .models import FrozenModel

SCHEMA_ID = "global-medicines-atlas.stable-v1-hosted-governance"
SHA40 = r"^[0-9a-f]{40}$"
SHA256 = r"^[0-9a-f]{64}$"
HTTP_SUCCESS_MIN = 200
HTTP_SUCCESS_MAX = 300

REQUIRED_OBSERVATIONS = frozenset({
    "repository",
    "rulesets",
    "branch_protection",
    "actions_permissions",
    "code_scanning_default_setup",
    "private_vulnerability_reporting",
    "automated_security_fixes",
    "vulnerability_alerts",
    "dependabot_alerts",
    "code_scanning_alerts",
    "secret_scanning_alerts",
    "issue_hierarchy",
    "project",
})

REQUIRED_CHECKS = frozenset({
    "Context and repository policy",
    "Dependency audit and SBOM",
    "CodeQL",
    "Mojo nightly / smoke",
    "Python 3.14 / unit",
    "Python 3.14 / integration",
    "Python 3.14 / e2e",
    "Python 3.14 / smoke",
    "Python 3.14 / property",
    "Python 3.14 / edge",
    "Python 3.14 / routine",
    "Python 3.14 / strict",
    "Python 3.14 / package",
    "Python 3.14 / coverage",
    "Python 3.14 / mutation",
    "Python 3.14 / gremlins",
    "Python 3.14 / dependencies",
    "Python 3.14 / profile",
    "Dependency review",
    "Repository and history leak detection",
    "Python 3.14 / regeneration",
    "Python 3.14 / representative performance",
    "codecov/patch",
})

REQUIRED_PROJECT_FIELDS: dict[str, frozenset[str]] = {
    "Status": frozenset({"Todo", "In Progress", "Done"}),
    "Priority": frozenset({"Must", "Should", "Could", "Unknown"}),
    "Workstream": frozenset({
        "Sources & ingestion",
        "Regulatory evidence",
        "Funding & formularies",
        "Mappings & terminology",
        "Comparison & analytics",
        "Quality & release gates",
        "CI/CD & security",
        "Migration & compatibility",
    }),
    "Gate": frozenset({
        "None",
        "Human",
        "Licence",
        "Credential",
        "External",
        "Publication",
    }),
    "Evidence State": frozenset({
        "Unverified",
        "Partial",
        "Verified",
        "Blocked",
    }),
    "Item Type": frozenset({"Issue", "Track"}),
    "Epic": frozenset(),
    "Track ID": frozenset(),
}

REQUIRED_WORKFLOWS = frozenset({
    "Auto-add sub-issues to project",
    "Auto-close issue",
    "Item added to project",
    "Item closed",
    "Pull request linked to issue",
    "Pull request merged",
})


class Availability(StrEnum):
    """Whether the authenticated read-only request returned evidence."""

    AVAILABLE = "available"
    PERMISSION_UNAVAILABLE = "permission_unavailable"
    NOT_SUPPORTED = "not_supported"
    FAILED = "failed"


class ControlStatus(StrEnum):
    """Result for one independently evaluated hosted control."""

    VERIFIED = "verified"
    NONCONFORMING = "nonconforming"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class QualificationState(StrEnum):
    """Maximum conclusion supported by the snapshot."""

    QUALIFIED = "qualified"
    PARTIAL = "partial"
    REJECTED = "rejected"


def canonical_json(value: object) -> bytes:
    """Serialize one evidence value with stable keys and a final newline."""
    return orjson.dumps(
        value,
        option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_SORT_KEYS,
    )


def evidence_digest(
    *,
    availability: Availability,
    http_status: int,
    data: JsonValue | None,
    limitation: str | None,
) -> str:
    """Bind normalized evidence and its availability classification."""
    return sha256(
        canonical_json({
            "availability": availability.value,
            "data": data,
            "http_status": http_status,
            "limitation": limitation,
        })
    ).hexdigest()


class HostedObservation(FrozenModel):
    """One normalized REST or GraphQL response and its exact digest."""

    name: str = Field(min_length=1)
    request: str = Field(min_length=1)
    availability: Availability
    http_status: int = Field(ge=0, le=599)
    response_sha256: str = Field(pattern=SHA256)
    data: JsonValue | None = None
    limitation: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def evidence_matches_availability_and_digest(self) -> HostedObservation:
        if self.availability is Availability.AVAILABLE:
            if self.data is None or self.limitation is not None:
                raise ValueError("available evidence requires data only")
            if not HTTP_SUCCESS_MIN <= self.http_status < HTTP_SUCCESS_MAX:
                raise ValueError("available evidence requires a 2xx response")
        elif self.data is not None or self.limitation is None:
            raise ValueError("unavailable evidence requires a limitation only")
        expected = evidence_digest(
            availability=self.availability,
            http_status=self.http_status,
            data=self.data,
            limitation=self.limitation,
        )
        if self.response_sha256 != expected:
            raise ValueError(
                "observation digest does not match normalized evidence"
            )
        return self


class HostedGovernanceSnapshot(FrozenModel):
    """Point-in-time evidence acquired without mutating GitHub."""

    schema_id: Literal[
        "global-medicines-atlas.stable-v1-hosted-governance.snapshot"
    ] = "global-medicines-atlas.stable-v1-hosted-governance.snapshot"
    schema_version: Literal[1] = 1
    repository: Literal["edithatogo/global-medicines-atlas"]
    project_owner: Literal["edithatogo"]
    project_number: Literal[35]
    acquisition_mode: Literal["github-read-only"] = "github-read-only"
    observations: tuple[HostedObservation, ...]

    @model_validator(mode="after")
    def observation_inventory_is_complete(self) -> HostedGovernanceSnapshot:
        names = [item.name for item in self.observations]
        if len(names) != len(set(names)):
            raise ValueError("hosted observation names must be unique")
        if set(names) != set(REQUIRED_OBSERVATIONS):
            raise ValueError("hosted observation inventory is incomplete")
        return self

    def canonical_json(self) -> bytes:
        """Return deterministic snapshot bytes."""
        return canonical_json(self.model_dump(mode="json"))

    def digest(self) -> str:
        """Return the immutable snapshot identity."""
        return sha256(self.canonical_json()).hexdigest()


class GovernanceControl(FrozenModel):
    """One control conclusion with stable evidence references."""

    control_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    status: ControlStatus
    evidence: tuple[str, ...] = Field(min_length=1)
    findings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def status_matches_findings(self) -> GovernanceControl:
        if self.status is ControlStatus.VERIFIED and self.findings:
            raise ValueError("verified controls cannot contain findings")
        if self.status is not ControlStatus.VERIFIED and not self.findings:
            raise ValueError("unverified controls require findings")
        return self


class HostedGovernanceReceipt(FrozenModel):
    """Deterministic qualification derived solely from the snapshot."""

    schema_id: Literal[
        "global-medicines-atlas.stable-v1-hosted-governance.receipt"
    ] = "global-medicines-atlas.stable-v1-hosted-governance.receipt"
    schema_version: Literal[1] = 1
    receipt_id: str = Field(min_length=1)
    snapshot_sha256: str = Field(pattern=SHA256)
    repository: Literal["edithatogo/global-medicines-atlas"]
    default_branch: str | None
    default_branch_sha: str | None = Field(default=None, pattern=SHA40)
    project_url: str | None
    controls: tuple[GovernanceControl, ...]
    qualification_state: QualificationState
    github_mutated: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def conclusion_matches_controls(self) -> HostedGovernanceReceipt:
        statuses = {item.status for item in self.controls}
        expected = (
            QualificationState.REJECTED
            if ControlStatus.FAILED in statuses
            else QualificationState.PARTIAL
            if statuses - {ControlStatus.VERIFIED}
            else QualificationState.QUALIFIED
        )
        if self.qualification_state is not expected:
            raise ValueError("qualification state does not match controls")
        return self

    def canonical_json(self) -> bytes:
        """Return deterministic receipt bytes."""
        return canonical_json(self.model_dump(mode="json"))

    def digest(self) -> str:
        """Return the deterministic receipt identity."""
        return sha256(self.canonical_json()).hexdigest()


def make_observation(
    *,
    name: str,
    request: str,
    availability: Availability,
    http_status: int,
    data: JsonValue | None = None,
    limitation: str | None = None,
) -> HostedObservation:
    """Construct one digest-bound normalized observation."""
    return HostedObservation(
        name=name,
        request=request,
        availability=availability,
        http_status=http_status,
        data=data,
        limitation=limitation,
        response_sha256=evidence_digest(
            availability=availability,
            http_status=http_status,
            data=data,
            limitation=limitation,
        ),
    )


def _mapping(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return cast("dict[str, JsonValue]", value)


def _sequence(value: JsonValue, label: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    return cast("list[JsonValue]", value)


def _text(value: JsonValue, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label} must be text")
    return value


def _integer(value: JsonValue, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{label} must be an integer")
    return value


def _observation(
    snapshot: HostedGovernanceSnapshot,
    name: str,
) -> HostedObservation:
    return next(item for item in snapshot.observations if item.name == name)


def _availability_control(
    *,
    control_id: str,
    observations: tuple[HostedObservation, ...],
) -> GovernanceControl | None:
    failures = [
        item
        for item in observations
        if item.availability is Availability.FAILED
    ]
    if failures:
        return GovernanceControl(
            control_id=control_id,
            status=ControlStatus.FAILED,
            evidence=tuple(item.name for item in observations),
            findings=tuple(f"request:{item.name}:failed" for item in failures),
        )
    unavailable = [
        item
        for item in observations
        if item.availability is not Availability.AVAILABLE
    ]
    if unavailable:
        return GovernanceControl(
            control_id=control_id,
            status=ControlStatus.UNAVAILABLE,
            evidence=tuple(item.name for item in observations),
            findings=tuple(
                f"request:{item.name}:{item.availability.value}"
                for item in unavailable
            ),
        )
    return None


def _evaluated_control(
    *,
    control_id: str,
    observations: tuple[HostedObservation, ...],
    findings: list[str],
) -> GovernanceControl:
    unavailable = _availability_control(
        control_id=control_id,
        observations=observations,
    )
    if unavailable is not None:
        return unavailable
    return GovernanceControl(
        control_id=control_id,
        status=(
            ControlStatus.NONCONFORMING if findings else ControlStatus.VERIFIED
        ),
        evidence=tuple(item.name for item in observations),
        findings=tuple(sorted(set(findings))),
    )


def _repository_controls(
    snapshot: HostedGovernanceSnapshot,
) -> tuple[GovernanceControl, GovernanceControl, GovernanceControl]:
    repository = _observation(snapshot, "repository")
    protection = _observation(snapshot, "branch_protection")
    rulesets = _observation(snapshot, "rulesets")
    repo_findings: list[str] = []
    if repository.availability is Availability.AVAILABLE:
        data = _mapping(repository.data, "repository")
        expected = {
            "full_name": "edithatogo/global-medicines-atlas",
            "private": False,
            "archived": False,
            "disabled": False,
            "default_branch": "main",
            "has_issues": True,
            "has_projects": True,
            "web_commit_signoff_required": True,
            "allow_squash_merge": True,
            "allow_merge_commit": False,
            "allow_rebase_merge": False,
            "allow_auto_merge": True,
            "delete_branch_on_merge": True,
        }
        repo_findings.extend(
            f"repository:{key}:expected:{value}"
            for key, value in expected.items()
            if data.get(key) != value
        )
    repository_control = _evaluated_control(
        control_id="repository_identity",
        observations=(repository,),
        findings=repo_findings,
    )

    protection_findings: list[str] = []
    if protection.availability is Availability.AVAILABLE:
        data = _mapping(protection.data, "protection")
        required = _sequence(data.get("required_checks"), "required checks")
        observed_checks = {_text(item, "required check") for item in required}
        protection_findings.extend(
            f"required-check:missing:{item}"
            for item in sorted(REQUIRED_CHECKS - observed_checks)
        )
        protection_findings.extend(
            f"branch-protection:{key}:disabled"
            for key in (
                "strict",
                "enforce_admins",
                "required_linear_history",
                "required_conversation_resolution",
            )
            if data.get(key) is not True
        )
        protection_findings.extend(
            f"branch-protection:{key}:enabled"
            for key in ("allow_force_pushes", "allow_deletions")
            if data.get(key) is not False
        )
    protection_control = _evaluated_control(
        control_id="default_branch_and_required_checks",
        observations=(protection,),
        findings=protection_findings,
    )

    ruleset_findings: list[str] = []
    if rulesets.availability is Availability.AVAILABLE:
        data = _mapping(rulesets.data, "rulesets")
        if _integer(data.get("count"), "ruleset count") == 0 and (
            protection.availability is not Availability.AVAILABLE
        ):
            ruleset_findings.append("rulesets:none-without-classic-protection")
    ruleset_control = _evaluated_control(
        control_id="rulesets_or_classic_protection",
        observations=(rulesets, protection),
        findings=ruleset_findings,
    )
    return repository_control, protection_control, ruleset_control


def _security_control(snapshot: HostedGovernanceSnapshot) -> GovernanceControl:
    names = (
        "repository",
        "actions_permissions",
        "code_scanning_default_setup",
        "private_vulnerability_reporting",
        "automated_security_fixes",
        "vulnerability_alerts",
        "dependabot_alerts",
        "code_scanning_alerts",
        "secret_scanning_alerts",
    )
    observations = tuple(_observation(snapshot, name) for name in names)
    findings: list[str] = []
    if all(
        item.availability is Availability.AVAILABLE for item in observations
    ):
        repository = _mapping(observations[0].data, "repository")
        security = _mapping(repository.get("security_and_analysis"), "security")
        for feature in (
            "secret_scanning",
            "secret_scanning_push_protection",
            "dependabot_security_updates",
        ):
            value = _mapping(security.get(feature), feature)
            if value.get("status") != "enabled":
                findings.append(f"security:{feature}:disabled")
        actions = _mapping(observations[1].data, "actions")
        if actions.get("enabled") is not True:
            findings.append("security:actions:disabled")
        if actions.get("sha_pinning_required") is not True:
            findings.append("security:actions:sha-pinning-disabled")
        private_reporting = _mapping(observations[3].data, "private reporting")
        if private_reporting.get("enabled") is not True:
            findings.append("security:private-vulnerability-reporting:disabled")
        fixes = _mapping(observations[4].data, "security fixes")
        if fixes.get("enabled") is not True or fixes.get("paused") is not False:
            findings.append("security:automated-security-fixes:not-active")
        alerts = _mapping(observations[5].data, "alerts")
        if alerts.get("enabled") is not True:
            findings.append("security:vulnerability-alerts:disabled")
        setup = _mapping(observations[2].data, "code scanning")
        if setup.get("state") == "not-configured":
            protection = _mapping(
                _observation(snapshot, "branch_protection").data,
                "protection",
            )
            checks = {
                _text(item, "required check")
                for item in _sequence(
                    protection.get("required_checks"), "required checks"
                )
            }
            if "CodeQL" not in checks:
                findings.append("security:code-scanning:not-configured")
    return _evaluated_control(
        control_id="security_features",
        observations=observations,
        findings=findings,
    )


def _issue_control(snapshot: HostedGovernanceSnapshot) -> GovernanceControl:
    observation = _observation(snapshot, "issue_hierarchy")
    findings: list[str] = []
    if observation.availability is Availability.AVAILABLE:
        data = _mapping(observation.data, "issues")
        issues = {
            _integer(item.get("number"), "issue number"): item
            for value in _sequence(data.get("issues"), "issues")
            for item in (_mapping(value, "issue"),)
        }
        expected: dict[int, tuple[int | None, set[int]]] = {
            44: (None, {40}),
            40: (44, {41, 42, 43}),
            41: (40, set()),
            42: (40, set()),
            43: (40, set()),
        }
        for number, (parent, children) in expected.items():
            item = issues.get(number)
            if item is None:
                findings.append(f"issue:{number}:missing")
                continue
            if item.get("parent") != parent:
                findings.append(f"issue:{number}:parent-mismatch")
            actual_children = {
                _integer(child, "subissue")
                for child in _sequence(item.get("subissues"), "subissues")
            }
            if not children <= actual_children:
                findings.append(f"issue:{number}:subissues-mismatch")
    return _evaluated_control(
        control_id="issues_and_subissues",
        observations=(observation,),
        findings=findings,
    )


def _project_controls(
    snapshot: HostedGovernanceSnapshot,
) -> tuple[
    GovernanceControl, GovernanceControl, GovernanceControl, GovernanceControl
]:
    observation = _observation(snapshot, "project")
    if observation.availability is not Availability.AVAILABLE:
        controls = tuple(
            _evaluated_control(
                control_id=control_id,
                observations=(observation,),
                findings=[],
            )
            for control_id in (
                "project_identity",
                "project_fields",
                "project_views",
                "project_workflows_and_items",
            )
        )
        return cast(
            "tuple[GovernanceControl, GovernanceControl, GovernanceControl, GovernanceControl]",
            controls,
        )
    data = _mapping(observation.data, "project")

    identity_findings: list[str] = []
    expected_identity = {
        "number": 35,
        "title": "Global Medicines Atlas Conductor",
        "public": True,
        "closed": False,
        "url": "https://github.com/users/edithatogo/projects/35",
    }
    identity_findings.extend(
        f"project:{key}:mismatch"
        for key, value in expected_identity.items()
        if data.get(key) != value
    )
    repositories = {
        _text(value, "project repository")
        for value in _sequence(data.get("repositories"), "repositories")
    }
    if "edithatogo/global-medicines-atlas" not in repositories:
        identity_findings.append("project:default-repository:missing")

    field_findings: list[str] = []
    fields = {
        _text(item.get("name"), "field name"): item
        for value in _sequence(data.get("fields"), "fields")
        for item in (_mapping(value, "field"),)
    }
    for name, expected_options in REQUIRED_PROJECT_FIELDS.items():
        field = fields.get(name)
        if field is None:
            field_findings.append(f"project-field:{name}:missing")
            continue
        options = {
            _text(option, "field option")
            for option in _sequence(field.get("options"), "field options")
        }
        field_findings.extend(
            f"project-field:{name}:option-missing:{option}"
            for option in sorted(expected_options - options)
        )

    view_findings: list[str] = []
    views = {
        _text(item.get("name"), "view name"): item
        for value in _sequence(data.get("views"), "views")
        for item in (_mapping(value, "view"),)
    }
    expected_layouts = {
        "Board": "BOARD_LAYOUT",
        "Roadmap": "ROADMAP_LAYOUT",
        "Gates & High Risk": "TABLE_LAYOUT",
        "Evidence & Review Due": "TABLE_LAYOUT",
    }
    for name, layout in expected_layouts.items():
        view = views.get(name)
        if view is None:
            view_findings.append(f"project-view:{name}:missing")
        elif view.get("layout") != layout:
            view_findings.append(f"project-view:{name}:layout-mismatch")
    board = views.get("Board")
    if board is not None and "Status" not in _sequence(
        board.get("vertical_group_by"), "board vertical grouping"
    ):
        view_findings.append("project-view:Board:status-grouping-missing")
    for name, required_fields in {
        "Gates & High Risk": {"Gate", "Priority"},
        "Evidence & Review Due": {"Evidence State", "Gate"},
    }.items():
        view = views.get(name)
        if view is None:
            continue
        visible = {
            _text(value, "visible field")
            for value in _sequence(view.get("visible_fields"), "visible fields")
        }
        view_findings.extend(
            f"project-view:{name}:field-missing:{field}"
            for field in sorted(required_fields - visible)
        )

    workflow_findings: list[str] = []
    workflows = {
        _text(item.get("name"), "workflow name"): item
        for value in _sequence(data.get("workflows"), "workflows")
        for item in (_mapping(value, "workflow"),)
    }
    for name in sorted(REQUIRED_WORKFLOWS):
        workflow = workflows.get(name)
        if workflow is None:
            workflow_findings.append(f"project-workflow:{name}:missing")
        elif workflow.get("enabled") is not True:
            workflow_findings.append(f"project-workflow:{name}:disabled")

    items = {
        _integer(item.get("number"), "project item number"): item
        for value in _sequence(data.get("items"), "items")
        for item in (_mapping(value, "project item"),)
    }
    expected_items = {
        40: {"Status": "In Progress", "Evidence State": "Partial"},
        41: {"Status": "Done", "Evidence State": "Verified"},
        42: {"Status": "Done", "Evidence State": "Verified"},
        43: {"Status": "Todo", "Evidence State": "Unverified"},
    }
    for number, expected_values in expected_items.items():
        item = items.get(number)
        if item is None:
            workflow_findings.append(f"project-item:{number}:missing")
            continue
        values = _mapping(item.get("field_values"), "project field values")
        for field, expected in expected_values.items():
            if values.get(field) != expected:
                workflow_findings.append(
                    f"project-item:{number}:{field}:expected:{expected}"
                )

    return (
        _evaluated_control(
            control_id="project_identity",
            observations=(observation,),
            findings=identity_findings,
        ),
        _evaluated_control(
            control_id="project_fields",
            observations=(observation,),
            findings=field_findings,
        ),
        _evaluated_control(
            control_id="project_views",
            observations=(observation,),
            findings=view_findings,
        ),
        _evaluated_control(
            control_id="project_workflows_and_items",
            observations=(observation,),
            findings=workflow_findings,
        ),
    )


def qualify_hosted_governance(
    snapshot: HostedGovernanceSnapshot,
) -> HostedGovernanceReceipt:
    """Evaluate a complete snapshot without contacting or mutating GitHub."""
    controls = (
        *_repository_controls(snapshot),
        _security_control(snapshot),
        _issue_control(snapshot),
        *_project_controls(snapshot),
    )
    statuses = {item.status for item in controls}
    state = (
        QualificationState.REJECTED
        if ControlStatus.FAILED in statuses
        else QualificationState.PARTIAL
        if statuses - {ControlStatus.VERIFIED}
        else QualificationState.QUALIFIED
    )
    repository_observation = _observation(snapshot, "repository")
    default_branch: str | None = None
    default_sha: str | None = None
    if repository_observation.availability is Availability.AVAILABLE:
        repository = _mapping(repository_observation.data, "repository")
        default_branch = _text(
            repository.get("default_branch"), "default branch"
        )
        default_sha = _text(repository.get("default_branch_sha"), "default SHA")
    project_observation = _observation(snapshot, "project")
    project_url: str | None = None
    if project_observation.availability is Availability.AVAILABLE:
        project = _mapping(project_observation.data, "project")
        project_url = _text(project.get("url"), "project URL")
    snapshot_digest = snapshot.digest()
    return HostedGovernanceReceipt(
        receipt_id=f"stable-v1-hosted-governance-{snapshot_digest[:16]}",
        snapshot_sha256=snapshot_digest,
        repository=snapshot.repository,
        default_branch=default_branch,
        default_branch_sha=default_sha,
        project_url=project_url,
        controls=controls,
        qualification_state=state,
        limitations=(
            "Point-in-time authenticated GitHub evidence; it is not a perpetual-state claim.",
            "No repository, issue, project, workflow, security, or release setting was mutated.",
            "Permission-unavailable and unsupported endpoints are reported as unavailable, not failed.",
            "User-project GraphQL exposes configured view metadata but not rendered UI behavior.",
            "Organisation-level controls and external publication or release approval are out of scope.",
        ),
    )
