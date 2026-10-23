"""The repository's active Python runtime is pinned to the qualified patch."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_selects_python_3151_and_rejects_older_series() -> None:
    assert (ROOT / ".python-version").read_text().strip() == "3.15.1"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["project"]["requires-python"] == ">=3.15,<3.16"
    assert project["tool"]["basedpyright"]["pythonVersion"] == "3.15"
    assert project["tool"]["ty"]["environment"]["python-version"] == "3.15"
    assert project["tool"]["ruff"]["target-version"] == "py315"


def test_active_ci_uses_python_3151_only() -> None:
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml"))
    assert workflows
    for workflow in workflows:
        content = workflow.read_text()
        assert not re.search(
            r"(?:Python|CPython) 3\.14|--python 3\.14|python-version:\s*['\"]?3\.14|"
            r"--python 3\.1[0-4](?:\.|\b)|python_version\s*=\s*['\"]3\.1[0-4]",
            content,
        ), workflow.relative_to(ROOT)


def test_project_execution_manifests_select_python_3151() -> None:
    pixi = tomllib.loads((ROOT / "pixi.toml").read_text())
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text())
    pylock = tomllib.loads((ROOT / "pylock.toml").read_text())
    toolchain = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pixi["dependencies"]["python"] == "3.15.*"
    assert "--python 3.15.1" in pixi["tasks"]["python-sync"]
    assert "--python 3.15.1" in pixi["tasks"]["python-test"]
    assert uv_lock["requires-python"] == "==3.15.*"
    assert pylock["requires-python"] == "==3.15.*"
    assert toolchain["project"]["requires-python"] == ">=3.15,<3.16"
    release_toolchain = json.loads(
        (ROOT / "quality/release-build-toolchain.json").read_text()
    )
    assert release_toolchain["python"] == "3.15.1"
    clean_consumer = (ROOT / "scripts/qualify_clean_consumer.py").read_text()
    assert "platform.python_version()" in clean_consumer
    assert "observed_python != python_version" in clean_consumer
