"""Acquire or offline-check stable-v1 hosted GitHub governance evidence."""

# ruff: file-ignore[too-many-branches, too-many-locals, too-many-statements]

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed gh executable
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

import jsonschema
import orjson

from global_medicines_atlas.stable_v1_hosted_governance import (
    Availability,
    HostedGovernanceReceipt,
    HostedGovernanceSnapshot,
    HostedObservation,
    make_observation,
    qualify_hosted_governance,
)

if TYPE_CHECKING:
    from pydantic import JsonValue

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "quality/snapshots/stable-v1-hosted-governance.json"
RECEIPT_PATH = ROOT / "quality/qualifications/stable-v1-hosted-governance.json"
SNAPSHOT_SCHEMA_PATH = (
    ROOT / "schemas/stable-v1-hosted-governance-snapshot-v1.json"
)
RECEIPT_SCHEMA_PATH = (
    ROOT / "schemas/stable-v1-hosted-governance-receipt-v1.json"
)
REPOSITORY = "edithatogo/global-medicines-atlas"
HTTP_SUCCESS_MIN = 200
HTTP_SUCCESS_MAX = 300
HTTP_NOT_SUPPORTED = 404
HEADER_AND_BODY_PARTS = 2

ISSUE_QUERY = """
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    issue44: issue(number: 44) { ...IssueEvidence }
    issue40: issue(number: 40) { ...IssueEvidence }
    issue41: issue(number: 41) { ...IssueEvidence }
    issue42: issue(number: 42) { ...IssueEvidence }
    issue43: issue(number: 43) { ...IssueEvidence }
  }
}
fragment IssueEvidence on Issue {
  number
  title
  state
  url
  parent { number }
  subIssues(first: 100) { totalCount nodes { number } }
}
"""

PROJECT_QUERY = """
query($login: String!, $number: Int!) {
  user(login: $login) {
    projectV2(number: $number) {
      id
      number
      title
      shortDescription
      readme
      public
      closed
      url
      repositories(first: 100) { totalCount nodes { nameWithOwner } }
      fields(first: 100) {
        totalCount
        nodes {
          __typename
          ... on ProjectV2FieldCommon { id name dataType }
          ... on ProjectV2SingleSelectField { options { id name } }
        }
      }
      views(first: 100) {
        totalCount
        nodes {
          id
          number
          name
          layout
          filter
          configuration {
            visibleFields(first: 100) {
              nodes { ... on ProjectV2FieldCommon { name } }
            }
          }
          fields(first: 100) {
            nodes { ... on ProjectV2FieldCommon { name } }
          }
          groupByFields(first: 100) {
            nodes { ... on ProjectV2FieldCommon { name } }
          }
          verticalGroupByFields(first: 100) {
            nodes { ... on ProjectV2FieldCommon { name } }
          }
          sortByFields(first: 100) {
            nodes {
              direction
              field { ... on ProjectV2FieldCommon { name } }
            }
          }
        }
      }
      workflows(first: 100) {
        totalCount
        nodes { id name enabled number }
      }
      items(first: 100) {
        totalCount
        nodes {
          id
          type
          content {
            ... on Issue {
              number
              title
              state
              url
              repository { nameWithOwner }
              parent { number }
            }
          }
          fieldValues(first: 100) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldTextValue {
                text
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2FieldCommon { name } }
              }
            }
          }
        }
      }
    }
  }
}
"""


def _gh(
    arguments: list[str], *, standard_input: str | None = None
) -> tuple[int, str, str]:
    executable = shutil.which("gh")
    if executable is None:
        raise RuntimeError("GitHub CLI is required for live acquisition")
    completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [executable, *arguments],
        check=False,
        capture_output=True,
        input=standard_input,
        shell=False,
        text=True,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _availability(status: int) -> Availability:
    if status in {401, 403}:
        return Availability.PERMISSION_UNAVAILABLE
    if status == HTTP_NOT_SUPPORTED:
        return Availability.NOT_SUPPORTED
    return Availability.FAILED


def _included_response(
    output: str, error: str
) -> tuple[int, JsonValue | None, str | None]:
    match = re.search(r"^HTTP/\S+\s+(?P<status>[0-9]{3})", output, re.MULTILINE)
    if match is None:
        error_match = re.search(r"HTTP (?P<status>[0-9]{3})", error)
        status = int(error_match.group("status")) if error_match else 0
        return (
            status,
            None,
            error.strip() or "GitHub response status unavailable",
        )
    status = int(match.group("status"))
    parts = re.split(r"\r?\n\r?\n", output, maxsplit=1)
    body = parts[1].strip() if len(parts) == HEADER_AND_BODY_PARTS else ""
    if not body:
        return status, {}, None
    try:
        return status, cast("JsonValue", json.loads(body)), None
    except json.JSONDecodeError as exc:
        return status, None, f"GitHub returned invalid JSON: {exc.msg}"


def _rest(
    *,
    name: str,
    endpoint: str,
    normalize: Callable[[JsonValue], JsonValue],
) -> HostedObservation:
    returncode, output, error = _gh(["api", "--include", endpoint])
    status, raw, parse_error = _included_response(output, error)
    if (
        returncode == 0
        and HTTP_SUCCESS_MIN <= status < HTTP_SUCCESS_MAX
        and raw is not None
    ):
        try:
            data = normalize(raw)
        except (KeyError, TypeError, ValueError) as exc:
            return make_observation(
                name=name,
                request=f"GET {endpoint}",
                availability=Availability.FAILED,
                http_status=status,
                limitation=f"normalization failed: {exc}",
            )
        return make_observation(
            name=name,
            request=f"GET {endpoint}",
            availability=Availability.AVAILABLE,
            http_status=status,
            data=data,
        )
    return make_observation(
        name=name,
        request=f"GET {endpoint}",
        availability=_availability(status),
        http_status=status,
        limitation=parse_error
        or error.strip()
        or f"GitHub returned HTTP {status}",
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


def _view_names(
    view: dict[str, JsonValue],
    connection_name: str,
    *,
    nested: bool = False,
) -> list[str]:
    connection = _mapping(view.get(connection_name), connection_name)
    if nested:
        connection = _mapping(connection.get("visibleFields"), "visible fields")
    return sorted(
        _text(_mapping(node, "view field").get("name"), "view field")
        for node in _sequence(connection.get("nodes"), "view fields")
    )


def _repository_data(raw: JsonValue, default_sha: str) -> JsonValue:
    data = _mapping(raw, "repository")
    keys = (
        "id",
        "node_id",
        "full_name",
        "private",
        "archived",
        "disabled",
        "default_branch",
        "has_issues",
        "has_projects",
        "web_commit_signoff_required",
        "allow_squash_merge",
        "allow_merge_commit",
        "allow_rebase_merge",
        "allow_auto_merge",
        "delete_branch_on_merge",
        "security_and_analysis",
    )
    return {
        **{key: data.get(key) for key in keys},
        "default_branch_sha": default_sha,
    }


def _repository_observation() -> HostedObservation:
    repository = _rest(
        name="repository",
        endpoint=f"repos/{REPOSITORY}",
        normalize=lambda value: value,
    )
    if repository.availability is not Availability.AVAILABLE:
        return repository
    reference = _rest(
        name="repository_ref",
        endpoint=f"repos/{REPOSITORY}/git/ref/heads/main",
        normalize=lambda value: value,
    )
    if reference.availability is not Availability.AVAILABLE:
        return make_observation(
            name="repository",
            request=f"GET repos/{REPOSITORY}; GET repos/{REPOSITORY}/git/ref/heads/main",
            availability=reference.availability,
            http_status=reference.http_status,
            limitation=reference.limitation,
        )
    ref_data = _mapping(reference.data, "Git reference")
    object_data = _mapping(ref_data.get("object"), "Git reference object")
    sha = _text(object_data.get("sha"), "default branch SHA")
    return make_observation(
        name="repository",
        request=f"GET repos/{REPOSITORY}; GET repos/{REPOSITORY}/git/ref/heads/main",
        availability=Availability.AVAILABLE,
        http_status=200,
        data=_repository_data(repository.data, sha),
    )


def _branch_protection(raw: JsonValue) -> JsonValue:
    data = _mapping(raw, "branch protection")
    status_checks = _mapping(
        data.get("required_status_checks"), "status checks"
    )
    contexts = sorted(
        _text(value, "required check")
        for value in _sequence(status_checks.get("contexts"), "contexts")
    )
    check_apps: dict[str, int] = {}
    for value in _sequence(status_checks.get("checks"), "checks"):
        check = _mapping(value, "required status check")
        context = _text(check.get("context"), "required status check context")
        if context in check_apps:
            raise ValueError(f"duplicate required status check: {context}")
        check_apps[context] = _integer(
            check.get("app_id"), f"required status check app for {context}"
        )
    if set(contexts) != set(check_apps):
        raise ValueError(
            "required status check contexts and app bindings differ"
        )
    return cast(
        "JsonValue",
        {
            "strict": status_checks.get("strict"),
            "required_checks": contexts,
            "required_check_apps": dict(sorted(check_apps.items())),
            "enforce_admins": _mapping(
                data.get("enforce_admins"), "admins"
            ).get("enabled"),
            "required_linear_history": _mapping(
                data.get("required_linear_history"), "linear history"
            ).get("enabled"),
            "required_conversation_resolution": _mapping(
                data.get("required_conversation_resolution"),
                "conversation resolution",
            ).get("enabled"),
            "allow_force_pushes": _mapping(
                data.get("allow_force_pushes"), "force pushes"
            ).get("enabled"),
            "allow_deletions": _mapping(
                data.get("allow_deletions"), "deletions"
            ).get("enabled"),
            "required_approving_review_count": _mapping(
                data.get("required_pull_request_reviews"),
                "pull request reviews",
            ).get("required_approving_review_count"),
        },
    )


def _rulesets(raw: JsonValue) -> JsonValue:
    items = _sequence(raw, "rulesets")
    return {
        "count": len(items),
        "rulesets": [
            {
                key: _mapping(item, "ruleset").get(key)
                for key in ("id", "name", "target", "enforcement")
            }
            for item in items
        ],
    }


def _alerts(raw: JsonValue) -> JsonValue:
    return {"accessible": True, "returned_count": len(_sequence(raw, "alerts"))}


def _graphql(
    *,
    name: str,
    query_name: str,
    query: str,
    variables: dict[str, JsonValue],
    normalize: Callable[[dict[str, JsonValue]], JsonValue],
) -> HostedObservation:
    payload = json.dumps({"query": query, "variables": variables})
    returncode, output, error = _gh(
        ["api", "graphql", "--input", "-"], standard_input=payload
    )
    try:
        parsed = _mapping(
            cast("JsonValue", json.loads(output)), "GraphQL response"
        )
    except (json.JSONDecodeError, TypeError) as exc:
        return make_observation(
            name=name,
            request=f"POST graphql:{query_name}",
            availability=Availability.FAILED,
            http_status=0,
            limitation=error.strip() or f"invalid GraphQL response: {exc}",
        )
    errors = parsed.get("errors")
    if returncode or errors is not None:
        serialized = json.dumps(errors, sort_keys=True)
        unavailable = (
            "FORBIDDEN" in serialized or "not have access" in serialized
        )
        return make_observation(
            name=name,
            request=f"POST graphql:{query_name}",
            availability=(
                Availability.PERMISSION_UNAVAILABLE
                if unavailable
                else Availability.FAILED
            ),
            http_status=200 if output else 0,
            limitation=serialized or error.strip() or "GraphQL request failed",
        )
    try:
        data = normalize(_mapping(parsed.get("data"), "GraphQL data"))
    except (KeyError, TypeError, ValueError) as exc:
        return make_observation(
            name=name,
            request=f"POST graphql:{query_name}",
            availability=Availability.FAILED,
            http_status=200,
            limitation=f"normalization failed: {exc}",
        )
    return make_observation(
        name=name,
        request=f"POST graphql:{query_name}",
        availability=Availability.AVAILABLE,
        http_status=200,
        data=data,
    )


def _issues(data: dict[str, JsonValue]) -> JsonValue:
    repository = _mapping(data.get("repository"), "issue repository")
    issues: list[JsonValue] = []
    for key in ("issue44", "issue40", "issue41", "issue42", "issue43"):
        item = _mapping(repository.get(key), key)
        parent = item.get("parent")
        subissues = _mapping(item.get("subIssues"), "subissues")
        nodes = _sequence(subissues.get("nodes"), "subissue nodes")
        if _integer(subissues.get("totalCount"), "subissue total") != len(
            nodes
        ):
            raise ValueError("subissue query was truncated")
        issues.append(
            cast(
                "JsonValue",
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "url": item.get("url"),
                    "parent": (
                        _mapping(parent, "parent").get("number")
                        if parent is not None
                        else None
                    ),
                    "subissues": sorted(
                        _integer(
                            _mapping(node, "subissue").get("number"), "subissue"
                        )
                        for node in nodes
                    ),
                },
            )
        )
    return {"issues": issues}


def _project(data: dict[str, JsonValue]) -> JsonValue:
    user = _mapping(data.get("user"), "project owner")
    project = _mapping(user.get("projectV2"), "project")
    repositories = _mapping(project.get("repositories"), "repositories")
    repository_nodes = _sequence(repositories.get("nodes"), "repository nodes")
    if _integer(repositories.get("totalCount"), "repository total") != len(
        repository_nodes
    ):
        raise ValueError("project repository query was truncated")

    field_connection = _mapping(project.get("fields"), "fields")
    field_nodes = _sequence(field_connection.get("nodes"), "field nodes")
    if _integer(field_connection.get("totalCount"), "field total") != len(
        field_nodes
    ):
        raise ValueError("project field query was truncated")
    fields: list[JsonValue] = []
    for value in field_nodes:
        field = _mapping(value, "field")
        options = field.get("options", [])
        fields.append(
            cast(
                "JsonValue",
                {
                    "name": field.get("name"),
                    "data_type": field.get("dataType"),
                    "options": sorted(
                        _text(_mapping(option, "option").get("name"), "option")
                        for option in _sequence(options, "options")
                    ),
                },
            )
        )

    view_connection = _mapping(project.get("views"), "views")
    view_nodes = _sequence(view_connection.get("nodes"), "view nodes")
    if _integer(view_connection.get("totalCount"), "view total") != len(
        view_nodes
    ):
        raise ValueError("project view query was truncated")
    views: list[JsonValue] = []
    for value in view_nodes:
        view = _mapping(value, "view")

        sort_values: list[JsonValue] = []
        sort_connection = _mapping(view.get("sortByFields"), "sort fields")
        for sort_value in _sequence(sort_connection.get("nodes"), "sort nodes"):
            sort_item = _mapping(sort_value, "sort item")
            sort_values.append(
                cast(
                    "JsonValue",
                    {
                        "field": _mapping(
                            sort_item.get("field"), "sort field"
                        ).get("name"),
                        "direction": sort_item.get("direction"),
                    },
                )
            )
        views.append(
            cast(
                "JsonValue",
                {
                    "number": view.get("number"),
                    "name": view.get("name"),
                    "layout": view.get("layout"),
                    "filter": view.get("filter"),
                    "visible_fields": _view_names(
                        view, "configuration", nested=True
                    ),
                    "fields": _view_names(view, "fields"),
                    "group_by": _view_names(view, "groupByFields"),
                    "vertical_group_by": _view_names(
                        view, "verticalGroupByFields"
                    ),
                    "sort_by": sort_values,
                },
            )
        )

    workflow_connection = _mapping(project.get("workflows"), "workflows")
    workflow_nodes = _sequence(
        workflow_connection.get("nodes"), "workflow nodes"
    )
    if _integer(workflow_connection.get("totalCount"), "workflow total") != len(
        workflow_nodes
    ):
        raise ValueError("project workflow query was truncated")
    workflows = [
        {
            key: _mapping(value, "workflow").get(key)
            for key in ("number", "name", "enabled")
        }
        for value in workflow_nodes
    ]

    item_connection = _mapping(project.get("items"), "items")
    item_nodes = _sequence(item_connection.get("nodes"), "item nodes")
    if _integer(item_connection.get("totalCount"), "item total") != len(
        item_nodes
    ):
        raise ValueError("project item query was truncated")
    items: list[JsonValue] = []
    for value in item_nodes:
        item = _mapping(value, "item")
        content_value = item.get("content")
        if content_value is None:
            continue
        content = _mapping(content_value, "item content")
        number = content.get("number")
        if number not in {40, 41, 42, 43}:
            continue
        field_values: dict[str, JsonValue] = {}
        connection = _mapping(item.get("fieldValues"), "field values")
        for field_value in _sequence(
            connection.get("nodes"), "field value nodes"
        ):
            field_item = _mapping(field_value, "field value")
            field = field_item.get("field")
            if field is None:
                continue
            name = _text(_mapping(field, "field").get("name"), "field name")
            selected = field_item.get("text", field_item.get("name"))
            if selected is not None:
                field_values[name] = selected
        parent = content.get("parent")
        items.append(
            cast(
                "JsonValue",
                {
                    "number": number,
                    "title": content.get("title"),
                    "state": content.get("state"),
                    "url": content.get("url"),
                    "parent": (
                        _mapping(parent, "item parent").get("number")
                        if parent is not None
                        else None
                    ),
                    "field_values": field_values,
                },
            )
        )

    return cast(
        "JsonValue",
        {
            key: project.get(key)
            for key in (
                "id",
                "number",
                "title",
                "shortDescription",
                "readme",
                "public",
                "closed",
                "url",
            )
        }
        | {
            "repositories": sorted(
                _text(
                    _mapping(node, "repository").get("nameWithOwner"),
                    "repository",
                )
                for node in repository_nodes
            ),
            "fields": sorted(
                fields, key=lambda value: str(_mapping(value, "field")["name"])
            ),
            "views": sorted(
                views,
                key=lambda value: _integer(
                    _mapping(value, "view")["number"], "view number"
                ),
            ),
            "workflows": sorted(
                workflows,
                key=lambda value: _integer(
                    _mapping(value, "workflow")["number"], "workflow number"
                ),
            ),
            "items": sorted(
                items,
                key=lambda value: _integer(
                    _mapping(value, "item")["number"], "item number"
                ),
            ),
            "total_item_count": len(item_nodes),
        },
    )


def acquire_snapshot() -> HostedGovernanceSnapshot:
    """Read exact repository and project evidence without any mutation call."""
    observations = (
        _repository_observation(),
        _rest(
            name="rulesets",
            endpoint=f"repos/{REPOSITORY}/rulesets",
            normalize=_rulesets,
        ),
        _rest(
            name="branch_protection",
            endpoint=f"repos/{REPOSITORY}/branches/main/protection",
            normalize=_branch_protection,
        ),
        _rest(
            name="actions_permissions",
            endpoint=f"repos/{REPOSITORY}/actions/permissions",
            normalize=lambda value: value,
        ),
        _rest(
            name="code_scanning_default_setup",
            endpoint=f"repos/{REPOSITORY}/code-scanning/default-setup",
            normalize=lambda value: value,
        ),
        _rest(
            name="private_vulnerability_reporting",
            endpoint=f"repos/{REPOSITORY}/private-vulnerability-reporting",
            normalize=lambda value: value,
        ),
        _rest(
            name="automated_security_fixes",
            endpoint=f"repos/{REPOSITORY}/automated-security-fixes",
            normalize=lambda value: value,
        ),
        _rest(
            name="vulnerability_alerts",
            endpoint=f"repos/{REPOSITORY}/vulnerability-alerts",
            normalize=lambda _value: {"enabled": True},
        ),
        _rest(
            name="dependabot_alerts",
            endpoint=f"repos/{REPOSITORY}/dependabot/alerts?per_page=1",
            normalize=_alerts,
        ),
        _rest(
            name="code_scanning_alerts",
            endpoint=f"repos/{REPOSITORY}/code-scanning/alerts?per_page=1",
            normalize=_alerts,
        ),
        _rest(
            name="secret_scanning_alerts",
            endpoint=f"repos/{REPOSITORY}/secret-scanning/alerts?per_page=1",
            normalize=_alerts,
        ),
        _graphql(
            name="issue_hierarchy",
            query_name="stable-v1-issue-hierarchy-v1",
            query=ISSUE_QUERY,
            variables={"owner": "edithatogo", "repo": "global-medicines-atlas"},
            normalize=_issues,
        ),
        _graphql(
            name="project",
            query_name="stable-v1-project-v1",
            query=PROJECT_QUERY,
            variables={"login": "edithatogo", "number": 35},
            normalize=_project,
        ),
    )
    return HostedGovernanceSnapshot(
        repository=REPOSITORY,
        project_owner="edithatogo",
        project_number=35,
        observations=observations,
    )


def _schema_bytes(
    model: type[HostedGovernanceSnapshot] | type[HostedGovernanceReceipt],
) -> bytes:
    return (
        json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
    ).encode()


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def write_artifacts(
    snapshot: HostedGovernanceSnapshot,
) -> HostedGovernanceReceipt:
    """Write the deterministic snapshot, schemas, receipt and digest sidecars."""
    receipt = qualify_hosted_governance(snapshot)
    _write(SNAPSHOT_PATH, snapshot.canonical_json())
    _write(RECEIPT_PATH, receipt.canonical_json())
    _write(SNAPSHOT_SCHEMA_PATH, _schema_bytes(HostedGovernanceSnapshot))
    _write(RECEIPT_SCHEMA_PATH, _schema_bytes(HostedGovernanceReceipt))
    _write(
        SNAPSHOT_PATH.with_suffix(".json.sha256"),
        f"{snapshot.digest()}\n".encode(),
    )
    _write(
        RECEIPT_PATH.with_suffix(".json.sha256"),
        f"{receipt.digest()}\n".encode(),
    )
    return receipt


def check_artifacts() -> HostedGovernanceReceipt:
    """Regenerate from the committed snapshot and verify every byte offline."""
    snapshot = HostedGovernanceSnapshot.model_validate_json(
        SNAPSHOT_PATH.read_bytes()
    )
    receipt = qualify_hosted_governance(snapshot)
    expected = {
        SNAPSHOT_PATH: snapshot.canonical_json(),
        RECEIPT_PATH: receipt.canonical_json(),
        SNAPSHOT_SCHEMA_PATH: _schema_bytes(HostedGovernanceSnapshot),
        RECEIPT_SCHEMA_PATH: _schema_bytes(HostedGovernanceReceipt),
        SNAPSHOT_PATH.with_suffix(
            ".json.sha256"
        ): f"{snapshot.digest()}\n".encode(),
        RECEIPT_PATH.with_suffix(
            ".json.sha256"
        ): f"{receipt.digest()}\n".encode(),
    }
    for path, content in expected.items():
        if path.read_bytes() != content:
            raise ValueError(
                f"deterministic artifact differs: {path.relative_to(ROOT)}"
            )
    jsonschema.Draft202012Validator(  # pyright: ignore[reportUnknownMemberType]
        json.loads(SNAPSHOT_SCHEMA_PATH.read_text(encoding="utf-8"))
    ).validate(snapshot.model_dump(mode="json"))
    jsonschema.Draft202012Validator(  # pyright: ignore[reportUnknownMemberType]
        json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    ).validate(receipt.model_dump(mode="json"))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--acquire",
        action="store_true",
        help="perform read-only GitHub acquisition before writing artifacts",
    )
    args = parser.parse_args()
    receipt = (
        write_artifacts(acquire_snapshot())
        if args.acquire
        else check_artifacts()
    )
    print(
        orjson.dumps(
            {
                "qualification_state": receipt.qualification_state.value,
                "receipt_sha256": receipt.digest(),
                "snapshot_sha256": receipt.snapshot_sha256,
            },
            option=orjson.OPT_SORT_KEYS,
        ).decode()
    )


if __name__ == "__main__":
    main()
