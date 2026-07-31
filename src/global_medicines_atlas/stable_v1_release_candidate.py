"""Deterministic, fail-closed stable-v1 release-candidate contracts."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tarfile
import zipfile
from collections import Counter
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from pydantic import Field, field_validator, model_validator

from .models import FrozenModel
from .release_metadata import ImmutableArtifact

RELEASE_CANDIDATE_SCHEMA_ID = (
    "global-medicines-atlas.stable-v1-release-candidate"
)
RELEASE_CANDIDATE_SCHEMA_VERSION = 1
PROJECT_NAME = "global-medicines-atlas"
MANIFEST_PATH = "candidate-manifest.json"
CHECKSUMS_PATH = "SHA256SUMS"
PROVENANCE_PATH = "provenance-references.json"
SBOM_PATH = "sbom.cdx.json"
LOCK_PATH = "uv.lock"
GUIDE_PATH = "VERIFY.md"

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_ARTIFACT_ROLES = frozenset({
    "wheel",
    "sdist",
    "sbom",
    "dependency-lock",
    "provenance-references",
    "verification-guide",
})
_REQUIRED_REFERENCE_ROLES = frozenset({
    "candidate-implementation",
    "candidate-schema",
    "candidate-script",
    "consumer-contract",
    "consumer-qualification",
    "dependency-lock",
    "interoperability-lock",
    "release-evidence-schema",
    "release-workflow",
    "source-commit-object",
    "source-tree-listing",
})
_REQUIRED_COMMANDS = frozenset({
    "verify-candidate",
    "install-wheel",
    "install-sdist",
    "probe-installed-version",
})
_FORBIDDEN_COMMAND_FRAGMENTS = (
    "actions/attest",
    "cosign sign",
    "gh release",
    "git tag",
    "sigstore sign",
    "twine upload",
    "uv publish",
)


class ReleaseCandidateError(ValueError):
    """A candidate package or receipt failed closed."""


class ArtifactRole(StrEnum):
    """Exact role of a file in the candidate package."""

    WHEEL = "wheel"
    SDIST = "sdist"
    SBOM = "sbom"
    DEPENDENCY_LOCK = "dependency-lock"
    PROVENANCE_REFERENCES = "provenance-references"
    VERIFICATION_GUIDE = "verification-guide"


class ReferenceKind(StrEnum):
    """How a content-bound provenance reference is resolved."""

    REPOSITORY_FILE = "repository-file"
    GIT_COMMIT_OBJECT = "git-commit-object"
    GIT_TREE_LISTING = "git-tree-listing"


def _safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("path must be a safe repository-relative POSIX path")
    return value


class CandidateArtifact(ImmutableArtifact):
    """Content identity and semantic role of one candidate file."""

    role: ArtifactRole
    media_type: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def path_is_safe(cls, value: str) -> str:
        return _safe_path(value)


class ProvenanceReference(FrozenModel):
    """Immutable source or policy input used to construct the candidate."""

    role: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    kind: ReferenceKind
    locator: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def locator_matches_kind(self) -> ProvenanceReference:
        if self.kind is ReferenceKind.REPOSITORY_FILE:
            if not self.locator.startswith("repo:"):
                raise ValueError(
                    "repository-file locator must start with repo:"
                )
            _safe_path(self.locator.removeprefix("repo:"))
        elif self.kind is ReferenceKind.GIT_COMMIT_OBJECT:
            if not self.locator.startswith("git:commit:"):
                raise ValueError("commit locator must start with git:commit:")
            if not _COMMIT.fullmatch(self.locator.removeprefix("git:commit:")):
                raise ValueError("commit locator must contain a full Git SHA")
        elif not self.locator.startswith("git:tree-listing:"):
            raise ValueError(
                "tree-listing locator must start with git:tree-listing:"
            )
        return self


class VerificationCommand(FrozenModel):
    """One copy-and-run consumer verification command."""

    command_id: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    argv: tuple[str, ...] = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    mutates_external_state: Literal[False] = False

    @model_validator(mode="after")
    def command_is_local_and_non_publishing(self) -> VerificationCommand:
        rendered = " ".join(self.argv).casefold()
        if any(value in rendered for value in _FORBIDDEN_COMMAND_FRAGMENTS):
            raise ValueError(
                "verification command may not publish, tag, or sign"
            )
        return self


class CandidateState(FrozenModel):
    """Authority boundary for the pre-release candidate."""

    status: Literal["unsigned-unapproved-not-published"] = (
        "unsigned-unapproved-not-published"
    )
    signed: Literal[False] = False
    approved: Literal[False] = False
    published: Literal[False] = False
    provenance_attested: Literal[False] = False
    git_tag_created: Literal[False] = False
    github_release_created: Literal[False] = False


class CandidateManifest(FrozenModel):
    """Deterministic inventory of candidate package payloads."""

    schema_version: Literal[1] = 1
    project: Literal["global-medicines-atlas"] = PROJECT_NAME
    candidate_id: str = Field(pattern=r"^stable-v1-rc-[0-9a-f]{12}$")
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    package_version: str = Field(min_length=1)
    files: tuple[CandidateArtifact, ...] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def artifact_set_is_exact(self) -> CandidateManifest:
        paths = tuple(item.path for item in self.files)
        roles = tuple(item.role.value for item in self.files)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError(
                "candidate artifacts must have unique sorted paths"
            )
        if set(roles) != set(_REQUIRED_ARTIFACT_ROLES):
            raise ValueError("candidate artifact roles are incomplete")
        if any(count != 1 for count in Counter(roles).values()):
            raise ValueError("candidate artifact roles must be unique")
        return self


class StableV1ReleaseCandidateReceipt(FrozenModel):
    """Content-bound receipt for a local, non-authoritative candidate."""

    schema_id: Literal["global-medicines-atlas.stable-v1-release-candidate"] = (
        RELEASE_CANDIDATE_SCHEMA_ID
    )
    schema_version: Literal[1] = RELEASE_CANDIDATE_SCHEMA_VERSION
    candidate_id: str = Field(pattern=r"^stable-v1-rc-[0-9a-f]{12}$")
    source_repository: Literal[
        "https://github.com/edithatogo/global-medicines-atlas"
    ] = "https://github.com/edithatogo/global-medicines-atlas"
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    package_version: str = Field(min_length=1)
    artifacts: tuple[CandidateArtifact, ...] = Field(min_length=6, max_length=6)
    manifest: ImmutableArtifact
    checksums: ImmutableArtifact
    provenance_references: tuple[ProvenanceReference, ...] = Field(
        min_length=11, max_length=11
    )
    verification_commands: tuple[VerificationCommand, ...] = Field(
        min_length=4, max_length=4
    )
    state: CandidateState = Field(default_factory=CandidateState)
    limitations: tuple[str, ...] = Field(min_length=4)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_is_complete_and_content_bound(
        self,
    ) -> StableV1ReleaseCandidateReceipt:
        artifact_paths = tuple(item.path for item in self.artifacts)
        if artifact_paths != tuple(sorted(artifact_paths)):
            raise ValueError("receipt artifacts must be sorted")
        if {item.role.value for item in self.artifacts} != set(
            _REQUIRED_ARTIFACT_ROLES
        ):
            raise ValueError("receipt artifact roles are incomplete")
        reference_roles = tuple(
            item.role for item in self.provenance_references
        )
        if reference_roles != tuple(sorted(reference_roles)):
            raise ValueError("provenance references must be sorted")
        if set(reference_roles) != set(_REQUIRED_REFERENCE_ROLES):
            raise ValueError("provenance references are incomplete")
        command_ids = tuple(
            item.command_id for item in self.verification_commands
        )
        if command_ids != tuple(sorted(command_ids)):
            raise ValueError("verification commands must be sorted")
        if set(command_ids) != set(_REQUIRED_COMMANDS):
            raise ValueError("verification commands are incomplete")
        if self.manifest.path != MANIFEST_PATH:
            raise ValueError("manifest path is not canonical")
        if self.checksums.path != CHECKSUMS_PATH:
            raise ValueError("checksums path is not canonical")
        if self.content_sha256 != self.expected_content_sha256():
            raise ValueError("release-candidate receipt digest is invalid")
        return self

    def expected_content_sha256(self) -> str:
        """Return the digest over all receipt fields except the digest itself."""
        payload = self.model_dump(mode="json", exclude={"content_sha256"})
        return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()

    def canonical_bytes(self) -> bytes:
        """Return deterministic receipt bytes."""
        return canonical_json_bytes(self.model_dump(mode="json"))


def canonical_json_bytes(value: object) -> bytes:
    """Encode JSON using the repository's deterministic representation."""
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        + "\n"
    ).encode()


def sha256_file(path: Path) -> str:
    """Hash a regular file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def immutable_artifact(root: Path, path: Path) -> ImmutableArtifact:
    """Describe a file relative to a controlled root."""
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(resolved_root).as_posix()
    except ValueError as error:
        raise ReleaseCandidateError(
            "artifact escapes candidate stage"
        ) from error
    if path.is_symlink() or not resolved.is_file():
        raise ReleaseCandidateError("candidate artifacts must be regular files")
    return ImmutableArtifact(
        path=relative,
        sha256=sha256_file(resolved),
        size=resolved.stat().st_size,
    )


def candidate_artifact(
    root: Path,
    path: Path,
    *,
    role: ArtifactRole,
    media_type: str,
) -> CandidateArtifact:
    """Describe one candidate payload with its required role."""
    identity = immutable_artifact(root, path)
    return CandidateArtifact(
        **identity.model_dump(), role=role, media_type=media_type
    )


def _metadata_fields(lines: Iterable[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition(":")
        if separator and key in {"Name", "Version"}:
            fields[key] = value.strip()
    return fields


def _wheel_identity(path: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(names) != 1:
                raise ReleaseCandidateError(
                    "wheel must contain exactly one METADATA file"
                )
            fields = _metadata_fields(
                archive.read(names[0]).decode().splitlines()
            )
    except (OSError, UnicodeError, zipfile.BadZipFile) as error:
        raise ReleaseCandidateError("wheel metadata is unreadable") from error
    return fields.get("Name", ""), fields.get("Version", "")


def _read_sdist_metadata(archive: tarfile.TarFile) -> dict[str, str]:
    members = [
        member
        for member in archive.getmembers()
        if member.isfile() and member.name.endswith("/PKG-INFO")
    ]
    if len(members) != 1:
        raise ReleaseCandidateError(
            "sdist must contain exactly one PKG-INFO file"
        )
    stream = archive.extractfile(members[0])
    if stream is None:
        raise ReleaseCandidateError("sdist PKG-INFO is unreadable")
    return _metadata_fields(stream.read().decode().splitlines())


def _sdist_identity(path: Path) -> tuple[str, str]:
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            fields = _read_sdist_metadata(archive)
    except (OSError, UnicodeError, tarfile.TarError) as error:
        raise ReleaseCandidateError("sdist metadata is unreadable") from error
    return fields.get("Name", ""), fields.get("Version", "")


def _normalized_project(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).casefold()


def _verify_distribution_identities(
    stage: Path,
    artifacts: Iterable[CandidateArtifact],
    version: str,
) -> None:
    by_role = {item.role: item for item in artifacts}
    wheel = stage.joinpath(
        *PurePosixPath(by_role[ArtifactRole.WHEEL].path).parts
    )
    sdist = stage.joinpath(
        *PurePosixPath(by_role[ArtifactRole.SDIST].path).parts
    )
    for name, observed_version in (
        _wheel_identity(wheel),
        _sdist_identity(sdist),
    ):
        if _normalized_project(name) != PROJECT_NAME:
            raise ReleaseCandidateError(
                "distribution project identity is invalid"
            )
        if observed_version != version:
            raise ReleaseCandidateError("distribution versions disagree")


def _verify_sbom(
    stage: Path, artifacts: Iterable[CandidateArtifact], version: str
) -> None:
    sbom_artifact = next(
        item for item in artifacts if item.role is ArtifactRole.SBOM
    )
    path = stage.joinpath(*PurePosixPath(sbom_artifact.path).parts)
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseCandidateError("SBOM is not readable JSON") from error
    if not isinstance(raw, dict):
        raise ReleaseCandidateError("SBOM must be CycloneDX JSON")
    sbom = cast("dict[str, object]", raw)
    if sbom.get("bomFormat") != "CycloneDX":
        raise ReleaseCandidateError("SBOM must be CycloneDX JSON")
    raw_metadata = sbom.get("metadata")
    if not isinstance(raw_metadata, dict):
        raise ReleaseCandidateError("SBOM lacks project metadata")
    metadata = cast("dict[str, object]", raw_metadata)
    raw_component = metadata.get("component")
    if not isinstance(raw_component, dict):
        raise ReleaseCandidateError("SBOM lacks project metadata")
    component = cast("dict[str, object]", raw_component)
    name = component.get("name")
    observed_version = component.get("version")
    if (
        not isinstance(name, str)
        or _normalized_project(name) != PROJECT_NAME
        or observed_version != version
    ):
        raise ReleaseCandidateError("SBOM project identity is invalid")
    if "serialNumber" in sbom or "timestamp" in metadata:
        raise ReleaseCandidateError(
            "SBOM contains nondeterministic identity fields"
        )


def _parse_checksums(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator or not _DIGEST.fullmatch(digest) or relative in values:
            raise ReleaseCandidateError("SHA256SUMS is not canonical")
        try:
            _safe_path(relative)
        except ValueError as error:
            raise ReleaseCandidateError(
                "SHA256SUMS is not canonical"
            ) from error
        values[relative] = digest
    return values


def _git_bytes(root: Path, *arguments: str) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise ReleaseCandidateError("Git provenance is unavailable")
    try:
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [git, "-C", str(root.resolve()), *arguments],
            check=True,
            capture_output=True,
            shell=False,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseCandidateError("Git provenance is unavailable") from error
    return result.stdout


def provenance_reference_bytes(
    root: Path,
    reference: ProvenanceReference,
    source_commit: str,
) -> bytes:
    """Resolve exact bytes for one declared provenance reference."""
    if reference.kind is ReferenceKind.REPOSITORY_FILE:
        relative = reference.locator.removeprefix("repo:")
        return _git_bytes(root, "show", f"{source_commit}:{relative}")
    if reference.kind is ReferenceKind.GIT_COMMIT_OBJECT:
        commit = reference.locator.removeprefix("git:commit:")
        if commit != source_commit:
            raise ReleaseCandidateError(
                "commit reference targets another commit"
            )
        return _git_bytes(root, "cat-file", "commit", commit)
    commit = reference.locator.removeprefix("git:tree-listing:")
    if commit != source_commit:
        raise ReleaseCandidateError("tree reference targets another commit")
    return _git_bytes(root, "ls-tree", "-r", "--full-tree", commit)


def build_receipt(
    *,
    candidate_id: str,
    source_commit: str,
    source_tree: str,
    package_version: str,
    artifacts: tuple[CandidateArtifact, ...],
    manifest: ImmutableArtifact,
    checksums: ImmutableArtifact,
    provenance_references: tuple[ProvenanceReference, ...],
    verification_commands: tuple[VerificationCommand, ...],
    limitations: tuple[str, ...],
) -> StableV1ReleaseCandidateReceipt:
    """Create a receipt whose digest covers every candidate assertion."""
    provisional = StableV1ReleaseCandidateReceipt.model_construct(
        candidate_id=candidate_id,
        source_commit=source_commit,
        source_tree=source_tree,
        package_version=package_version,
        artifacts=artifacts,
        manifest=manifest,
        checksums=checksums,
        provenance_references=provenance_references,
        verification_commands=verification_commands,
        state=CandidateState(),
        limitations=limitations,
        content_sha256="0" * 64,
    )
    payload = provisional.model_dump(mode="json")
    payload["content_sha256"] = provisional.expected_content_sha256()
    return StableV1ReleaseCandidateReceipt.model_validate(payload)


def _verify_controls(
    stage: Path, receipt: StableV1ReleaseCandidateReceipt
) -> set[str]:
    manifest_path = stage / MANIFEST_PATH
    checksums_path = stage / CHECKSUMS_PATH
    if immutable_artifact(stage, manifest_path) != receipt.manifest:
        raise ReleaseCandidateError("manifest identity does not match receipt")
    if immutable_artifact(stage, checksums_path) != receipt.checksums:
        raise ReleaseCandidateError("checksum identity does not match receipt")
    try:
        manifest = CandidateManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise ReleaseCandidateError("candidate manifest is invalid") from error
    if manifest.candidate_id != receipt.candidate_id:
        raise ReleaseCandidateError("manifest candidate identity disagrees")
    if manifest.source_commit != receipt.source_commit:
        raise ReleaseCandidateError("manifest source commit disagrees")
    if manifest.source_tree != receipt.source_tree:
        raise ReleaseCandidateError("manifest source tree disagrees")
    if manifest.package_version != receipt.package_version:
        raise ReleaseCandidateError("manifest package version disagrees")
    if manifest.files != receipt.artifacts:
        raise ReleaseCandidateError("manifest artifacts disagree with receipt")
    return {item.path for item in receipt.artifacts} | {
        MANIFEST_PATH,
        CHECKSUMS_PATH,
    }


def _verify_payloads(
    stage: Path,
    receipt: StableV1ReleaseCandidateReceipt,
    expected_files: set[str],
) -> None:
    observed_files = {
        item.relative_to(stage).as_posix()
        for item in stage.rglob("*")
        if item.is_file()
    }
    if observed_files != expected_files:
        raise ReleaseCandidateError(
            "candidate stage contains an unexpected file set"
        )
    if any(item.is_symlink() for item in stage.rglob("*")):
        raise ReleaseCandidateError("candidate stage may not contain symlinks")
    for artifact in receipt.artifacts:
        path = stage.joinpath(*PurePosixPath(artifact.path).parts)
        if immutable_artifact(stage, path).model_dump() != artifact.model_dump(
            exclude={"role", "media_type"}
        ):
            raise ReleaseCandidateError(
                f"candidate artifact identity mismatch: {artifact.path}"
            )

    checksums = _parse_checksums(stage / CHECKSUMS_PATH)
    checksum_targets = expected_files - {CHECKSUMS_PATH}
    if set(checksums) != checksum_targets:
        raise ReleaseCandidateError(
            "SHA256SUMS does not bind the exact package"
        )
    for relative, digest in checksums.items():
        if (
            sha256_file(stage.joinpath(*PurePosixPath(relative).parts))
            != digest
        ):
            raise ReleaseCandidateError(f"checksum mismatch: {relative}")

    _verify_distribution_identities(
        stage, receipt.artifacts, receipt.package_version
    )
    _verify_sbom(stage, receipt.artifacts, receipt.package_version)


def _verify_provenance(
    root: Path, stage: Path, receipt: StableV1ReleaseCandidateReceipt
) -> None:
    provenance_artifact = next(
        item
        for item in receipt.artifacts
        if item.role is ArtifactRole.PROVENANCE_REFERENCES
    )
    raw_references = json.loads(
        stage.joinpath(
            *PurePosixPath(provenance_artifact.path).parts
        ).read_text(encoding="utf-8")
    )
    references = tuple(
        ProvenanceReference.model_validate(item) for item in raw_references
    )
    if references != receipt.provenance_references:
        raise ReleaseCandidateError("provenance-reference file disagrees")
    for reference in references:
        actual = hashlib.sha256(
            provenance_reference_bytes(root, reference, receipt.source_commit)
        ).hexdigest()
        if actual != reference.sha256:
            raise ReleaseCandidateError(
                f"provenance reference changed: {reference.role}"
            )

    observed_tree = (
        _git_bytes(root, "rev-parse", f"{receipt.source_commit}^{{tree}}")
        .decode()
        .strip()
    )
    if observed_tree != receipt.source_tree:
        raise ReleaseCandidateError("source tree does not match source commit")


def verify_candidate_package(
    *, root: Path, stage: Path, receipt: StableV1ReleaseCandidateReceipt
) -> None:
    """Verify the exact local package and repository provenance fail closed."""
    if receipt.content_sha256 != receipt.expected_content_sha256():
        raise ReleaseCandidateError("receipt digest is invalid")
    try:
        resolved_stage = stage.resolve(strict=True)
    except OSError as error:
        raise ReleaseCandidateError("candidate stage is unavailable") from error
    if not resolved_stage.is_dir():
        raise ReleaseCandidateError("candidate stage must be a directory")
    expected_files = _verify_controls(resolved_stage, receipt)
    _verify_payloads(resolved_stage, receipt, expected_files)
    _verify_provenance(root, resolved_stage, receipt)


def write_manifest_and_checksums(
    *,
    stage: Path,
    candidate_id: str,
    source_commit: str,
    source_tree: str,
    package_version: str,
    artifacts: tuple[CandidateArtifact, ...],
) -> tuple[ImmutableArtifact, ImmutableArtifact]:
    """Write deterministic package controls for an already staged payload."""
    if (stage / MANIFEST_PATH).exists() or (stage / CHECKSUMS_PATH).exists():
        raise ReleaseCandidateError("candidate controls already exist")
    manifest = CandidateManifest(
        candidate_id=candidate_id,
        source_commit=source_commit,
        source_tree=source_tree,
        package_version=package_version,
        files=artifacts,
    )
    manifest_path = stage / MANIFEST_PATH
    manifest_path.write_bytes(
        canonical_json_bytes(manifest.model_dump(mode="json"))
    )
    checksum_paths = [
        stage.joinpath(*PurePosixPath(item.path).parts) for item in artifacts
    ] + [manifest_path]
    checksums_path = stage / CHECKSUMS_PATH
    checksums_path.write_text(
        "".join(
            f"{sha256_file(path)}  {path.relative_to(stage).as_posix()}\n"
            for path in sorted(
                checksum_paths,
                key=lambda item: item.relative_to(stage).as_posix(),
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    return (
        immutable_artifact(stage, manifest_path),
        immutable_artifact(stage, checksums_path),
    )


def reference_payload(
    references: Iterable[ProvenanceReference],
) -> bytes:
    """Serialize sorted provenance references for the candidate package."""
    items = tuple(sorted(references, key=lambda item: item.role))
    roles = tuple(item.role for item in items)
    if set(roles) != set(_REQUIRED_REFERENCE_ROLES) or len(roles) != len(
        set(roles)
    ):
        raise ReleaseCandidateError("provenance reference roles are incomplete")
    return canonical_json_bytes([
        item.model_dump(mode="json") for item in items
    ])


def receipt_from_json(path: Path) -> StableV1ReleaseCandidateReceipt:
    """Load and validate a release-candidate receipt."""
    try:
        return StableV1ReleaseCandidateReceipt.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise ReleaseCandidateError(
            "release-candidate receipt is invalid"
        ) from error
