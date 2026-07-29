"""Offline clean-room verification for governed publication artifacts."""

from __future__ import annotations

import hashlib
import json
import tempfile
import tomllib
import zipfile
from collections.abc import Mapping
from email.parser import Parser
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Literal, cast

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
RelativePath = Annotated[str, StringConstraints(min_length=1)]
SHA256_HEX_LENGTH = 64


class RehearsalError(ValueError):
    """Raised when clean-room verification fails closed."""


class DeclaredArtifact(BaseModel):
    """One immutable input admitted to the clean room."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: RelativePath
    role: Literal[
        "asset-manifest",
        "checksums",
        "package",
        "provenance-attestation",
        "qualification",
        "runtime-lock",
        "sbom",
    ]
    sha256: Digest
    size: int = Field(ge=0)


class RehearsalDeclaration(BaseModel):
    """Complete declaration of clean-room inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2"]
    expected_project: Annotated[str, StringConstraints(min_length=1)]
    expected_version: Annotated[str, StringConstraints(min_length=1)]
    trusted_builder_id: Annotated[str, StringConstraints(min_length=1)]
    artifacts: tuple[DeclaredArtifact, ...] = Field(min_length=7)


class VerifiedArtifact(BaseModel):
    """Content identity recorded in a durable receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: RelativePath
    role: str
    sha256: Digest
    size: int


class CleanRoomReceipt(BaseModel):
    """Deterministic result of an offline rehearsal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2"] = "2"
    declaration_sha256: Digest
    qualified_assets_sha256: Digest
    verified: Literal[True] = True
    network_accessed: Literal[False] = False
    published: Literal[False] = False
    artifacts: tuple[VerifiedArtifact, ...]


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        + "\n"
    ).encode()


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or value != path.as_posix()
        or ".." in path.parts
    ):
        raise RehearsalError(f"unsafe relative path: {value}")
    if any(part in {"", "."} for part in path.parts):
        raise RehearsalError(f"unsafe relative path: {value}")
    return path


def _load_object(path: Path, label: str) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RehearsalError(
            f"{label} is not readable canonical JSON"
        ) from error
    if not isinstance(value, dict):
        raise RehearsalError(f"{label} must be a JSON object")
    return cast("dict[str, object]", value)


def _copy_declared(
    source_root: Path,
    clean_root: Path,
    declaration: RehearsalDeclaration,
) -> dict[str, DeclaredArtifact]:
    resolved_root = source_root.resolve(strict=True)
    declared: dict[str, DeclaredArtifact] = {}
    roles: set[str] = set()
    for artifact in declaration.artifacts:
        relative = _relative(artifact.path)
        if artifact.path in declared:
            raise RehearsalError(f"duplicate declared path: {artifact.path}")
        if artifact.role in roles:
            raise RehearsalError(f"duplicate artifact role: {artifact.role}")
        source = source_root.joinpath(*relative.parts)
        if source.is_symlink():
            raise RehearsalError(
                f"symbolic links are forbidden: {artifact.path}"
            )
        try:
            resolved = source.resolve(strict=True)
        except OSError as error:
            raise RehearsalError(
                f"declared artifact is missing: {artifact.path}"
            ) from error
        if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
            raise RehearsalError(
                f"artifact escapes source root: {artifact.path}"
            )
        payload = resolved.read_bytes()
        if len(payload) != artifact.size or _digest(payload) != artifact.sha256:
            raise RehearsalError(f"declared identity mismatch: {artifact.path}")
        destination = clean_root.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        declared[artifact.path] = artifact
        roles.add(artifact.role)
    required = {
        "asset-manifest",
        "checksums",
        "package",
        "provenance-attestation",
        "qualification",
        "runtime-lock",
        "sbom",
    }
    if roles != required:
        raise RehearsalError(
            f"artifact roles must be exactly {sorted(required)}"
        )
    return declared


def _by_role(
    root: Path, declared: Mapping[str, DeclaredArtifact], role: str
) -> Path:
    path = next(item.path for item in declared.values() if item.role == role)
    return root.joinpath(*PurePosixPath(path).parts)


def _verify_checksums(
    root: Path, declared: Mapping[str, DeclaredArtifact], checksums: Path
) -> None:
    observed: dict[str, str] = {}
    try:
        lines = checksums.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise RehearsalError("checksum file is unreadable") from error
    for line in lines:
        digest, separator, path = line.partition("  ")
        if (
            not separator
            or len(digest) != SHA256_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise RehearsalError("checksum file has an invalid entry")
        _relative(path)
        if path in observed:
            raise RehearsalError(f"duplicate checksum entry: {path}")
        observed[path] = digest
    expected = {
        path
        for path, artifact in declared.items()
        if artifact.role != "checksums"
    }
    if set(observed) != expected:
        raise RehearsalError(
            "checksums must bind every non-checksum artifact exactly"
        )
    for path, digest in observed.items():
        payload = root.joinpath(*PurePosixPath(path).parts).read_bytes()
        if _digest(payload) != digest:
            raise RehearsalError(f"checksum mismatch: {path}")


def _verify_asset_manifest(
    root: Path, declared: Mapping[str, DeclaredArtifact], manifest_path: Path
) -> str:
    manifest = _load_object(manifest_path, "asset manifest")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise RehearsalError("asset manifest files must be a list")
    observed: dict[str, tuple[str, int]] = {}
    for raw in cast("list[object]", entries):
        if not isinstance(raw, dict):
            raise RehearsalError("asset manifest entry must be an object")
        entry = cast("dict[str, object]", raw)
        path, digest, size = (
            entry.get("path"),
            entry.get("sha256"),
            entry.get("size"),
        )
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or not isinstance(size, int)
        ):
            raise RehearsalError("asset manifest entry has invalid fields")
        _relative(path)
        if path in observed:
            raise RehearsalError(f"duplicate asset manifest entry: {path}")
        observed[path] = (digest, size)
    expected = {
        path
        for path, artifact in declared.items()
        if artifact.role not in {"asset-manifest", "checksums", "qualification"}
    }
    if set(observed) != expected:
        raise RehearsalError("asset manifest must bind exact governed payloads")
    for path, (digest, size) in observed.items():
        payload = root.joinpath(*PurePosixPath(path).parts).read_bytes()
        if digest != _digest(payload) or size != len(payload):
            raise RehearsalError(f"asset manifest identity mismatch: {path}")
    return _digest(manifest_path.read_bytes())


def _wheel_identity(path: Path) -> tuple[str, str, set[str]]:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise RehearsalError(
                    "package wheel must contain exactly one METADATA file"
                )
            message = Parser().parsestr(
                archive.read(metadata_names[0]).decode("utf-8")
            )
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as error:
        raise RehearsalError("package must be a readable wheel") from error
    name, version = message.get("Name"), message.get("Version")
    if not name or not version:
        raise RehearsalError("package metadata requires Name and Version")
    requirements: set[str] = set()
    for value in message.get_all("Requires-Dist", []):
        requirement = Requirement(value)
        marker = requirement.marker
        if marker is None or marker.evaluate():
            requirements.add(str(canonicalize_name(requirement.name)))
    return str(canonicalize_name(name)), version, requirements


def _index_lock_packages(
    packages: list[object],
) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for item in packages:
        if not isinstance(item, dict):
            raise RehearsalError("runtime lock package must be a table")
        package = cast("dict[str, object]", item)
        name, version = package.get("name"), package.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise RehearsalError(
                "runtime lock packages require name and version"
            )
        normalized = str(canonicalize_name(name))
        if normalized in indexed:
            raise RehearsalError("runtime lock package names must be unique")
        indexed[normalized] = package
    return indexed


def _lock_closure(
    path: Path, *, project: str, direct_requirements: set[str]
) -> set[tuple[str, str]]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise RehearsalError("runtime lock is not valid TOML") from error
    packages = cast("dict[str, object]", raw).get("package")
    if not isinstance(packages, list):
        raise RehearsalError("runtime lock must contain package records")
    indexed = _index_lock_packages(cast("list[object]", packages))
    root = indexed.get(project)
    if root is None:
        raise RehearsalError("runtime lock lacks the expected project")
    root_dependencies = root.get("dependencies", [])
    if not isinstance(root_dependencies, list):
        raise RehearsalError("project lock dependencies must be a list")

    def dependency_names(values: list[object]) -> set[str]:
        names: set[str] = set()
        for value in values:
            if not isinstance(value, dict) or not isinstance(
                cast("dict[str, object]", value).get("name"), str
            ):
                raise RehearsalError("locked dependency requires a name")
            names.add(
                str(
                    canonicalize_name(
                        cast("str", cast("dict[str, object]", value)["name"])
                    )
                )
            )
        return names

    if (
        dependency_names(cast("list[object]", root_dependencies))
        != direct_requirements
    ):
        raise RehearsalError("wheel requirements disagree with runtime lock")
    closure: set[tuple[str, str]] = set()
    pending = list(direct_requirements)
    while pending:
        name = pending.pop()
        package = indexed.get(name)
        if package is None:
            raise RehearsalError(f"runtime dependency is not locked: {name}")
        version = cast("str", package["version"])
        if (name, version) in closure:
            continue
        closure.add((name, version))
        dependencies = package.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise RehearsalError("locked dependencies must be a list")
        pending.extend(dependency_names(cast("list[object]", dependencies)))
    return closure


def _verify_sbom(
    path: Path,
    *,
    project: str,
    version: str,
    runtime_closure: set[tuple[str, str]],
) -> None:
    sbom = _load_object(path, "SBOM")
    if sbom.get("bomFormat") != "CycloneDX":
        raise RehearsalError("SBOM must use CycloneDX")
    if not isinstance(sbom.get("specVersion"), str):
        raise RehearsalError("SBOM must declare a CycloneDX specVersion")
    metadata = sbom.get("metadata")
    if not isinstance(metadata, dict):
        raise RehearsalError("SBOM must contain project metadata")
    root_component = cast("dict[str, object]", metadata).get("component")
    if not isinstance(root_component, dict):
        raise RehearsalError("SBOM must identify the project component")
    root_fields = cast("dict[str, object]", root_component)
    if (
        canonicalize_name(str(root_fields.get("name", ""))) != project
        or root_fields.get("version") != version
    ):
        raise RehearsalError("SBOM project identity disagrees with package")
    components = sbom.get("components")
    if not isinstance(components, list) or not components:
        raise RehearsalError("SBOM must contain components")
    observed: set[tuple[str, str]] = set()
    for component in cast("list[object]", components):
        if not isinstance(component, dict):
            raise RehearsalError("SBOM component must be an object")
        fields = cast("dict[str, object]", component)
        name, component_version = fields.get("name"), fields.get("version")
        if not isinstance(name, str) or not isinstance(component_version, str):
            raise RehearsalError("SBOM components require name and version")
        identity = (canonicalize_name(name), component_version)
        if identity in observed:
            raise RehearsalError("SBOM component identities must be unique")
        observed.add(identity)
    if observed != runtime_closure:
        raise RehearsalError(
            "SBOM does not match the exact runtime lock closure"
        )


def _verify_attestation(
    path: Path,
    *,
    root: Path,
    declared: Mapping[str, DeclaredArtifact],
    trusted_builder_id: str,
) -> None:
    statement = _load_object(path, "provenance attestation")
    if statement.get("_type") != "https://in-toto.io/Statement/v1":
        raise RehearsalError("attestation must be an in-toto v1 statement")
    if statement.get("predicateType") != "https://slsa.dev/provenance/v1":
        raise RehearsalError("attestation must use SLSA provenance v1")
    predicate = statement.get("predicate")
    if not isinstance(predicate, dict):
        raise RehearsalError("attestation predicate must be an object")
    builder = cast("dict[str, object]", predicate).get("builder")
    if (
        not isinstance(builder, dict)
        or cast("dict[str, object]", builder).get("id") != trusted_builder_id
    ):
        raise RehearsalError("attestation builder identity is not trusted")
    subjects = statement.get("subject")
    if not isinstance(subjects, list):
        raise RehearsalError("attestation subjects must be a list")
    observed: dict[str, str] = {}
    for item in cast("list[object]", subjects):
        if not isinstance(item, dict):
            raise RehearsalError("attestation subject must be an object")
        subject = cast("dict[str, object]", item)
        name, digest = subject.get("name"), subject.get("digest")
        if not isinstance(name, str) or not isinstance(digest, dict):
            raise RehearsalError("attestation subject is malformed")
        sha256 = cast("dict[str, object]", digest).get("sha256")
        if not isinstance(sha256, str) or name in observed:
            raise RehearsalError("attestation subject digest is invalid")
        observed[name] = sha256
    expected = {
        item.path: _digest(
            root.joinpath(*PurePosixPath(item.path).parts).read_bytes()
        )
        for item in declared.values()
        if item.role in {"package", "runtime-lock", "sbom"}
    }
    if observed != expected:
        raise RehearsalError(
            "attestation subjects do not match exact governed bytes"
        )


def _verify_qualification(path: Path, manifest_digest: str) -> None:
    receipt = _load_object(path, "qualification receipt")
    qualified = receipt.get("qualified") is True
    dry_run = receipt.get("dry_run_validated") is True
    if not (qualified or dry_run):
        raise RehearsalError("qualification receipt is not successful")
    if receipt.get("qualified_assets_sha256") != manifest_digest:
        raise RehearsalError(
            "qualification receipt is not bound to asset manifest"
        )
    if receipt.get("published") is True:
        raise RehearsalError(
            "clean-room rehearsal rejects publication receipts"
        )


def rehearse_publication(
    *,
    source_root: Path,
    declaration_path: Path,
    receipt_path: Path,
) -> CleanRoomReceipt:
    """Verify declared publication bytes offline in an isolated directory."""

    declaration_bytes = declaration_path.read_bytes()
    declaration = RehearsalDeclaration.model_validate_json(declaration_bytes)
    output = receipt_path.resolve()
    source = source_root.resolve(strict=True)
    if output.is_relative_to(source):
        raise RehearsalError(
            "durable receipt must be outside the governed source root"
        )
    with tempfile.TemporaryDirectory(prefix="gma-clean-room-") as temporary:
        clean_root = Path(temporary)
        declared = _copy_declared(source, clean_root, declaration)
        _verify_checksums(
            clean_root, declared, _by_role(clean_root, declared, "checksums")
        )
        manifest_digest = _verify_asset_manifest(
            clean_root,
            declared,
            _by_role(clean_root, declared, "asset-manifest"),
        )
        package_project, package_version, requirements = _wheel_identity(
            _by_role(clean_root, declared, "package")
        )
        expected_project = canonicalize_name(declaration.expected_project)
        if (
            package_project != expected_project
            or package_version != declaration.expected_version
        ):
            raise RehearsalError(
                "package project or version disagrees with declaration"
            )
        runtime_closure = _lock_closure(
            _by_role(clean_root, declared, "runtime-lock"),
            project=expected_project,
            direct_requirements=requirements,
        )
        _verify_sbom(
            _by_role(clean_root, declared, "sbom"),
            project=expected_project,
            version=package_version,
            runtime_closure=runtime_closure,
        )
        _verify_attestation(
            _by_role(clean_root, declared, "provenance-attestation"),
            root=clean_root,
            declared=declared,
            trusted_builder_id=declaration.trusted_builder_id,
        )
        _verify_qualification(
            _by_role(clean_root, declared, "qualification"), manifest_digest
        )
        verified = tuple(
            VerifiedArtifact(
                path=item.path,
                role=item.role,
                sha256=item.sha256,
                size=item.size,
            )
            for item in sorted(declared.values(), key=lambda value: value.path)
        )
        receipt = CleanRoomReceipt(
            declaration_sha256=_digest(declaration_bytes),
            qualified_assets_sha256=manifest_digest,
            artifacts=verified,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical_json(receipt.model_dump(mode="json")))
    return receipt
