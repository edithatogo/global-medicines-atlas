from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import jsonschema
import pytest
import yaml
from pydantic import JsonValue, ValidationError
from scripts.qualify_stable_v1_hosted_governance import check_artifacts

from global_medicines_atlas.stable_v1_hosted_governance import (
    CODECOV_APP_ID,
    EXTERNAL_REQUIRED_STATUS_CHECKS,
    GITHUB_ACTIONS_APP_ID,
    MAIN_PUSH_MANDATORY_CHECKS,
    PULL_REQUEST_ONLY_MANDATORY_CHECKS,
    REQUIRED_CHECK_APPS,
    REQUIRED_CHECKS,
    Availability,
    ControlStatus,
    GovernanceControl,
    HostedGovernanceReceipt,
    HostedGovernanceSnapshot,
    HostedObservation,
    QualificationState,
    make_observation,
    qualify_hosted_governance,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "quality/snapshots/stable-v1-hosted-governance.json"
RECEIPT_PATH = ROOT / "quality/qualifications/stable-v1-hosted-governance.json"


def _snapshot() -> HostedGovernanceSnapshot:
    return HostedGovernanceSnapshot.model_validate_json(
        SNAPSHOT_PATH.read_bytes()
    )


def _observation(
    snapshot: HostedGovernanceSnapshot, name: str
) -> HostedObservation:
    return next(item for item in snapshot.observations if item.name == name)


def _replace_observation(
    snapshot: HostedGovernanceSnapshot,
    replacement: HostedObservation,
) -> HostedGovernanceSnapshot:
    return snapshot.model_copy(
        update={
            "observations": tuple(
                replacement if item.name == replacement.name else item
                for item in snapshot.observations
            )
        }
    )


def _replace_data(
    snapshot: HostedGovernanceSnapshot,
    name: str,
    mutate: object,
) -> HostedGovernanceSnapshot:
    current = _observation(snapshot, name)
    data = copy.deepcopy(current.data)
    assert isinstance(data, (dict, list))
    assert callable(mutate)
    mutate(data)
    replacement = make_observation(
        name=name,
        request=current.request,
        availability=Availability.AVAILABLE,
        http_status=current.http_status,
        data=cast("JsonValue", data),
    )
    return _replace_observation(snapshot, replacement)


def _control(receipt: HostedGovernanceReceipt, name: str) -> GovernanceControl:
    return next(item for item in receipt.controls if item.control_id == name)


def _workflow_jobs(path: Path) -> dict[str, dict[str, JsonValue]]:
    workflow = cast(
        "dict[str, JsonValue]", yaml.safe_load(path.read_text(encoding="utf-8"))
    )
    return cast("dict[str, dict[str, JsonValue]]", workflow["jobs"])


def _matrix_values(job: dict[str, JsonValue], axis: str) -> list[str]:
    strategy = cast("dict[str, JsonValue]", job["strategy"])
    matrix = cast("dict[str, JsonValue]", strategy["matrix"])
    return cast("list[str]", matrix[axis])


def _test_goblin_check_names(
    jobs: dict[str, dict[str, JsonValue]],
) -> set[str]:
    names = {
        *(
            f"Python 3.14 / {lane}"
            for lane in _matrix_values(jobs["tests"], "lane")
        ),
        *(
            f"Python 3.14 / {profile}"
            for profile in _matrix_values(jobs["quality"], "profile")
        ),
    }
    consumer_strategy = cast(
        "dict[str, JsonValue]", jobs["consumer-compatibility"]["strategy"]
    )
    consumer_matrix = cast("dict[str, JsonValue]", consumer_strategy["matrix"])
    consumer_rows = cast(
        "list[dict[str, JsonValue]]", consumer_matrix["include"]
    )
    names.update(
        f"Consumer / {row['platform']} / Python 3.14" for row in consumer_rows
    )
    names.update(
        cast("str", jobs[job]["name"])
        for job in (
            "mojo",
            "representative-performance",
            "governed-recovery",
            "operational-exercises",
        )
    )
    return names


def test_committed_snapshot_and_receipt_regenerate_exactly_offline() -> None:
    receipt = check_artifacts()

    assert receipt.canonical_json() == RECEIPT_PATH.read_bytes()
    assert receipt.snapshot_sha256 == _snapshot().digest()
    assert receipt.github_mutated is False
    assert any(
        "preceding authorized main-branch protection hardening" in limitation
        for limitation in receipt.limitations
    )


def test_live_snapshot_is_exactly_available_and_point_in_time() -> None:
    snapshot = _snapshot()

    assert all(
        item.availability is Availability.AVAILABLE
        for item in snapshot.observations
    )
    repository = cast(
        "dict[str, JsonValue]", _observation(snapshot, "repository").data
    )
    assert repository["default_branch"] == "main"
    assert repository["default_branch_sha"] == (
        "0917a7d7f1de1b865ca2fc0a6d1a73d5b5aa3204"
    )


def test_required_checks_match_harness_and_exact_hosted_protection() -> None:
    snapshot = _snapshot()
    protection = cast(
        "dict[str, JsonValue]",
        _observation(snapshot, "branch_protection").data,
    )
    observed_checks = set(cast("list[str]", protection["required_checks"]))
    observed_apps = cast("dict[str, int]", protection["required_check_apps"])

    assert len(MAIN_PUSH_MANDATORY_CHECKS) == 26
    assert {"Dependency review"} == PULL_REQUEST_ONLY_MANDATORY_CHECKS
    assert {"codecov/patch"} == EXTERNAL_REQUIRED_STATUS_CHECKS
    assert len(REQUIRED_CHECKS) == 28
    assert observed_checks == REQUIRED_CHECKS
    assert observed_apps == REQUIRED_CHECK_APPS
    assert set(observed_apps.values()) == {
        GITHUB_ACTIONS_APP_ID,
        CODECOV_APP_ID,
    }

    test_jobs = _workflow_jobs(ROOT / ".github/workflows/test-goblin.yml")
    security_jobs = _workflow_jobs(
        ROOT / ".github/workflows/security-context.yml"
    )
    dependency_jobs = _workflow_jobs(
        ROOT / ".github/workflows/dependency-review.yml"
    )
    assert set(test_jobs) == {
        "tests",
        "quality",
        "consumer-compatibility",
        "mojo",
        "representative-performance",
        "governed-recovery",
        "operational-exercises",
        "iceberg-rest-interoperability",
        "ducklake-comparison",
        "free-tier-git-mechanics",
        "table-format-comparison",
        "hudi-comparison",
    }
    assert set(security_jobs) == {
        "leak-detection",
        "context",
        "supply-chain",
        "codeql",
    }
    assert set(dependency_jobs) == {"dependency-review"}

    expanded_test_goblin = _test_goblin_check_names(test_jobs)
    expanded_security = {
        cast("str", job["name"]) for job in security_jobs.values()
    }
    assert (
        expanded_test_goblin | expanded_security == MAIN_PUSH_MANDATORY_CHECKS
    )
    assert cast("str", dependency_jobs["dependency-review"]["name"]) in (
        PULL_REQUEST_ONLY_MANDATORY_CHECKS
    )

    workflow = (ROOT / ".github/workflows/test-goblin.yml").read_text(
        encoding="utf-8"
    )
    assert "COVERAGE_CORE: sysmon" in workflow
    assert "pytest -q -n 2 --dist worksteal" in workflow
    assert "Restore content-validated gremlins cache" in workflow
    assert "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9" in workflow
    assert "'scripts/test_goblin.py', 'src/**/*.py', 'tests/**/*'" in workflow


def test_free_threaded_canary_is_advisory_and_sha_pinned() -> None:
    workflow = (
        ROOT / ".github/workflows/python-free-threaded-canary.yml"
    ).read_text(encoding="utf-8")
    assert "CPython 3.14t / advisory smoke" in workflow
    assert "continue-on-error: true" in workflow
    assert "uv run --python 3.14t" in workflow
    assert "--no-project" in workflow
    assert 'PYTHON_GIL: "0"' in workflow
    assert (
        "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803" in workflow
    )
    assert (
        "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b"
        in workflow
    )
    assert (
        "group: python-free-threaded-canary-${{ github.workflow }}-"
        "${{ github.ref }}" in workflow
    )
    assert "group: python-free-threaded-canary\n" not in workflow


def test_current_receipt_reports_all_hosted_controls_verified() -> None:
    receipt = qualify_hosted_governance(_snapshot())

    assert receipt.qualification_state is QualificationState.QUALIFIED
    assert (
        _control(receipt, "repository_identity").status
        is ControlStatus.VERIFIED
    )
    assert (
        _control(receipt, "security_features").status is ControlStatus.VERIFIED
    )
    assert (
        _control(receipt, "issues_and_subissues").status
        is ControlStatus.VERIFIED
    )
    assert _control(receipt, "project_fields").status is ControlStatus.VERIFIED
    assert _control(receipt, "project_views").findings == ()
    assert _control(receipt, "project_workflows_and_items").findings == ()


@pytest.mark.parametrize(
    ("availability", "status"),
    [
        (Availability.PERMISSION_UNAVAILABLE, 403),
        (Availability.NOT_SUPPORTED, 404),
    ],
)
def test_permission_or_feature_unavailability_is_not_classified_as_failure(
    availability: Availability,
    status: int,
) -> None:
    snapshot = _snapshot()
    current = _observation(snapshot, "project")
    unavailable = make_observation(
        name="project",
        request=current.request,
        availability=availability,
        http_status=status,
        limitation="authenticated principal cannot observe this endpoint",
    )

    receipt = qualify_hosted_governance(
        _replace_observation(snapshot, unavailable)
    )

    assert receipt.qualification_state is QualificationState.PARTIAL
    project_controls = receipt.controls[-4:]
    assert {item.status for item in project_controls} == {
        ControlStatus.UNAVAILABLE
    }
    assert all("failed" not in item.findings for item in project_controls)


def test_operational_request_failure_rejects_the_qualification() -> None:
    snapshot = _snapshot()
    current = _observation(snapshot, "project")
    failed = make_observation(
        name="project",
        request=current.request,
        availability=Availability.FAILED,
        http_status=500,
        limitation="GitHub returned an unexpected server error",
    )

    receipt = qualify_hosted_governance(_replace_observation(snapshot, failed))

    assert receipt.qualification_state is QualificationState.REJECTED
    assert all(
        item.status is ControlStatus.FAILED for item in receipt.controls[-4:]
    )


def test_observation_digest_rejects_tampering() -> None:
    current = _observation(_snapshot(), "repository")
    payload = current.model_dump(mode="json")
    assert isinstance(payload["data"], dict)
    payload["data"]["default_branch"] = "develop"

    with pytest.raises(ValidationError, match="digest"):
        HostedObservation.model_validate(payload)


@pytest.mark.parametrize(
    ("availability", "status", "data", "limitation"),
    [
        (Availability.AVAILABLE, 200, None, None),
        (Availability.AVAILABLE, 500, {}, None),
        (Availability.PERMISSION_UNAVAILABLE, 403, {}, "hidden"),
    ],
)
def test_observation_availability_invariants_are_fail_closed(
    availability: Availability,
    status: int,
    data: JsonValue | None,
    limitation: str | None,
) -> None:
    with pytest.raises(ValidationError, match=r"evidence|response"):
        make_observation(
            name="invalid",
            request="GET invalid",
            availability=availability,
            http_status=status,
            data=data,
            limitation=limitation,
        )


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("repository", []),
        ("branch_protection", {"required_checks": {}}),
        ("branch_protection", {"required_checks": [1]}),
        ("rulesets", {"count": True}),
    ],
)
def test_malformed_available_evidence_fails_offline_normalization(
    name: str,
    data: JsonValue,
) -> None:
    snapshot = _snapshot()
    current = _observation(snapshot, name)
    malformed = make_observation(
        name=name,
        request=current.request,
        availability=Availability.AVAILABLE,
        http_status=200,
        data=data,
    )

    with pytest.raises(TypeError):
        qualify_hosted_governance(_replace_observation(snapshot, malformed))


def test_snapshot_rejects_missing_or_duplicate_observations() -> None:
    payload = _snapshot().model_dump(mode="json")
    observations = cast("list[object]", payload["observations"])
    payload["observations"] = observations[:-1]
    with pytest.raises(ValidationError, match="inventory"):
        HostedGovernanceSnapshot.model_validate(payload)

    payload = _snapshot().model_dump(mode="json")
    observations = cast("list[object]", payload["observations"])
    payload["observations"] = [*observations, observations[0]]
    with pytest.raises(ValidationError, match="unique"):
        HostedGovernanceSnapshot.model_validate(payload)


def test_repository_and_branch_policy_mismatches_are_nonconforming() -> None:
    snapshot = _replace_data(
        _snapshot(),
        "repository",
        lambda data: cast("dict[str, JsonValue]", data).update({
            "private": True
        }),
    )
    snapshot = _replace_data(
        snapshot,
        "branch_protection",
        lambda data: cast("dict[str, JsonValue]", data).update({
            "strict": False,
            "allow_force_pushes": True,
            "required_checks": [],
        }),
    )

    receipt = qualify_hosted_governance(snapshot)

    assert _control(receipt, "repository_identity").status is (
        ControlStatus.NONCONFORMING
    )
    findings = _control(receipt, "default_branch_and_required_checks").findings
    assert "branch-protection:strict:disabled" in findings
    assert "branch-protection:allow_force_pushes:enabled" in findings
    assert "required-check:missing:CodeQL" in findings


@pytest.mark.parametrize(
    "required_check",
    [
        "Consumer / linux / Python 3.14",
        "Consumer / macos / Python 3.14",
        "Consumer / windows / Python 3.14",
        "Python 3.14 / governed recovery rehearsal",
        "Python 3.14 / operational exercises",
    ],
)
def test_each_hardening_lane_is_mandatory(required_check: str) -> None:
    def remove_required_check(data: object) -> None:
        protection = cast("dict[str, JsonValue]", data)
        checks = cast("list[str]", protection["required_checks"])
        protection["required_checks"] = [
            item for item in checks if item != required_check
        ]
        apps = cast("dict[str, int]", protection["required_check_apps"])
        apps.pop(required_check)

    snapshot = _replace_data(
        _snapshot(), "branch_protection", remove_required_check
    )
    control = _control(
        qualify_hosted_governance(snapshot),
        "default_branch_and_required_checks",
    )

    assert control.status is ControlStatus.NONCONFORMING
    assert f"required-check:missing:{required_check}" in control.findings


def test_required_check_app_identity_mismatch_is_nonconforming() -> None:
    required_check = "Python 3.14 / governed recovery rehearsal"

    def spoof_app(data: object) -> None:
        protection = cast("dict[str, JsonValue]", data)
        apps = cast("dict[str, int]", protection["required_check_apps"])
        apps[required_check] = CODECOV_APP_ID

    snapshot = _replace_data(_snapshot(), "branch_protection", spoof_app)
    control = _control(
        qualify_hosted_governance(snapshot),
        "default_branch_and_required_checks",
    )

    assert control.status is ControlStatus.NONCONFORMING
    assert (
        "required-check-app:mismatch:Python 3.14 / governed recovery rehearsal:"
        f"expected:{GITHUB_ACTIONS_APP_ID}:observed:{CODECOV_APP_ID}"
        in control.findings
    )


def test_active_destructive_update_ruleset_is_bound_to_the_default_branch() -> (
    None
):
    control = _control(
        qualify_hosted_governance(_snapshot()),
        "rulesets_or_classic_protection",
    )

    assert control.status is ControlStatus.VERIFIED
    rulesets = cast(
        "dict[str, JsonValue]", _observation(_snapshot(), "rulesets").data
    )
    assert rulesets == {
        "count": 1,
        "rulesets": [
            {
                "enforcement": "active",
                "id": 20156276,
                "name": "Protect main from destructive updates",
                "target": "branch",
            }
        ],
    }


def test_security_control_detects_disabled_features_and_codeql_gap() -> None:
    def disable_security(data: object) -> None:
        repository = cast("dict[str, JsonValue]", data)
        security = cast(
            "dict[str, JsonValue]", repository["security_and_analysis"]
        )
        security["secret_scanning"] = {"status": "disabled"}

    snapshot = _replace_data(_snapshot(), "repository", disable_security)
    snapshot = _replace_data(
        snapshot,
        "actions_permissions",
        lambda data: cast("dict[str, JsonValue]", data).update({
            "enabled": False,
            "sha_pinning_required": False,
        }),
    )
    snapshot = _replace_data(
        snapshot,
        "private_vulnerability_reporting",
        lambda data: cast("dict[str, JsonValue]", data).update({
            "enabled": False
        }),
    )
    snapshot = _replace_data(
        snapshot,
        "automated_security_fixes",
        lambda data: cast("dict[str, JsonValue]", data).update({
            "enabled": False,
            "paused": True,
        }),
    )
    snapshot = _replace_data(
        snapshot,
        "vulnerability_alerts",
        lambda data: cast("dict[str, JsonValue]", data).update({
            "enabled": False
        }),
    )
    snapshot = _replace_data(
        snapshot,
        "branch_protection",
        lambda data: cast("dict[str, JsonValue]", data).update({
            "required_checks": []
        }),
    )

    findings = _control(
        qualify_hosted_governance(snapshot), "security_features"
    ).findings

    assert "security:secret_scanning:disabled" in findings
    assert "security:actions:disabled" in findings
    assert "security:actions:sha-pinning-disabled" in findings
    assert "security:private-vulnerability-reporting:disabled" in findings
    assert "security:automated-security-fixes:not-active" in findings
    assert "security:vulnerability-alerts:disabled" in findings
    assert "security:code-scanning:not-configured" in findings


def test_issue_hierarchy_mismatch_is_fail_closed() -> None:
    def detach_phase(data: object) -> None:
        issues = cast(
            "list[dict[str, JsonValue]]",
            cast("dict[str, JsonValue]", data)["issues"],
        )
        next(item for item in issues if item["number"] == 43)["parent"] = None

    snapshot = _replace_data(_snapshot(), "issue_hierarchy", detach_phase)
    control = _control(
        qualify_hosted_governance(snapshot), "issues_and_subissues"
    )

    assert control.status is ControlStatus.NONCONFORMING
    assert "issue:43:parent-mismatch" in control.findings


def test_missing_issue_and_subissue_are_both_reported() -> None:
    def remove_issue_and_child(data: object) -> None:
        payload = cast("dict[str, JsonValue]", data)
        issues = cast("list[dict[str, JsonValue]]", payload["issues"])
        payload["issues"] = [item for item in issues if item["number"] != 43]
        parent = next(item for item in issues if item["number"] == 40)
        parent["subissues"] = []

    control = _control(
        qualify_hosted_governance(
            _replace_data(
                _snapshot(), "issue_hierarchy", remove_issue_and_child
            )
        ),
        "issues_and_subissues",
    )

    assert "issue:43:missing" in control.findings
    assert "issue:40:subissues-mismatch" in control.findings


def test_project_identity_and_field_options_are_verified_exactly() -> None:
    def remove_contracts(data: object) -> None:
        project = cast("dict[str, JsonValue]", data)
        project["repositories"] = []
        fields = cast("list[dict[str, JsonValue]]", project["fields"])
        gate = next(item for item in fields if item["name"] == "Gate")
        gate["options"] = []

    receipt = qualify_hosted_governance(
        _replace_data(_snapshot(), "project", remove_contracts)
    )

    assert (
        "project:default-repository:missing"
        in _control(receipt, "project_identity").findings
    )
    assert (
        "project-field:Gate:option-missing:Human"
        in _control(receipt, "project_fields").findings
    )


def test_project_workflow_disable_is_reported() -> None:
    def disable_workflow(data: object) -> None:
        workflows = cast(
            "list[dict[str, JsonValue]]",
            cast("dict[str, JsonValue]", data)["workflows"],
        )
        workflows[0]["enabled"] = False

    receipt = qualify_hosted_governance(
        _replace_data(_snapshot(), "project", disable_workflow)
    )

    assert any(
        finding.startswith("project-workflow:")
        and finding.endswith(":disabled")
        for finding in _control(receipt, "project_workflows_and_items").findings
    )


def test_missing_project_components_and_view_contracts_are_reported() -> None:
    def remove_components(data: object) -> None:
        project = cast("dict[str, JsonValue]", data)
        fields = cast("list[dict[str, JsonValue]]", project["fields"])
        project["fields"] = [item for item in fields if item["name"] != "Epic"]
        views = cast("list[dict[str, JsonValue]]", project["views"])
        project["views"] = [
            item for item in views if item["name"] != "Evidence & Review Due"
        ]
        board = next(item for item in views if item["name"] == "Board")
        board["layout"] = "TABLE_LAYOUT"
        board["vertical_group_by"] = []
        workflows = cast("list[dict[str, JsonValue]]", project["workflows"])
        project["workflows"] = workflows[1:]
        items = cast("list[dict[str, JsonValue]]", project["items"])
        project["items"] = [item for item in items if item["number"] != 43]

    receipt = qualify_hosted_governance(
        _replace_data(_snapshot(), "project", remove_components)
    )

    assert (
        "project-field:Epic:missing"
        in _control(receipt, "project_fields").findings
    )
    view_findings = _control(receipt, "project_views").findings
    assert "project-view:Evidence & Review Due:missing" in view_findings
    assert "project-view:Board:layout-mismatch" in view_findings
    assert "project-view:Board:status-grouping-missing" in view_findings
    item_findings = _control(receipt, "project_workflows_and_items").findings
    assert "project-item:43:missing" in item_findings
    assert any(finding.endswith(":missing") for finding in item_findings)


def test_unavailable_repository_and_project_omit_hosted_identity_fields() -> (
    None
):
    snapshot = _snapshot()
    for name in ("repository", "project"):
        current = _observation(snapshot, name)
        snapshot = _replace_observation(
            snapshot,
            make_observation(
                name=name,
                request=current.request,
                availability=Availability.PERMISSION_UNAVAILABLE,
                http_status=403,
                limitation="permission unavailable",
            ),
        )

    receipt = qualify_hosted_governance(snapshot)

    assert receipt.default_branch is None
    assert receipt.default_branch_sha is None
    assert receipt.project_url is None


def _fix_project_drift(data: object) -> None:
    project = cast("dict[str, JsonValue]", data)
    views = cast("list[dict[str, JsonValue]]", project["views"])
    gates = next(item for item in views if item["name"] == "Gates & High Risk")
    gates["visible_fields"] = [
        *cast("list[JsonValue]", gates["visible_fields"]),
        "Gate",
        "Priority",
    ]
    evidence = next(
        item for item in views if item["name"] == "Evidence & Review Due"
    )
    evidence["visible_fields"] = [
        *cast("list[JsonValue]", evidence["visible_fields"]),
        "Evidence State",
        "Gate",
    ]
    items = cast("list[dict[str, JsonValue]]", project["items"])
    for number in (41, 42):
        item = next(value for value in items if value["number"] == number)
        field_values = cast("dict[str, JsonValue]", item["field_values"])
        field_values["Status"] = "Done"
        field_values["Evidence State"] = "Verified"


def test_resolving_snapshot_drift_produces_a_fully_qualified_receipt() -> None:
    snapshot = _replace_data(_snapshot(), "project", _fix_project_drift)

    receipt = qualify_hosted_governance(snapshot)

    assert receipt.qualification_state is QualificationState.QUALIFIED
    assert {item.status for item in receipt.controls} == {
        ControlStatus.VERIFIED
    }


def test_receipt_and_control_models_reject_forged_conclusions() -> None:
    with pytest.raises(ValidationError, match="verified controls"):
        GovernanceControl(
            control_id="forged_control",
            status=ControlStatus.VERIFIED,
            evidence=("repository",),
            findings=("forged",),
        )
    with pytest.raises(ValidationError, match="require findings"):
        GovernanceControl(
            control_id="forged_control",
            status=ControlStatus.NONCONFORMING,
            evidence=("repository",),
        )
    payload = qualify_hosted_governance(_snapshot()).model_dump(mode="json")
    payload["qualification_state"] = "partial"
    with pytest.raises(ValidationError, match="does not match controls"):
        HostedGovernanceReceipt.model_validate(payload)


def test_generated_json_schemas_validate_committed_artifacts() -> None:
    pairs = (
        (
            ROOT / "schemas/stable-v1-hosted-governance-snapshot-v1.json",
            SNAPSHOT_PATH,
        ),
        (
            ROOT / "schemas/stable-v1-hosted-governance-receipt-v1.json",
            RECEIPT_PATH,
        ),
    )
    for schema_path, artifact_path in pairs:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(
            json.loads(artifact_path.read_text(encoding="utf-8"))
        )
