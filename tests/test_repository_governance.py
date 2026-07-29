from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def test_single_canonical_renovate_configuration() -> None:
    assert not (ROOT / "renovate.json5").exists()
    config = json.loads((ROOT / "renovate.json").read_text(encoding="utf-8"))
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
        "docs/data-sources/SOURCE_RIGHTS.md",
    ):
        assert (ROOT / filename).is_file()
    assert not (ROOT / "LICENSE").exists()


def test_licence_selection_remains_an_explicit_maintainer_gate() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    follow_ups = (ROOT / ".github/EXTERNAL_FOLLOW_UPS.md").read_text(
        encoding="utf-8"
    )
    source_rights = (ROOT / "docs/data-sources/SOURCE_RIGHTS.md").read_text(
        encoding="utf-8"
    )

    assert "\nlicense =" not in pyproject
    assert "\nlicense:" not in citation
    assert "\nversion:" not in citation
    assert "\ndate-released:" not in citation
    assert "maintainer" in follow_ups.lower()
    assert "licence" in follow_ups.lower()
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
