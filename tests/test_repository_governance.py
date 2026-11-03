# ruff: file-ignore[subprocess-without-shell-equals-true]

from __future__ import annotations

import configparser
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tomllib
from pathlib import Path

import pytest
import yaml
from scripts import build_dependency_snapshot as dependency_snapshot

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
CONDUCTOR_PLUGIN = ".agents/plugins/conductor"
CONDUCTOR_PLUGIN_URL = "https://github.com/gemini-cli-extensions/conductor.git"
CONDUCTOR_SKILLS = (
    "conductor-setup",
    "conductor-new-track",
    "conductor-implement",
    "conductor-status",
    "conductor-review",
    "conductor-revert",
)


def test_single_canonical_renovate_configuration() -> None:
    assert not (ROOT / "renovate.json5").exists()
    config = json.loads((ROOT / "renovate.json").read_text(encoding="utf-8"))
    assert "github>edithatogo/renovate-config" in config["extends"]
    enabled_managers = set(config["enabledManagers"])
    assert {
        "pep621",
        "pixi",
        "github-actions",
        "custom.regex",
    } <= enabled_managers
    assert "uv" not in enabled_managers
    assert any(
        "pep621" in rule.get("matchManagers", [])
        for rule in config["packageRules"]
    )
    assert "pep621" in enabled_managers, (
        "Renovate's pep621 manager owns pyproject.toml and uv.lock"
    )
    assert config["minimumReleaseAge"] == "7 days"
    assert config["automerge"] is False
    github_rules = [
        rule
        for rule in config["packageRules"]
        if "github-actions" in rule.get("matchManagers", [])
    ]
    assert github_rules
    assert github_rules[0]["pinDigests"] is True


def test_required_community_health_files_exist() -> None:
    for filename in (
        "SECURITY.md",
        "CONTRIBUTING.md",
        "SUPPORT.md",
        "CODE_OF_CONDUCT.md",
        "CITATION.cff",
        "CHANGELOG.md",
        "NOTICE",
        "LICENSE",
        "DATA_LICENSE.md",
        "docs/governance/licensing-decision.md",
        "docs/data-sources/SOURCE_RIGHTS.md",
    ):
        assert (ROOT / filename).is_file()
    assert "Apache License" in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_licence_decision_is_explicit_and_data_rights_remain_bounded() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    follow_ups = (ROOT / ".github/EXTERNAL_FOLLOW_UPS.md").read_text(
        encoding="utf-8"
    )
    source_rights = (ROOT / "docs/data-sources/SOURCE_RIGHTS.md").read_text(
        encoding="utf-8"
    )

    data_licence = (ROOT / "DATA_LICENSE.md").read_text(encoding="utf-8")
    decision = (ROOT / "docs/governance/licensing-decision.md").read_text(
        encoding="utf-8"
    )

    assert '\nlicense = "Apache-2.0"' in pyproject
    assert "\nlicense: Apache-2.0" in citation
    assert '\nversion: "1.0.0rc1"' in citation
    assert '\ndate-released: "2026-08-01"' in citation
    assert "third-party" in data_licence.lower()
    assert "cc-by-4.0" in decision.lower()
    assert "licence detection" in follow_ups.lower()
    assert "does not grant" in source_rights.lower()


def test_workflow_actions_are_immutable_and_permissions_are_explicit() -> None:
    yaml = pytest.importorskip("yaml")
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        assert "permissions" in document, workflow
        for line in workflow.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith("- uses:"):
                continue
            revision = stripped.split("@", 1)[1].split()[0]
            assert FULL_SHA.fullmatch(revision), f"{workflow}: {revision}"


def test_issue_forms_and_labels_are_machine_readable() -> None:
    yaml = pytest.importorskip("yaml")
    for filename in (
        "source-onboarding.yml",
        "data-incident.yml",
        "config.yml",
    ):
        payload = yaml.safe_load(
            (ROOT / ".github/ISSUE_TEMPLATE" / filename).read_text(
                encoding="utf-8"
            )
        )
        assert isinstance(payload, dict)
    labels = yaml.safe_load(
        (ROOT / ".github/labels.yml").read_text(encoding="utf-8")
    )
    names = {label["name"] for label in labels}
    assert {
        "type:data-source",
        "type:data-incident",
        "status:external-gate",
    } <= names


def test_conductor_plugin_is_pinned_git_submodule() -> None:
    modules = configparser.ConfigParser()
    parsed = modules.read(ROOT / ".gitmodules")
    assert parsed, "missing .gitmodules"
    section = f'submodule "{CONDUCTOR_PLUGIN}"'
    assert modules.has_section(section)
    assert modules.get(section, "path") == CONDUCTOR_PLUGIN
    assert modules.get(section, "url") == CONDUCTOR_PLUGIN_URL
    assert modules.get(section, "branch") == "main"

    git = shutil.which("git")
    if git is None:
        pytest.skip("git is unavailable")
    recorded = subprocess.run(
        [git, "ls-tree", "HEAD", CONDUCTOR_PLUGIN],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    mode, object_type, rest = recorded.stdout.split(maxsplit=2)
    sha = rest.split("\t", 1)[0]
    assert mode == "160000"
    assert object_type == "commit"
    assert FULL_SHA.fullmatch(sha)


def test_cursor_skills_delegate_to_pinned_conductor_plugin() -> None:
    for name in CONDUCTOR_SKILLS:
        skill = ROOT / ".cursor" / "skills" / name / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        relative = f"{CONDUCTOR_PLUGIN}/skills/{name}/SKILL.md"
        assert f"name: {name}" in text
        assert relative in text
        assert "git submodule update --init --recursive" in text


def test_dependency_snapshot_covers_the_entire_lock_deterministically() -> None:
    raw = (ROOT / "uv.lock").read_bytes()
    locked = tomllib.loads(raw.decode())
    snapshot = dependency_snapshot.build_snapshot(
        raw, "a" * 40, "123", "2026-11-03T00:00:00Z"
    )
    assert snapshot == dependency_snapshot.build_snapshot(
        raw, "a" * 40, "123", "2026-11-03T00:00:00Z"
    )
    resolved = snapshot["manifests"]["uv.lock"]["resolved"]
    registry = [p for p in locked["package"] if "registry" in p["source"]]
    assert set(resolved) == {
        dependency_snapshot.package_url(p) for p in registry
    }
    assert "pkg:pypi/filelock@4.2.4" in resolved
    assert "pkg:pypi/msgpack@1.2.3" in resolved
    for name in ("lancedb", "pyiceberg", "pip-audit", "colorama"):
        assert any(key.startswith(f"pkg:pypi/{name}@") for key in resolved)
    assert all(
        set(row["dependencies"]) <= set(resolved) for row in resolved.values()
    )
    assert snapshot["job"]["correlator"] == "gma-uv-lock-main"


def test_dependency_snapshot_rejects_ambiguous_and_unsupported_identities() -> (
    None
):
    root = {
        "name": "project",
        "source": {"editable": "."},
        "dependencies": [{"name": "example"}],
    }
    first = {
        "name": "example",
        "version": "1.0",
        "source": {"registry": "https://pypi.org/simple"},
    }
    second = {**first, "version": "2.0"}
    document = {"package": [root, first, second]}
    with pytest.raises(ValueError, match="ambiguous"):
        dependency_snapshot.resolved_inventory(document)
    root["dependencies"] = [{"name": "example", "version": "1.0"}]
    assert len(dependency_snapshot.resolved_inventory(document)) == 2
    with pytest.raises(ValueError, match="duplicate"):
        dependency_snapshot.resolved_inventory({
            "package": [root, first, first]
        })
    with pytest.raises(ValueError, match="unsupported"):
        dependency_snapshot.resolved_inventory({
            "package": [
                root,
                {**first, "source": {"git": "https://example.invalid/private"}},
            ]
        })


@pytest.mark.parametrize(
    "change",
    [
        {"GITHUB_ACTIONS": "false"},
        {"GITHUB_EVENT_NAME": "pull_request"},
        {"GITHUB_REF": "refs/heads/feature"},
        {"GITHUB_SHA": "b" * 40},
        {"GITHUB_REPOSITORY": "example/other"},
    ],
)
def test_dependency_submission_requires_exact_trusted_main(change) -> None:
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
    }
    dependency_snapshot.require_trusted_main(env, "a" * 40)
    with pytest.raises(ValueError, match="exact trusted main"):
        dependency_snapshot.require_trusted_main({**env, **change}, "a" * 40)


def test_dependency_submission_workflow_keeps_write_scope_off_prs() -> None:
    document = yaml.safe_load(
        (ROOT / ".github/workflows/security-context.yml").read_text()
    )
    assert document["permissions"] == {"contents": "read"}
    job = document["jobs"]["dependency-submission"]
    assert job["needs"] == "supply-chain"
    assert job["permissions"] == {"contents": "write"}
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "github.event_name == 'push'" in job["if"]
    assert "github.event_name == 'workflow_dispatch'" in job["if"]
    assert "pull_request" not in job["if"]
