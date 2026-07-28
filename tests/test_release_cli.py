"""Adversarial tests for the temporal release qualification CLI boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed git executable
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_cli() -> ModuleType:
    script = (
        Path(__file__).parents[1] / "scripts" / "qualify_temporal_release.py"
    )
    specification = importlib.util.spec_from_file_location(
        "release_cli", script
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


CLI = _load_cli()


def _git(repository: Path, *arguments: str) -> None:
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("git is unavailable")
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [executable, "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "tests@example.invalid")
    _git(tmp_path, "config", "user.name", "Tests")
    (tmp_path / ".gitignore").write_text("build/\n", encoding="utf-8")
    (tmp_path / "tracked.json").write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "tracked.json")
    _git(tmp_path, "commit", "-m", "fixture")
    return tmp_path


@pytest.mark.parametrize(
    "requested",
    [Path("../outside.json"), Path("build/../../outside.json")],
)
def test_output_rejects_traversal(repository: Path, requested: Path) -> None:
    with pytest.raises(ValueError, match="descendant"):
        CLI._safe_output(repository, requested)


def test_output_rejects_tracked_path(repository: Path) -> None:
    tracked_build = repository / "build" / "tracked.json"
    tracked_build.parent.mkdir()
    tracked_build.write_text("{}\n", encoding="utf-8")
    _git(repository, "add", "-f", "build/tracked.json")

    with pytest.raises(ValueError, match="tracked"):
        CLI._safe_output(repository, Path("build/tracked.json"))


def test_output_rejects_symlink_parent(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    link = repository / "build" / "linked"
    link.mkdir(parents=True)
    original = Path.is_symlink

    def is_test_symlink(path: Path) -> bool:
        return path == link or original(path)

    monkeypatch.setattr(
        Path,
        "is_symlink",
        is_test_symlink,
    )

    with pytest.raises(ValueError, match="symlink"):
        CLI._safe_output(repository, Path("build/linked/evidence.json"))


def test_input_evidence_is_deterministic(tmp_path: Path) -> None:
    paths: dict[str, Path] = {}
    for name in ("receipts", "coverage", "snapshots", "gates"):
        path = tmp_path / f"{name}.json"
        path.write_bytes(f'{{"name":"{name}"}}\n'.encode())
        paths[name] = path

    first = CLI._input_evidence(**paths)
    second = CLI._input_evidence(
        gates=paths["gates"],
        snapshots=paths["snapshots"],
        coverage=paths["coverage"],
        receipts=paths["receipts"],
    )

    assert first == second
    assert tuple(first) == (
        "receipts_sha256",
        "coverage_sha256",
        "snapshots_sha256",
        "gates_sha256",
    )
    assert all(len(digest) == 64 for digest in first.values())


def test_input_evidence_matches_exact_file_bytes(tmp_path: Path) -> None:
    paths: dict[str, Path] = {}
    for name in ("receipts", "coverage", "snapshots", "gates"):
        path = tmp_path / f"{name}.json"
        path.write_bytes(f'{{ "name": "{name}" }}\r\n'.encode())
        paths[name] = path

    evidence = CLI._input_evidence(**paths)

    for name, path in paths.items():
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        assert evidence[f"{name}_sha256"] == expected


def test_atomic_write_replaces_without_temporary_files(
    repository: Path,
) -> None:
    output = CLI._safe_output(repository, Path("build/evidence.json"))
    CLI._atomic_write(output, b"first")
    CLI._atomic_write(output, b"second")

    assert output.read_bytes() == b"second"
    assert list(output.parent.glob(".evidence.json.*.tmp")) == []


def test_request_approval_fails_before_reading_ordinary_gate_json(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify_temporal_release.py",
            "--repository",
            str(repository),
            "--receipts",
            "missing-receipts.json",
            "--coverage",
            "missing-coverage.json",
            "--snapshots",
            "missing-snapshots.json",
            "--gates",
            "ordinary-gates.json",
            "--dataset-schema-version",
            "2",
            "--migration-version",
            "1-to-2",
            "--request-approval",
        ],
    )

    with pytest.raises(SystemExit, match="separately verified"):
        CLI.main()
