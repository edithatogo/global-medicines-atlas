"""Generate and qualify exact release assets without publishing them."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tarfile
import tomllib
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, cast

from packaging.requirements import Requirement

from global_medicines_atlas.publication_contracts import (
    PublicationPackage,
    PublicationVerificationReceipt,
)
from global_medicines_atlas.publication_package import (
    generate_publication_package,
)
from global_medicines_atlas.release_metadata import (
    ImmutableArtifact,
    PrepublicationQualification,
    validate_release_metadata,
)

PROJECT = "global-medicines-atlas"
_TAG = re.compile(
    r"^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:(?:a|b|rc)(?:0|[1-9]\d*))?"
    r"(?:-(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*))*)?$"
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CONTROL_FILES = frozenset({
    "SHA256SUMS",
    "qualification.json",
    "qualified-assets.json",
})


class QualificationError(ValueError):
    """A release input or staged byte failed closed."""


def is_canonical_release_tag(tag: str) -> bool:
    """Return whether a tag uses an approved SemVer or PEP 440 spelling."""

    return _TAG.fullmatch(tag) is not None


def _require_fixture_only(
    contract: PublicationPackage,
    receipt: PublicationVerificationReceipt,
    publication_mode: str,
) -> None:
    fixture_only = contract.contract_version.startswith("fixture-dry-run-")
    if fixture_only and publication_mode != "dry-run":
        raise QualificationError(
            "committed fixture inputs cannot qualify production publication"
        )
    if fixture_only and (
        "no-maintainer-approval" not in receipt.verifier
        or not all(
            item.evidence_uri.host is not None
            and item.evidence_uri.host.endswith(".invalid")
            for item in receipt.evidence
        )
    ):
        raise QualificationError(
            "fixture receipt must deny approval and use reserved evidence URIs"
        )


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, separators=(",", ": "))
        + "\n"
    ).encode()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(path: str) -> PurePosixPath:
    relative = PurePosixPath(path)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or "\\" in path
    ):
        raise QualificationError(f"unsafe package path: {path}")
    return relative


def _contained(root: Path, relative: str) -> Path:
    candidate = root.joinpath(*_safe_relative(relative).parts)
    resolved_root = root.resolve(strict=True)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise QualificationError(
            f"asset is absent or escapes the stage: {relative}"
        ) from error
    if not resolved.is_file():
        raise QualificationError(f"asset is not a regular file: {relative}")
    return resolved


def build_governed_package(
    *,
    root: Path,
    contract_path: Path,
    qualification_path: Path,
    rows_path: Path,
    output: Path,
    publication_mode: str,
) -> tuple[str, ...]:
    """Generate reviewed package bytes into an empty controlled directory."""

    resolved_root = root.resolve(strict=True)
    inputs = tuple(
        path.resolve(strict=True)
        for path in (contract_path, qualification_path, rows_path)
    )
    if any(not path.is_relative_to(resolved_root) for path in inputs):
        raise QualificationError("reviewed inputs must remain inside root")
    if output.exists() and any(output.iterdir()):
        raise QualificationError("package output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    contract = PublicationPackage.model_validate_json(inputs[0].read_text())
    receipt = PublicationVerificationReceipt.model_validate_json(
        inputs[1].read_text()
    )
    _require_fixture_only(contract, receipt, publication_mode)
    rows: list[Mapping[str, Any]] = []
    for number, line in enumerate(inputs[2].read_text().splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise QualificationError(f"row {number} must be a JSON object")
        rows.append(cast("Mapping[str, Any]", value))
    generated = generate_publication_package(contract, receipt, rows)
    written: list[str] = []
    for member in generated.files:
        destination = output.joinpath(*_safe_relative(member.path).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(member.content)
        written.append(member.path)
    return tuple(written)


def _git(root: Path, *arguments: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        raise QualificationError("git executable is unavailable")
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [executable, "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        shell=False,
        text=True,
    )
    return result.stdout.strip()


def _verify_tag(root: Path, tag: str, commit: str) -> str:
    if not is_canonical_release_tag(tag):
        raise QualificationError(
            "release tag must be canonical vSemVer or PEP 440 prerelease"
        )
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise QualificationError("commit must be a full lowercase Git SHA")
    try:
        _git(root, "diff", "--quiet", "HEAD", "--")
    except subprocess.CalledProcessError as error:
        raise QualificationError(
            "tracked release inputs differ from the qualified commit"
        ) from error
    head = _git(root, "rev-parse", "HEAD")
    tagged = _git(root, "rev-parse", f"refs/tags/{tag}^{{commit}}")
    if head != commit or tagged != commit:
        raise QualificationError("tag, checked-out HEAD and commit must agree")
    return tag.removeprefix("v")


def _wheel_metadata(wheel: Path) -> tuple[str, str]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise QualificationError(
                "wheel must contain exactly one METADATA file"
            )
        fields: dict[str, str] = {}
        for line in archive.read(metadata_names[0]).decode().splitlines():
            key, separator, value = line.partition(":")
            if separator and key in {"Name", "Version"}:
                fields[key] = value.strip()
    name = fields.get("Name", "")
    version = fields.get("Version", "")
    normalized = name.casefold().replace("_", "-")
    if normalized != PROJECT or not version:
        raise QualificationError("wheel project identity is invalid")
    filename_version = wheel.name.removeprefix(
        f"{PROJECT.replace('-', '_')}-"
    ).split("-py3-", maxsplit=1)[0]
    if filename_version != version:
        raise QualificationError("wheel filename and METADATA version disagree")
    return normalized, version


def _components(sbom: Mapping[str, object]) -> set[tuple[str, str]]:
    values: set[tuple[str, str]] = set()
    raw_components = sbom.get("components", [])
    if not isinstance(raw_components, list):
        raise QualificationError("CycloneDX components must be a list")
    metadata = sbom.get("metadata", {})
    candidates = cast("list[object]", raw_components).copy()
    if isinstance(metadata, dict):
        component = cast("dict[str, object]", metadata).get("component")
        if isinstance(component, dict):
            candidates.append(cast("dict[str, object]", component))
    for component in candidates:
        if not isinstance(component, dict):
            continue
        component_fields = cast("dict[str, object]", component)
        name = component_fields.get("name")
        version = component_fields.get("version")
        if isinstance(name, str) and isinstance(version, str):
            values.add((name.casefold().replace("_", "-"), version))
    return values


def _dependency_name(value: object) -> tuple[str, frozenset[str]]:
    if not isinstance(value, dict):
        raise QualificationError("uv.lock dependency entry must be a table")
    dependency = cast("dict[str, object]", value)
    name = dependency.get("name")
    extras = dependency.get("extra", [])
    if not isinstance(name, str) or not isinstance(extras, list):
        raise QualificationError("uv.lock dependency identity is invalid")
    raw_extras = cast("list[object]", extras)
    if not all(isinstance(item, str) for item in raw_extras):
        raise QualificationError("uv.lock dependency extras are invalid")
    return (
        name.casefold().replace("_", "-"),
        frozenset(cast("list[str]", extras)),
    )


def _runtime_requirements(root: Path) -> set[tuple[str, frozenset[str]]]:
    manifest = cast(
        "dict[str, object]",
        tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")),
    )
    project = manifest.get("project")
    if not isinstance(project, dict):
        raise QualificationError("pyproject.toml lacks [project]")
    raw_requirements = cast("dict[str, object]", project).get("dependencies")
    if not isinstance(raw_requirements, list):
        raise QualificationError("project runtime dependencies are invalid")
    requirement_values = cast("list[object]", raw_requirements)
    if not all(isinstance(item, str) for item in requirement_values):
        raise QualificationError("project runtime dependencies are invalid")
    return {
        (
            Requirement(item).name.casefold().replace("_", "-"),
            frozenset(Requirement(item).extras),
        )
        for item in cast("list[str]", raw_requirements)
    }


def _lock_packages(
    lock: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    raw_packages = lock.get("package")
    if not isinstance(raw_packages, list):
        raise QualificationError("uv.lock does not contain package records")
    packages: dict[str, dict[str, object]] = {}
    for raw in cast("list[object]", raw_packages):
        if not isinstance(raw, dict):
            raise QualificationError("uv.lock package entry must be a table")
        package = cast("dict[str, object]", raw)
        name = package.get("name")
        if not isinstance(name, str):
            raise QualificationError("uv.lock package name is invalid")
        normalized = name.casefold().replace("_", "-")
        if normalized in packages:
            raise QualificationError("uv.lock package names must be unique")
        packages[normalized] = package
    return packages


def _package_dependencies(
    package: Mapping[str, object], extras: frozenset[str]
) -> list[tuple[str, frozenset[str]]]:
    dependencies = package.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise QualificationError("uv.lock dependencies must be a list")
    result = [
        _dependency_name(item) for item in cast("list[object]", dependencies)
    ]
    optional = package.get("optional-dependencies", {})
    if not isinstance(optional, dict):
        raise QualificationError(
            "uv.lock optional dependencies must be a table"
        )
    optional_groups = cast("dict[str, object]", optional)
    for extra in extras:
        extra_dependencies = optional_groups.get(extra, [])
        if not isinstance(extra_dependencies, list):
            raise QualificationError(
                "uv.lock optional dependency group must be a list"
            )
        result.extend(
            _dependency_name(item)
            for item in cast("list[object]", extra_dependencies)
        )
    return result


def _runtime_lock_closure(
    *, root: Path, lock: Mapping[str, object]
) -> set[tuple[str, str]]:
    direct = _runtime_requirements(root)
    packages = _lock_packages(lock)
    root_package = packages.get(PROJECT)
    if root_package is None:
        raise QualificationError("uv.lock lacks the project root package")
    root_dependencies = root_package.get("dependencies", [])
    if not isinstance(root_dependencies, list):
        raise QualificationError("uv.lock project dependencies are invalid")
    locked_direct = {
        _dependency_name(item)
        for item in cast("list[object]", root_dependencies)
    }
    if direct != locked_direct:
        raise QualificationError(
            "pyproject runtime dependencies disagree with uv.lock"
        )

    expected: set[tuple[str, str]] = set()
    pending = list(direct)
    visited: set[tuple[str, frozenset[str]]] = set()
    while pending:
        name, extras = pending.pop()
        identity = (name, extras)
        if identity in visited:
            continue
        visited.add(identity)
        package = packages.get(name)
        if package is None:
            raise QualificationError(
                f"runtime dependency is not locked: {name}"
            )
        version = package.get("version")
        if not isinstance(version, str):
            raise QualificationError(
                f"runtime dependency lacks a locked version: {name}"
            )
        expected.add((name, version))
        pending.extend(_package_dependencies(package, extras))
    return expected


def verify_runtime_sbom(
    *,
    root: Path,
    sbom_path: Path,
    lock_path: Path,
    project_version: str,
) -> None:
    raw_sbom: object = json.loads(sbom_path.read_text(encoding="utf-8"))
    if not isinstance(raw_sbom, dict):
        raise QualificationError("SBOM must be CycloneDX JSON")
    sbom = cast("dict[str, object]", raw_sbom)
    if sbom.get("bomFormat") != "CycloneDX":
        raise QualificationError("SBOM must be CycloneDX JSON")
    components = _components(sbom)
    if (PROJECT, project_version) not in components:
        raise QualificationError(
            "SBOM does not identify the built project and version"
        )
    lock = cast(
        "dict[str, object]",
        tomllib.loads(lock_path.read_text(encoding="utf-8")),
    )
    expected = _runtime_lock_closure(root=root, lock=lock)
    observed = {item for item in components if item[0] != PROJECT}
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    if missing:
        raise QualificationError(
            f"SBOM omits resolved runtime dependencies: {missing}"
        )
    if unexpected:
        raise QualificationError(
            f"SBOM contains non-runtime or unlocked components: {unexpected}"
        )


def _verify_dataset_archive(stage: Path, version: str) -> None:
    archives = tuple(stage.glob(f"{PROJECT}-dataset-{version}.tar.gz"))
    if len(archives) != 1:
        raise QualificationError(
            "stage must contain exactly one governed dataset archive"
        )
    payloads: dict[str, bytes] = {}
    with tarfile.open(archives[0], mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            path = member.name.removeprefix("./")
            _safe_relative(path)
            if not member.isfile() or path in payloads:
                raise QualificationError("dataset archive has unsafe members")
            stream = archive.extractfile(member)
            if stream is None:
                raise QualificationError("dataset archive member is unreadable")
            payloads[path] = stream.read()
    try:
        manifest_bytes = payloads["package-manifest.json"]
        checksum_bytes = payloads["SHA256SUMS"]
    except KeyError as error:
        raise QualificationError(
            "dataset archive lacks package controls"
        ) from error
    raw_manifest: object = json.loads(manifest_bytes)
    manifest = (
        cast("dict[str, object]", raw_manifest)
        if isinstance(raw_manifest, dict)
        else {}
    )
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise QualificationError("dataset package manifest is empty")
    declared: set[str] = set()
    for raw in cast("list[object]", entries):
        if not isinstance(raw, dict):
            raise QualificationError("invalid dataset manifest entry")
        entry = cast("dict[str, object]", raw)
        path = str(entry.get("path", ""))
        digest = str(entry.get("sha256", ""))
        size = entry.get("size")
        if (
            not _DIGEST.fullmatch(digest)
            or path not in payloads
            or size != len(payloads[path])
            or digest != hashlib.sha256(payloads[path]).hexdigest()
        ):
            raise QualificationError(f"dataset manifest mismatch: {path}")
        declared.add(path)
    expected = {
        path
        for path in payloads
        if path not in {"SHA256SUMS", "package-manifest.json"}
    }
    if declared != expected:
        raise QualificationError("dataset manifest does not bind exact files")
    expected_sums = "".join(
        f"{hashlib.sha256(payloads[path]).hexdigest()}  {path}\n"
        for path in sorted(declared)
    )
    if checksum_bytes.decode() != expected_sums:
        raise QualificationError("dataset checksums disagree with its manifest")


def _stage_files(stage: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                item
                for item in stage.rglob("*")
                if item.is_file()
                and item.relative_to(stage).as_posix() not in _CONTROL_FILES
            ),
            key=lambda item: item.relative_to(stage).as_posix(),
        )
    )


def _write_asset_manifest(
    *,
    root: Path,
    stage: Path,
    payloads: tuple[Path, ...],
    release_tag: str,
    version: str,
    commit: str,
) -> tuple[Path, tuple[ImmutableArtifact, ...]]:
    entries = [
        {
            "path": item.relative_to(stage).as_posix(),
            "sha256": _sha256(item),
            "size": item.stat().st_size,
        }
        for item in payloads
    ]
    manifest = {
        "commit": commit,
        "project": PROJECT,
        "release_tag": release_tag,
        "version": version,
        "files": entries,
    }
    manifest_path = stage / "qualified-assets.json"
    manifest_path.write_bytes(_canonical_json(manifest))
    artifacts = tuple(
        ImmutableArtifact(
            path=item
            .resolve(strict=True)
            .relative_to(root.resolve(strict=True))
            .as_posix(),
            sha256=_sha256(item),
            size=item.stat().st_size,
        )
        for item in (*payloads, manifest_path)
    )
    return manifest_path, artifacts


def qualify_release_assets(
    *,
    root: Path,
    stage: Path,
    release_tag: str,
    commit: str,
    dynamic_version: str,
    include_dataset: bool = True,
) -> dict[str, object]:
    """Fail closed unless staged bytes form one coherent governed release."""

    version = _verify_tag(root, release_tag, commit)
    if dynamic_version != version:
        raise QualificationError("dynamic version and release tag disagree")
    if any((stage / name).exists() for name in _CONTROL_FILES):
        raise QualificationError("stage contains stale qualification controls")
    wheels = tuple(stage.glob("*.whl"))
    if len(wheels) != 1:
        raise QualificationError("stage must contain exactly one wheel")
    _, wheel_version = _wheel_metadata(wheels[0])
    if wheel_version != version:
        raise QualificationError("wheel and release tag versions disagree")
    lock_path = _contained(stage, "uv.lock")
    verify_runtime_sbom(
        root=root,
        sbom_path=_contained(stage, "sbom.cdx.json"),
        lock_path=lock_path,
        project_version=version,
    )
    if include_dataset:
        _verify_dataset_archive(stage, version)
    elif tuple(stage.glob(f"{PROJECT}-dataset-*.tar.gz")):
        raise QualificationError(
            "software-only stage must not contain a dataset archive"
        )

    payloads = _stage_files(stage)
    manifest_path, artifacts = _write_asset_manifest(
        root=root,
        stage=stage,
        payloads=payloads,
        release_tag=release_tag,
        version=version,
        commit=commit,
    )
    qualification = PrepublicationQualification(
        release_version=version,
        evidence_sha256=_sha256(manifest_path),
        qualified=True,
        artifact_sha256=tuple(
            sorted({artifact.sha256 for artifact in artifacts})
        ),
    )
    report = validate_release_metadata(
        root=root,
        release_version=release_tag,
        dynamic_version=dynamic_version,
        artifacts=artifacts,
        qualification=qualification,
    )
    if not report.qualified:
        codes = ", ".join(finding.code for finding in report.findings)
        raise QualificationError(f"release metadata is not qualified: {codes}")
    receipt: dict[str, object] = {
        "commit": commit,
        "dynamic_version": dynamic_version,
        "qualified": True,
        "qualified_assets_sha256": _sha256(manifest_path),
        "release_tag": release_tag,
        "version": version,
    }
    (stage / "qualification.json").write_bytes(_canonical_json(receipt))
    checksum_files = tuple(
        sorted(
            (item for item in stage.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(stage).as_posix(),
        )
    )
    lines = "".join(
        f"{_sha256(item)}  {item.relative_to(stage).as_posix()}\n"
        for item in checksum_files
    )
    (stage / "SHA256SUMS").write_text(lines, encoding="utf-8")
    return receipt


def qualify_fixture_assets(
    *,
    root: Path,
    stage: Path,
    contract_path: Path,
    qualification_path: Path,
) -> dict[str, object]:
    """Validate committed fixture bytes without qualifying a release."""

    contract = PublicationPackage.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    fixture_receipt = PublicationVerificationReceipt.model_validate_json(
        qualification_path.read_text(encoding="utf-8")
    )
    _require_fixture_only(contract, fixture_receipt, "dry-run")
    if not contract.contract_version.startswith("fixture-dry-run-"):
        raise QualificationError(
            "dry-run qualification requires fixture inputs"
        )
    if any((stage / name).exists() for name in _CONTROL_FILES):
        raise QualificationError("stage contains stale qualification controls")
    wheels = tuple(stage.glob("*.whl"))
    if len(wheels) != 1:
        raise QualificationError("stage must contain exactly one wheel")
    _, wheel_version = _wheel_metadata(wheels[0])
    verify_runtime_sbom(
        root=root,
        sbom_path=_contained(stage, "sbom.cdx.json"),
        lock_path=_contained(stage, "uv.lock"),
        project_version=wheel_version,
    )
    _verify_dataset_archive(stage, contract.dataset_card.version)
    payloads = _stage_files(stage)
    manifest_path, _ = _write_asset_manifest(
        root=root,
        stage=stage,
        payloads=payloads,
        release_tag="fixture-dry-run-only",
        version=wheel_version,
        commit=_git(root, "rev-parse", "HEAD"),
    )
    receipt: dict[str, object] = {
        "dry_run_validated": True,
        "fixture_only": True,
        "maintainer_approved": False,
        "production_release_qualified": False,
        "qualified_assets_sha256": _sha256(manifest_path),
    }
    (stage / "qualification.json").write_bytes(_canonical_json(receipt))
    checksum_files = tuple(
        sorted(
            (item for item in stage.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(stage).as_posix(),
        )
    )
    (stage / "SHA256SUMS").write_text(
        "".join(
            f"{_sha256(item)}  {item.relative_to(stage).as_posix()}\n"
            for item in checksum_files
        ),
        encoding="utf-8",
    )
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build-package")
    for name in ("root", "contract", "qualification", "rows", "output"):
        build.add_argument(f"--{name}", type=Path, required=True)
    build.add_argument(
        "--publication-mode",
        choices=("dry-run", "production"),
        required=True,
    )
    qualify = subparsers.add_parser("qualify")
    qualify.add_argument("--root", type=Path, required=True)
    qualify.add_argument("--stage", type=Path, required=True)
    qualify.add_argument("--release-tag", required=True)
    qualify.add_argument("--commit", required=True)
    qualify.add_argument("--dynamic-version", required=True)
    qualify.add_argument("--software-only", action="store_true")
    fixture = subparsers.add_parser("qualify-fixture")
    fixture.add_argument("--root", type=Path, required=True)
    fixture.add_argument("--stage", type=Path, required=True)
    fixture.add_argument("--contract", type=Path, required=True)
    fixture.add_argument("--qualification", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build-package":
        written = build_governed_package(
            root=args.root,
            contract_path=args.contract,
            qualification_path=args.qualification,
            rows_path=args.rows,
            output=args.output,
            publication_mode=args.publication_mode,
        )
        print(json.dumps({"generated": written}, sort_keys=True))
    elif args.command == "qualify":
        receipt = qualify_release_assets(
            root=args.root,
            stage=args.stage,
            release_tag=args.release_tag,
            commit=args.commit,
            dynamic_version=args.dynamic_version,
            include_dataset=not args.software_only,
        )
        print(json.dumps(receipt, sort_keys=True))
    else:
        receipt = qualify_fixture_assets(
            root=args.root,
            stage=args.stage,
            contract_path=args.contract,
            qualification_path=args.qualification,
        )
        print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
