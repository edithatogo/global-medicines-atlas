"""Acquire a normalized GitHub snapshot; never publish or approve a release."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed gh executable
from pathlib import Path
from typing import Literal, cast

import orjson
from pydantic import AnyHttpUrl

from global_medicines_atlas.protected_evidence import (
    CheckRunObservation,
    HostedEvidenceSnapshot,
    ProtectedEvidencePolicy,
    PublicationEvidence,
    PublicationState,
    PullRequestObservation,
    WorkflowRunObservation,
)

RUN_ID_PATTERN = re.compile(r"/actions/runs/(?P<run_id>[1-9][0-9]*)")


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object")
    mapping = cast("dict[object, object]", value)
    return {str(key): item for key, item in mapping.items()}


def _sequence(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a JSON array")
    return cast("list[object]", value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _count(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _gh_json(endpoint: str) -> dict[str, object]:
    executable = shutil.which("gh")
    if executable is None:
        raise RuntimeError("GitHub CLI is required for hosted acquisition")
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [executable, "api", endpoint],
        check=True,
        capture_output=True,
        shell=False,
        text=True,
    )
    parsed: object = json.loads(result.stdout)
    return _mapping(parsed, endpoint)


def _complete_page(payload: dict[str, object], key: str) -> list[object]:
    items = _sequence(payload.get(key), key)
    total = _count(payload.get("total_count"), "total_count")
    if total > len(items):
        raise RuntimeError(
            f"GitHub returned a truncated {key} page ({len(items)}/{total})"
        )
    return items


def _run_id(details_url: str) -> int | None:
    match = RUN_ID_PATTERN.search(details_url)
    return int(match.group("run_id")) if match is not None else None


def _normalize_check(value: object) -> CheckRunObservation:
    item = _mapping(value, "check run")
    app = _mapping(item.get("app"), "check run app")
    details_url = _text(item.get("details_url"), "check details_url")
    return CheckRunObservation(
        check_run_id=_integer(item.get("id"), "check id"),
        name=_text(item.get("name"), "check name"),
        head_sha=_text(item.get("head_sha"), "check head_sha"),
        status=_text(item.get("status"), "check status"),
        conclusion=_optional_text(item.get("conclusion"), "check conclusion"),
        app_slug=_text(app.get("slug"), "check app slug"),
        workflow_run_id=_run_id(details_url),
        details_url=AnyHttpUrl(details_url),
    )


def _normalize_workflow(value: object) -> WorkflowRunObservation:
    item = _mapping(value, "workflow run")
    return WorkflowRunObservation(
        run_id=_integer(item.get("id"), "workflow run id"),
        name=_text(item.get("name"), "workflow name"),
        head_sha=_text(item.get("head_sha"), "workflow head_sha"),
        status=_text(item.get("status"), "workflow status"),
        conclusion=_optional_text(
            item.get("conclusion"), "workflow conclusion"
        ),
        url=AnyHttpUrl(_text(item.get("html_url"), "workflow html_url")),
    )


def acquire_snapshot(
    policy: ProtectedEvidencePolicy,
    *,
    publication_blocker: str | None,
) -> HostedEvidenceSnapshot:
    """Acquire only evidence; publication remains blocked or not attempted."""
    target = policy.target
    root = f"repos/{target.repository}"
    pull = _gh_json(f"{root}/pulls/{target.pull_request_number}")
    checks_payload = _gh_json(
        f"{root}/commits/{target.commit_sha}/check-runs?per_page=100"
    )
    runs_payload = _gh_json(
        f"{root}/actions/runs?head_sha={target.commit_sha}&per_page=100"
    )
    required_identities = {
        (check.name, check.app_slug) for check in policy.required_checks
    }
    observed_checks = tuple(
        _normalize_check(raw)
        for raw in _complete_page(checks_payload, "check_runs")
    )
    checks = tuple(
        check
        for check in observed_checks
        if (check.name, check.app_slug) in required_identities
    )
    referenced_run_ids = {
        item.workflow_run_id
        for item in checks
        if item.workflow_run_id is not None
    }
    runs = tuple(
        run
        for raw in _complete_page(runs_payload, "workflow_runs")
        if (run := _normalize_workflow(raw)).run_id in referenced_run_ids
    )
    head = _mapping(pull.get("head"), "pull request head")
    raw_state = _text(pull.get("state"), "pull request state")
    if raw_state not in {"open", "closed"}:
        raise ValueError(f"unsupported pull request state: {raw_state}")
    state = cast("Literal['open', 'closed']", raw_state)
    publication = (
        PublicationEvidence(
            state=PublicationState.BLOCKED,
            blockers=(publication_blocker,),
        )
        if publication_blocker is not None
        else PublicationEvidence(state=PublicationState.NOT_ATTEMPTED)
    )
    return HostedEvidenceSnapshot(
        repository=target.repository,
        commit_sha=target.commit_sha,
        pull_request=PullRequestObservation(
            number=_integer(pull.get("number"), "pull request number"),
            head_sha=_text(head.get("sha"), "pull request head sha"),
            state=state,
            url=AnyHttpUrl(
                _text(pull.get("html_url"), "pull request html_url")
            ),
        ),
        workflow_runs=tuple(sorted(runs, key=lambda item: item.run_id)),
        check_runs=tuple(sorted(checks, key=lambda item: item.check_run_id)),
        publication=publication,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publication-blocker")
    arguments = parser.parse_args()
    policy = ProtectedEvidencePolicy.model_validate_json(
        arguments.policy.read_bytes()
    )
    snapshot = acquire_snapshot(
        policy,
        publication_blocker=arguments.publication_blocker,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(
        orjson.dumps(
            snapshot.model_dump(mode="json"),
            option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_SORT_KEYS,
        )
    )
    print(arguments.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
