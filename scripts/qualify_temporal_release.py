"""Create deterministic temporal release evidence without publishing it."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed git executable
import tempfile
from pathlib import Path
from typing import Final

import orjson
from pydantic import TypeAdapter

from global_medicines_atlas.coverage import CoverageObservation
from global_medicines_atlas.receipts import FailureReceipt, SourceReceipt
from global_medicines_atlas.release_evidence import (
    GateStatus,
    InputEvidenceDigests,
    inspect_git_state,
    qualify_release,
)
from global_medicines_atlas.snapshots import SnapshotManifest

Receipt = SourceReceipt | FailureReceipt
_INPUT_NAMES: Final = ("receipts", "coverage", "snapshots", "gates")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--gates", type=Path, required=True)
    parser.add_argument("--dataset-schema-version", action="append", required=True)
    parser.add_argument("--migration-version", action="append", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/release-evidence/temporal-v1.json"),
    )
    parser.add_argument(
        "--request-approval",
        action="store_true",
        help="Deprecated: approval requires a separately verified approval receipt.",
    )
    return parser


def _json(path: Path) -> object:
    return orjson.loads(path.read_bytes())


def _input_evidence(
    *,
    receipts: Path,
    coverage: Path,
    snapshots: Path,
    gates: Path,
) -> dict[str, str]:
    """Return deterministic SHA-256 identities for all qualification inputs."""
    paths = (receipts, coverage, snapshots, gates)
    return {
        f"{name}_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in zip(_INPUT_NAMES, paths, strict=True)
    }


def _git(
    repository: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is required for release evidence")
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [executable, "-C", str(repository), *arguments],
        check=check,
        capture_output=True,
        shell=False,
        text=True,
    )


def _safe_output(repository: Path, requested: Path) -> Path:
    """Require a nonsymlinked, ignored, untracked output below repository/build."""
    repository = repository.resolve(strict=True)
    build = (repository / "build").resolve(strict=False)
    candidate = requested if requested.is_absolute() else repository / requested
    candidate = candidate.resolve(strict=False)
    if not candidate.is_relative_to(build) or candidate == build:
        raise ValueError("output must be a descendant of repository/build")

    relative = candidate.relative_to(repository)
    current = repository
    for part in relative.parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise ValueError("output path must not contain symlinks")

    tracked = _git(
        repository,
        "ls-files",
        "--error-unmatch",
        "--",
        relative.as_posix(),
        check=False,
    )
    if tracked.returncode == 0:
        raise ValueError("output must not overwrite a tracked path")
    ignored = _git(
        repository,
        "check-ignore",
        "--quiet",
        "--",
        relative.as_posix(),
        check=False,
    )
    if ignored.returncode != 0:
        raise ValueError("output must be git-ignored")
    return candidate


def _atomic_write(path: Path, payload: bytes) -> None:
    """Atomically replace an allowed build artifact without following symlinks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("output path must not be a symlink")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Qualify supplied evidence and write only ignored build output."""
    arguments = _parser().parse_args()
    if arguments.request_approval:
        raise SystemExit(
            "--request-approval is disabled; approval requires a separately "
            "verified, content-bound approval receipt"
        )
    repository = arguments.repository.resolve(strict=True)
    output = _safe_output(repository, arguments.output)
    input_evidence = _input_evidence(
        receipts=arguments.receipts,
        coverage=arguments.coverage,
        snapshots=arguments.snapshots,
        gates=arguments.gates,
    )
    receipts = TypeAdapter(list[Receipt]).validate_python(_json(arguments.receipts))
    coverage = TypeAdapter(list[CoverageObservation]).validate_python(
        _json(arguments.coverage)
    )
    snapshots = TypeAdapter(list[SnapshotManifest]).validate_python(
        _json(arguments.snapshots)
    )
    gates = TypeAdapter(dict[str, GateStatus]).validate_python(_json(arguments.gates))
    evidence = qualify_release(
        git=inspect_git_state(repository),
        receipts=receipts,
        coverage=coverage,
        snapshots=snapshots,
        gate_outcomes=gates,
        dataset_schema_versions=arguments.dataset_schema_version,
        migration_versions=arguments.migration_version,
        request_approval=False,
        input_evidence=InputEvidenceDigests(**input_evidence),
    )
    _atomic_write(output, evidence.canonical_json())
    print(output)


if __name__ == "__main__":
    main()
