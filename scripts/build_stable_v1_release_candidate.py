"""Build or verify an unsigned, unapproved stable-v1 release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from scripts.qualify_release import verify_runtime_sbom

from global_medicines_atlas.stable_v1_release_candidate import (
    GUIDE_PATH,
    LOCK_PATH,
    PROVENANCE_PATH,
    SBOM_PATH,
    ArtifactRole,
    CandidateArtifact,
    ProvenanceReference,
    ReferenceKind,
    ReleaseCandidateError,
    VerificationCommand,
    build_receipt,
    candidate_artifact,
    canonical_json_bytes,
    provenance_reference_bytes,
    receipt_from_json,
    reference_payload,
    verify_candidate_package,
    write_manifest_and_checksums,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE = Path("build/stable-v1/release-candidate")
DEFAULT_RECEIPT = Path(
    "quality/qualifications/stable-v1-release-candidate.json"
)

_REFERENCE_FILES = {
    "candidate-implementation": (
        "src/global_medicines_atlas/stable_v1_release_candidate.py"
    ),
    "candidate-schema": "schemas/stable-v1-release-candidate-v1.json",
    "candidate-script": "scripts/build_stable_v1_release_candidate.py",
    "consumer-contract": "schemas/stable-v1-consumer-compatibility-v1.json",
    "consumer-qualification": (
        "quality/qualifications/stable-v1-consumer-compatibility.json"
    ),
    "dependency-lock": "uv.lock",
    "interoperability-lock": "pylock.toml",
    "release-evidence-schema": "schemas/release-evidence-v1.json",
    "release-workflow": ".github/workflows/release-provenance.yml",
}


def _run(
    root: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> bytes:
    try:
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            list(arguments),
            cwd=root,
            env=environment,
            check=True,
            capture_output=True,
            shell=False,
        )
    except subprocess.CalledProcessError as error:
        message = error.stderr.decode(errors="replace").strip()
        raise ReleaseCandidateError(
            f"candidate command failed: {arguments[0]}: {message}"
        ) from error
    return result.stdout


def _git(root: Path, *arguments: str) -> str:
    return _run(root, "git", *arguments).decode().strip()


def _assert_clean_source(root: Path) -> tuple[str, str, str]:
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise ReleaseCandidateError(
            "release-candidate source must be a clean Git worktree"
        )
    commit = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    timestamp = _git(root, "show", "-s", "--format=%ct", commit)
    return commit, tree, timestamp


def canonicalize_sbom(path: Path, version: str) -> None:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ReleaseCandidateError("generated SBOM must be a JSON object")
    sbom = cast("dict[str, object]", raw)
    sbom.pop("serialNumber", None)
    metadata = sbom.get("metadata")
    if not isinstance(metadata, dict):
        raise ReleaseCandidateError("generated SBOM lacks metadata")
    metadata = cast("dict[str, object]", metadata)
    metadata.pop("timestamp", None)
    component = metadata.get("component")
    if not isinstance(component, dict):
        raise ReleaseCandidateError("generated SBOM lacks project component")
    component = cast("dict[str, object]", component)
    component["version"] = version
    path.write_bytes(canonical_json_bytes(sbom))


def built_wheel_version(path: Path) -> str:
    """Read the authoritative PEP 427 version from built wheel metadata."""
    with zipfile.ZipFile(path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        if len(names) != 1:
            raise ReleaseCandidateError(
                "built wheel must contain exactly one METADATA file"
            )
        for line in archive.read(names[0]).decode().splitlines():
            if line.startswith("Version: "):
                return line.removeprefix("Version: ")
    raise ReleaseCandidateError("built wheel metadata lacks Version")


def _build_once(
    root: Path,
    destination: Path,
    *,
    source_date_epoch: str,
) -> tuple[str, tuple[Path, Path], Path]:
    destination.mkdir(parents=True)
    environment = dict(os.environ)
    environment["SOURCE_DATE_EPOCH"] = source_date_epoch
    dist = destination / "dist"
    _run(
        root,
        "uv",
        "build",
        "--out-dir",
        str(dist),
        environment=environment,
    )
    distributions = tuple(sorted(dist.iterdir(), key=lambda path: path.name))
    wheels = tuple(path for path in distributions if path.suffix == ".whl")
    sdists = tuple(
        path for path in distributions if path.name.endswith(".tar.gz")
    )
    unexpected = tuple(
        path
        for path in distributions
        if path not in {*wheels, *sdists} and path.name != ".gitignore"
    )
    if unexpected or len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseCandidateError(
            "build must produce exactly one wheel and one sdist"
        )
    package_version = built_wheel_version(wheels[0])
    sbom = destination / SBOM_PATH
    _run(
        root,
        "uv",
        "export",
        "--locked",
        "--no-dev",
        "--no-default-groups",
        "--preview-features",
        "sbom-export",
        "--format",
        "cyclonedx1.5",
        "--output-file",
        str(sbom),
        environment=environment,
    )
    canonicalize_sbom(sbom, package_version)
    return package_version, (wheels[0], sdists[0]), sbom


def _identity(path: Path) -> tuple[str, str, int]:
    return (
        path.name,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_size,
    )


def assert_reproducible_builds(
    first: tuple[str, tuple[Path, Path], Path],
    second: tuple[str, tuple[Path, Path], Path],
) -> None:
    first_version, first_distributions, first_sbom = first
    second_version, second_distributions, second_sbom = second
    if first_version != second_version:
        raise ReleaseCandidateError(
            "repeated builds produced different versions"
        )
    first_identities = tuple(_identity(path) for path in first_distributions)
    second_identities = tuple(_identity(path) for path in second_distributions)
    if first_identities != second_identities:
        raise ReleaseCandidateError(
            "repeated builds produced different distribution bytes"
        )
    if first_sbom.read_bytes() != second_sbom.read_bytes():
        raise ReleaseCandidateError(
            "repeated builds produced different SBOM bytes"
        )


def _reference(
    root: Path,
    *,
    role: str,
    kind: ReferenceKind,
    locator: str,
    source_commit: str,
) -> ProvenanceReference:
    provisional = ProvenanceReference(
        role=role,
        kind=kind,
        locator=locator,
        sha256="0" * 64,
    )
    payload = provenance_reference_bytes(root, provisional, source_commit)
    return provisional.model_copy(
        update={"sha256": hashlib.sha256(payload).hexdigest()}
    )


def build_provenance_references(
    root: Path, source_commit: str
) -> tuple[ProvenanceReference, ...]:
    """Build the complete sorted source and policy reference set."""
    references = [
        _reference(
            root,
            role=role,
            kind=ReferenceKind.REPOSITORY_FILE,
            locator=f"repo:{path}",
            source_commit=source_commit,
        )
        for role, path in _REFERENCE_FILES.items()
    ]
    references.extend((
        _reference(
            root,
            role="source-commit-object",
            kind=ReferenceKind.GIT_COMMIT_OBJECT,
            locator=f"git:commit:{source_commit}",
            source_commit=source_commit,
        ),
        _reference(
            root,
            role="source-tree-listing",
            kind=ReferenceKind.GIT_TREE_LISTING,
            locator=f"git:tree-listing:{source_commit}",
            source_commit=source_commit,
        ),
    ))
    return tuple(sorted(references, key=lambda item: item.role))


def verification_commands(
    wheel: str, sdist: str
) -> tuple[VerificationCommand, ...]:
    stage = DEFAULT_STAGE.as_posix()
    receipt = DEFAULT_RECEIPT.as_posix()
    values = (
        VerificationCommand(
            command_id="install-sdist",
            argv=(
                "uv",
                "pip",
                "install",
                "--python",
                ".candidate-venv",
                f"{stage}/dist/{sdist}",
            ),
            expected_result="the exact source distribution installs locally",
        ),
        VerificationCommand(
            command_id="install-wheel",
            argv=(
                "uv",
                "pip",
                "install",
                "--python",
                ".candidate-venv",
                f"{stage}/dist/{wheel}",
            ),
            expected_result="the exact wheel installs locally",
        ),
        VerificationCommand(
            command_id="probe-installed-version",
            argv=(
                ".candidate-venv/python",
                "-c",
                "from global_medicines_atlas import __version__; print(__version__)",
            ),
            expected_result="the installed version equals package_version in the receipt",
        ),
        VerificationCommand(
            command_id="verify-candidate",
            argv=(
                "uv",
                "run",
                "--python",
                "3.14.6",
                "python",
                "-m",
                "scripts.build_stable_v1_release_candidate",
                "verify",
                "--root",
                ".",
                "--stage",
                stage,
                "--receipt",
                receipt,
            ),
            expected_result="candidate receipt, package, checksums, SBOM and provenance pass",
        ),
    )
    return tuple(sorted(values, key=lambda item: item.command_id))


def _build_reproducible_payloads(
    root: Path, stage: Path, source_date_epoch: str
) -> tuple[str, Path, Path]:
    with tempfile.TemporaryDirectory(prefix="gma-stable-v1-rc-") as temporary:
        temporary_root = Path(temporary)
        first = _build_once(
            root,
            temporary_root / "first",
            source_date_epoch=source_date_epoch,
        )
        second = _build_once(
            root,
            temporary_root / "second",
            source_date_epoch=source_date_epoch,
        )
        assert_reproducible_builds(first, second)
        package_version, distributions, sbom = first
        dist = stage / "dist"
        dist.mkdir()
        for distribution in distributions:
            shutil.copyfile(distribution, dist / distribution.name)
        shutil.copyfile(sbom, stage / SBOM_PATH)
    return (
        package_version,
        next((stage / "dist").glob("*.whl")),
        next((stage / "dist").glob("*.tar.gz")),
    )


def _candidate_artifacts(
    stage: Path, wheel: Path, sdist: Path
) -> tuple[CandidateArtifact, ...]:
    return tuple(
        sorted(
            (
                candidate_artifact(
                    stage,
                    wheel,
                    role=ArtifactRole.WHEEL,
                    media_type="application/vnd.pypa.wheel+zip",
                ),
                candidate_artifact(
                    stage,
                    sdist,
                    role=ArtifactRole.SDIST,
                    media_type="application/gzip",
                ),
                candidate_artifact(
                    stage,
                    stage / SBOM_PATH,
                    role=ArtifactRole.SBOM,
                    media_type="application/vnd.cyclonedx+json",
                ),
                candidate_artifact(
                    stage,
                    stage / LOCK_PATH,
                    role=ArtifactRole.DEPENDENCY_LOCK,
                    media_type="application/toml",
                ),
                candidate_artifact(
                    stage,
                    stage / PROVENANCE_PATH,
                    role=ArtifactRole.PROVENANCE_REFERENCES,
                    media_type="application/json",
                ),
                candidate_artifact(
                    stage,
                    stage / GUIDE_PATH,
                    role=ArtifactRole.VERIFICATION_GUIDE,
                    media_type="text/markdown",
                ),
            ),
            key=lambda item: item.path,
        )
    )


def build_candidate(root: Path, stage: Path, receipt_path: Path) -> str:
    """Build twice, stage exact bytes, and emit an unsigned candidate receipt."""
    resolved_root = root.resolve(strict=True)
    if stage.exists() and any(stage.iterdir()):
        raise ReleaseCandidateError("candidate stage must be absent or empty")
    stage.mkdir(parents=True, exist_ok=True)
    source_commit, source_tree, source_date_epoch = _assert_clean_source(
        resolved_root
    )
    package_version, wheel, sdist = _build_reproducible_payloads(
        resolved_root, stage, source_date_epoch
    )
    shutil.copyfile(resolved_root / LOCK_PATH, stage / LOCK_PATH)
    shutil.copyfile(
        resolved_root / "docs/qualification/stable-v1-release-candidate.md",
        stage / GUIDE_PATH,
    )

    references = build_provenance_references(resolved_root, source_commit)
    (stage / PROVENANCE_PATH).write_bytes(reference_payload(references))
    artifacts = _candidate_artifacts(stage, wheel, sdist)
    candidate_id = f"stable-v1-rc-{source_commit[:12]}"
    manifest, checksums = write_manifest_and_checksums(
        stage=stage,
        candidate_id=candidate_id,
        source_commit=source_commit,
        source_tree=source_tree,
        package_version=package_version,
        artifacts=artifacts,
    )
    verify_runtime_sbom(
        root=resolved_root,
        sbom_path=stage / SBOM_PATH,
        lock_path=stage / LOCK_PATH,
        project_version=package_version,
    )
    receipt = build_receipt(
        candidate_id=candidate_id,
        source_commit=source_commit,
        source_tree=source_tree,
        package_version=package_version,
        artifacts=artifacts,
        manifest=manifest,
        checksums=checksums,
        provenance_references=references,
        verification_commands=verification_commands(wheel.name, sdist.name),
        limitations=(
            "This local candidate is unsigned and has no provenance attestation.",
            "No maintainer licence or stable-release approval is inferred.",
            "No version-control tag or hosted release has been created.",
            "The candidate has not been uploaded or published to any external service.",
        ),
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(receipt.canonical_bytes())
    verify_candidate_package(root=resolved_root, stage=stage, receipt=receipt)
    return receipt.content_sha256


def verify_candidate(root: Path, stage: Path, receipt_path: Path) -> str:
    """Verify an existing candidate without changing local or hosted state."""
    receipt = receipt_from_json(receipt_path)
    verify_runtime_sbom(
        root=root.resolve(strict=True),
        sbom_path=stage / SBOM_PATH,
        lock_path=stage / LOCK_PATH,
        project_version=receipt.package_version,
    )
    verify_candidate_package(root=root, stage=stage, receipt=receipt)
    return receipt.content_sha256


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--root", type=Path, default=ROOT)
        command.add_argument("--stage", type=Path, default=DEFAULT_STAGE)
        command.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve(strict=True)
    stage = args.stage if args.stage.is_absolute() else root / args.stage
    receipt = (
        args.receipt if args.receipt.is_absolute() else root / args.receipt
    )
    digest = (
        build_candidate(root, stage, receipt)
        if args.command == "build"
        else verify_candidate(root, stage, receipt)
    )
    print(json.dumps({"content_sha256": digest, "state": "verified"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
