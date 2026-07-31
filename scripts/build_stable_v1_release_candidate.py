"""Build or verify an unsigned, unapproved stable-v1 release candidate."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tarfile
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

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
    "build-constraints": "quality/release-build-constraints.txt",
    "build-toolchain": "quality/release-build-toolchain.json",
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

_GENERATED_VERSION_PATH = Path("src/global_medicines_atlas/_version.py")
_BUILD_TOOLCHAIN_PATH = Path("quality/release-build-toolchain.json")
_UV_VERSION_PART_COUNT = 2
_CANONICAL_FILE_MODE = 0o100644
_CANONICAL_DIRECTORY_MODE = 0o40755
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

_PACKAGED_TEXT_SAMPLES = (
    "src/global_medicines_atlas/static/atlas-autocomplete.js",
    "conductor/tracks/stable_v1_qualification_20260729/evidence.jsonl",
    "quality/qualifications/stable-v1-hosted-governance.json.sha256",
)

_CONSUMER_PROBE = """
import json
from importlib.metadata import version
from typing import cast
from global_medicines_atlas import __version__
from global_medicines_atlas.api import create_app
from global_medicines_atlas.query_service import ReadOnlyQueryService
schema = create_app(cast(ReadOnlyQueryService, object())).openapi()
print(json.dumps({
    'api': 'passed',
    'metadata_version': version('global-medicines-atlas'),
    'openapi_paths': len(schema['paths']),
    'package_version': __version__,
}, sort_keys=True))
"""


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


def _uv_version_matches(output: str, expected: object) -> bool:
    parts = output.split()
    return len(parts) >= _UV_VERSION_PART_COUNT and parts[
        :_UV_VERSION_PART_COUNT
    ] == ["uv", expected]


def _resolve_release_uv(root: Path, expected: object) -> str:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        for executable in ("uv.exe", "uv"):
            candidate = Path(directory) / executable
            if candidate.is_file():
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    candidates.append(resolved)
    for candidate in candidates:
        try:
            output = _run(root, str(candidate), "--version").decode().strip()
        except OSError, ReleaseCandidateError:
            continue
        if _uv_version_matches(output, expected):
            return str(candidate)
    observed = ", ".join(str(candidate) for candidate in candidates) or "none"
    raise ReleaseCandidateError(
        f"release build requires uv {expected}; candidates: {observed}"
    )


def _verify_build_toolchain(root: Path) -> tuple[Path, str]:
    raw: object = json.loads((root / _BUILD_TOOLCHAIN_PATH).read_text())
    if not isinstance(raw, dict):
        raise ReleaseCandidateError("build toolchain must be a JSON object")
    toolchain = cast("dict[str, object]", raw)
    expected_python = toolchain.get("python")
    actual_python = platform.python_version()
    if expected_python != actual_python:
        raise ReleaseCandidateError(
            f"release build requires Python {expected_python}, got {actual_python}"
        )
    expected_uv = toolchain.get("uv")
    uv_executable = _resolve_release_uv(root, expected_uv)
    constraints = toolchain.get("build_constraints")
    if not isinstance(constraints, str):
        raise ReleaseCandidateError("build constraints path is not recorded")
    path = root / constraints
    if not path.is_file():
        raise ReleaseCandidateError("recorded build constraints do not exist")
    return path, uv_executable


def _remove_generated_version(root: Path) -> None:
    """Remove Hatch VCS state that Git intentionally ignores."""
    path = root / _GENERATED_VERSION_PATH
    if path.exists() and not path.is_file():
        raise ReleaseCandidateError("generated version path is not a file")
    path.unlink(missing_ok=True)


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


def canonicalize_wheel(path: Path) -> None:
    """Rewrite a wheel with platform-independent ZIP metadata and storage."""
    with zipfile.ZipFile(path) as source:
        members = tuple(
            (name, source.read(name), name.endswith("/"))
            for name in sorted(source.namelist())
        )
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, mode="w", compression=zipfile.ZIP_STORED
    ) as archive:
        for name, payload, is_directory in members:
            info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = (
                _CANONICAL_DIRECTORY_MODE
                if is_directory
                else _CANONICAL_FILE_MODE
            ) << 16
            archive.writestr(info, payload)
    path.write_bytes(output.getvalue())


def canonicalize_sdist(path: Path, *, source_date_epoch: str) -> None:
    """Rewrite an sdist with canonical tar and gzip metadata."""
    with tarfile.open(path, mode="r:gz") as source:
        members: list[tuple[tarfile.TarInfo, bytes]] = []
        for member in sorted(source.getmembers(), key=lambda item: item.name):
            extracted = source.extractfile(member) if member.isfile() else None
            if member.isfile() and extracted is None:
                raise ReleaseCandidateError(
                    f"sdist member is unreadable: {member.name}"
                )
            members.append((member, extracted.read() if extracted else b""))
    output = io.BytesIO()
    with (
        gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=output,
            mtime=int(source_date_epoch),
        ) as compressed,
        tarfile.open(
            fileobj=compressed,
            mode="w",
            format=tarfile.PAX_FORMAT,
        ) as archive,
    ):
        for original, payload in members:
            info = tarfile.TarInfo(original.name)
            info.mtime = int(source_date_epoch)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.type = original.type
            info.linkname = original.linkname
            info.mode = 0o755 if original.isdir() else 0o644
            info.size = len(payload) if original.isfile() else 0
            archive.addfile(
                info, io.BytesIO(payload) if original.isfile() else None
            )
    path.write_bytes(output.getvalue())


def _build_once(
    root: Path,
    destination: Path,
    *,
    source_date_epoch: str,
) -> tuple[str, tuple[Path, Path], Path]:
    destination.mkdir(parents=True)
    constraints, uv_executable = _verify_build_toolchain(root)
    environment = dict(os.environ)
    environment["SOURCE_DATE_EPOCH"] = source_date_epoch
    dist = destination / "dist"
    _remove_generated_version(root)
    try:
        _run(
            root,
            uv_executable,
            "build",
            "--build-constraints",
            str(constraints),
            "--out-dir",
            str(dist),
            environment=environment,
        )
    finally:
        _remove_generated_version(root)
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
    canonicalize_wheel(wheels[0])
    canonicalize_sdist(sdists[0], source_date_epoch=source_date_epoch)
    package_version = built_wheel_version(wheels[0])
    sbom = destination / SBOM_PATH
    _run(
        root,
        uv_executable,
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


def portable_venv_python(environment: Path) -> Path:
    """Resolve either standard virtual-environment interpreter layout."""
    candidates = (
        environment / "Scripts/python.exe",
        environment / "bin/python",
    )
    existing = tuple(path for path in candidates if path.is_file())
    if len(existing) != 1:
        raise ReleaseCandidateError(
            "consumer virtual environment has no unambiguous interpreter layout"
        )
    return existing[0]


def _parse_consumer_probe(
    payload: bytes, expected_version: str
) -> dict[str, Any]:
    try:
        raw: object = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseCandidateError(
            "consumer probe did not emit valid JSON"
        ) from error
    if not isinstance(raw, dict):
        raise ReleaseCandidateError("consumer probe must emit one JSON object")
    probe = cast("dict[str, Any]", raw)
    if (
        probe.get("api") != "passed"
        or probe.get("package_version") != expected_version
        or probe.get("metadata_version") != expected_version
        or not isinstance(probe.get("openapi_paths"), int)
        or cast("int", probe["openapi_paths"]) < 1
    ):
        raise ReleaseCandidateError(
            "consumer import, version, or API probe did not match the receipt"
        )
    return probe


def consume_candidate(
    *,
    root: Path,
    stage: Path,
    receipt_path: Path,
    artifact_role: ArtifactRole,
    environment: Path,
) -> dict[str, object]:
    """Install and independently probe one exact candidate distribution."""
    resolved_root = root.resolve(strict=True)
    resolved_stage = stage.resolve(strict=True)
    resolved_environment = (
        environment
        if environment.is_absolute()
        else resolved_root / environment
    )
    if resolved_environment.exists():
        raise ReleaseCandidateError(
            "consumer virtual environment must not already exist"
        )
    _, uv_executable = _verify_build_toolchain(resolved_root)
    receipt = receipt_from_json(receipt_path.resolve(strict=True))
    verify_candidate_package(
        root=resolved_root,
        stage=resolved_stage,
        receipt=receipt,
    )
    matching = tuple(
        artifact
        for artifact in receipt.artifacts
        if artifact.role is artifact_role
    )
    if len(matching) != 1:
        raise ReleaseCandidateError(
            "candidate has no unique requested distribution"
        )
    artifact = matching[0]
    artifact_path = resolved_stage / artifact.path
    resolved_environment.parent.mkdir(parents=True, exist_ok=True)
    _run(
        resolved_root,
        uv_executable,
        "venv",
        "--python",
        "3.14.6",
        str(resolved_environment),
    )
    _run(
        resolved_root,
        uv_executable,
        "pip",
        "install",
        "--python",
        str(resolved_environment),
        str(artifact_path),
    )
    python = portable_venv_python(resolved_environment)
    first_probe = _parse_consumer_probe(
        _run(resolved_root, str(python), "-c", _CONSUMER_PROBE),
        receipt.package_version,
    )
    _run(
        resolved_root,
        str(python),
        "-m",
        "global_medicines_atlas.cli",
        "--help",
    )
    _run(
        resolved_root,
        uv_executable,
        "pip",
        "install",
        "--python",
        str(resolved_environment),
        "--reinstall",
        str(artifact_path),
    )
    second_probe = _parse_consumer_probe(
        _run(resolved_root, str(python), "-c", _CONSUMER_PROBE),
        receipt.package_version,
    )
    if first_probe != second_probe:
        raise ReleaseCandidateError("consumer probe changed after reinstall")
    return {
        "artifact_role": artifact_role.value,
        "artifact_sha256": artifact.sha256,
        "package_version": receipt.package_version,
        "probe": first_probe,
        "reinstall": "passed",
        "state": "passed",
        "venv_layout": python.relative_to(resolved_environment).as_posix(),
    }


def _packaged_text_evidence(root: Path) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for relative in _PACKAGED_TEXT_SAMPLES:
        payload = (root / relative).read_bytes()
        if b"\r\n" in payload or b"\n" not in payload:
            raise ReleaseCandidateError(
                f"packaged text input is not canonical LF: {relative}"
            )
        evidence.append({
            "line_ending": "lf",
            "path": relative,
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    return evidence


def _build_identity_payload(
    build: tuple[str, tuple[Path, Path], Path],
) -> list[dict[str, object]]:
    _, distributions, sbom = build
    paths = (*distributions, sbom)
    roles = ("wheel", "sdist", "sbom")
    return [
        {
            "name": path.name,
            "role": role,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        }
        for role, path in zip(roles, paths, strict=True)
    ]


def clean_detached_reproducibility(root: Path) -> dict[str, object]:
    """Rebuild one commit from detached LF and CRLF-policy worktrees."""
    resolved_root = root.resolve(strict=True)
    source_commit, source_tree, source_date_epoch = _assert_clean_source(
        resolved_root
    )
    policies = (("autocrlf-false", "false"), ("autocrlf-true", "true"))
    builds: list[tuple[str, tuple[Path, Path], Path]] = []
    text_evidence: list[list[dict[str, object]]] = []
    with tempfile.TemporaryDirectory(
        prefix="gma-stable-v1-detached-", ignore_cleanup_errors=True
    ) as temporary:
        temporary_root = Path(temporary)
        for policy, autocrlf in policies:
            checkout = temporary_root / policy
            _run(
                resolved_root,
                "git",
                "-c",
                f"core.autocrlf={autocrlf}",
                "worktree",
                "add",
                "--detach",
                str(checkout),
                source_commit,
            )
            try:
                if _git(
                    checkout,
                    "status",
                    "--porcelain=v1",
                    "--untracked-files=all",
                ):
                    raise ReleaseCandidateError(
                        f"{policy} detached checkout is not clean"
                    )
                if _git(checkout, "rev-parse", "HEAD^{tree}") != source_tree:
                    raise ReleaseCandidateError(
                        f"{policy} detached checkout changed the source tree"
                    )
                text_evidence.append(_packaged_text_evidence(checkout))
                builds.append(
                    _build_once(
                        checkout,
                        temporary_root / f"build-{policy}",
                        source_date_epoch=source_date_epoch,
                    )
                )
            finally:
                _run(
                    resolved_root,
                    "git",
                    "worktree",
                    "remove",
                    "--force",
                    str(checkout),
                )
        if len(builds) != len(policies) or len(text_evidence) != len(policies):
            raise ReleaseCandidateError(
                "both detached checkout policies must complete"
            )
        assert_reproducible_builds(builds[0], builds[1])
        if text_evidence[0] != text_evidence[1]:
            raise ReleaseCandidateError(
                "packaged text identities differ across checkout policies"
            )
        evidence: dict[str, object] = {
            "artifacts": _build_identity_payload(builds[0]),
            "checkout_policies": [policy for policy, _ in policies],
            "cross_platform_ci_required": True,
            "host_platform": platform.system().casefold(),
            "package_version": builds[0][0],
            "packaged_text_inputs": text_evidence[0],
            "source_commit": source_commit,
            "source_tree": source_tree,
            "state": "passed",
        }
        evidence["content_sha256"] = hashlib.sha256(
            canonical_json_bytes(evidence)
        ).hexdigest()
        return evidence


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
            command_id="verify-sdist-consumer",
            argv=(
                "uv",
                "run",
                "--python",
                "3.14.6",
                "python",
                "-m",
                "scripts.build_stable_v1_release_candidate",
                "consume",
                "--root",
                ".",
                "--stage",
                stage,
                "--receipt",
                receipt,
                "--artifact",
                "sdist",
                "--environment",
                "build/stable-v1/consumer-sdist",
            ),
            expected_result=(
                f"the exact {sdist} source distribution creates its own portable "
                "environment and passes import, version, API, CLI and reinstall probes"
            ),
        ),
        VerificationCommand(
            command_id="verify-wheel-consumer",
            argv=(
                "uv",
                "run",
                "--python",
                "3.14.6",
                "python",
                "-m",
                "scripts.build_stable_v1_release_candidate",
                "consume",
                "--root",
                ".",
                "--stage",
                stage,
                "--receipt",
                receipt,
                "--artifact",
                "wheel",
                "--environment",
                "build/stable-v1/consumer-wheel",
            ),
            expected_result=(
                f"the exact {wheel} wheel creates its own portable environment and "
                "passes import, version, API, CLI and reinstall probes"
            ),
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
    consume = subparsers.add_parser("consume")
    consume.add_argument("--root", type=Path, default=ROOT)
    consume.add_argument("--stage", type=Path, default=DEFAULT_STAGE)
    consume.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    consume.add_argument(
        "--artifact",
        type=ArtifactRole,
        choices=(ArtifactRole.WHEEL, ArtifactRole.SDIST),
        required=True,
    )
    consume.add_argument("--environment", type=Path, required=True)
    reproduce = subparsers.add_parser("reproduce")
    reproduce.add_argument("--root", type=Path, default=ROOT)
    reproduce.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve(strict=True)
    if args.command == "reproduce":
        evidence = clean_detached_reproducibility(root)
        if args.output is not None:
            output = (
                args.output if args.output.is_absolute() else root / args.output
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(canonical_json_bytes(evidence))
        print(json.dumps(evidence, sort_keys=True))
        return 0
    stage = args.stage if args.stage.is_absolute() else root / args.stage
    receipt = (
        args.receipt if args.receipt.is_absolute() else root / args.receipt
    )
    if args.command == "consume":
        evidence = consume_candidate(
            root=root,
            stage=stage,
            receipt_path=receipt,
            artifact_role=args.artifact,
            environment=args.environment,
        )
        print(json.dumps(evidence, sort_keys=True))
        return 0
    digest = (
        build_candidate(root, stage, receipt)
        if args.command == "build"
        else verify_candidate(root, stage, receipt)
    )
    print(json.dumps({"content_sha256": digest, "state": "verified"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
