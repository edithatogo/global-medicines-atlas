"""Offline clean-room verification for governed publication artifacts."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Literal, cast

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
        "asset-manifest", "checksums", "package", "qualification", "sbom"
    ]
    sha256: Digest
    size: int = Field(ge=0)


class RehearsalDeclaration(BaseModel):
    """Complete declaration of clean-room inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"]
    artifacts: tuple[DeclaredArtifact, ...] = Field(min_length=4)


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

    schema_version: Literal["1"] = "1"
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
        "qualification",
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


def _verify_sbom(path: Path) -> None:
    sbom = _load_object(path, "SBOM")
    if sbom.get("bomFormat") != "CycloneDX":
        raise RehearsalError("SBOM must use CycloneDX")
    if not isinstance(sbom.get("specVersion"), str):
        raise RehearsalError("SBOM must declare a CycloneDX specVersion")
    components = sbom.get("components")
    if not isinstance(components, list) or not components:
        raise RehearsalError("SBOM must contain components")
    for component in cast("list[object]", components):
        if not isinstance(component, dict):
            raise RehearsalError("SBOM component must be an object")
        fields = cast("dict[str, object]", component)
        if not isinstance(fields.get("name"), str) or not isinstance(
            fields.get("version"), str
        ):
            raise RehearsalError("SBOM components require name and version")


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
        _verify_sbom(_by_role(clean_root, declared, "sbom"))
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
