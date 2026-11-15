"""Contracts for fail-open heavyweight CI change classification."""

from pathlib import Path
from types import SimpleNamespace

import yaml
from scripts import classify_ci_changes
from scripts.classify_ci_changes import requires_heavy_ci


def test_documentation_and_conductor_only_changes_are_lightweight() -> None:
    assert not requires_heavy_ci(("docs/testing/test-goblin.md",))
    assert not requires_heavy_ci((
        "conductor/tracks/example/plan.md",
        "conductor/tracks.md",
    ))


def test_every_governed_runtime_surface_requires_heavy_ci() -> None:
    paths = (
        ".github/workflows/test-goblin.yml",
        "contracts/example.json",
        "quality/qualifications/example.json",
        "schemas/example.json",
        "scripts/example.py",
        "sources/example.py",
        "src/global_medicines_atlas/example.py",
        "tests/test_example.py",
        ".gitattributes",
        "pyproject.toml",
        "uv.lock",
    )
    assert all(requires_heavy_ci((path,)) for path in paths)


def test_changed_paths_includes_deletions(monkeypatch) -> None:
    observed: list[str] = []

    monkeypatch.setattr(classify_ci_changes.shutil, "which", lambda _: "/git")

    def fake_run(command, **_kwargs):
        observed.extend(command)
        return SimpleNamespace(stdout="src/deleted.py\n")

    monkeypatch.setattr(classify_ci_changes.subprocess, "run", fake_run)
    assert classify_ci_changes.changed_paths("base", "head") == (
        "src/deleted.py",
    )
    assert "--diff-filter=ACDMRTUXB" in observed


def test_public_mbs_ci_fails_closed_without_an_explicit_dispatch() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/test-goblin.yml"
    )
    workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    option = workflow["on"]["workflow_dispatch"]["inputs"][
        "acquire_existing_public_mbs"
    ]
    assert option["type"] == "boolean"
    assert option["default"] == "false"
    steps = workflow["jobs"]["public-parquet-iceberg-registration"]["steps"]
    guard = steps[0]
    assert guard["name"] == "Require authorization for public MBS payload reads"
    assert guard["if"] == (
        "github.event_name != 'workflow_dispatch' || "
        "inputs.acquire_existing_public_mbs != true"
    )
    assert "exit 1" in guard["run"]
    assert any(
        step.get("name")
        == "Verify and register the exact existing public MBS Parquet object"
        for step in steps[1:]
    )
    assert any(
        step.get("name")
        == "Verify exact public MBS six-table B2-to-Silver row-value parity"
        for step in steps[1:]
    )
