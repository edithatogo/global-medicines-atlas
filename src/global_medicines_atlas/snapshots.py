"""Deterministic, fixture-only snapshot qualification manifests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenModel

MANIFEST_SCHEMA_ID = "global-medicines-atlas.snapshot-lineage"
MANIFEST_SCHEMA_VERSION = 1
FIXTURE_EVIDENCE_LABEL = "fixture_only_not_live_evidence"
FORBIDDEN_PATH_PARTS = frozenset({
    ".env",
    ".git",
    ".ssh",
    "credential",
    "credentials",
    "ignored",
    "private",
    "restricted",
    "secret",
    "secrets",
})


class SnapshotArtifact(FrozenModel):
    """A content-addressed fixture artifact."""

    role: Literal["input", "output"]
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class TransformationLineage(FrozenModel):
    """Reproducible transformation identity."""

    command: tuple[str, ...] = Field(min_length=1)
    package_commit: str = Field(min_length=1)


class SnapshotManifest(FrozenModel):
    """Qualification receipt that makes its fixture-only scope explicit."""

    schema_id: Literal["global-medicines-atlas.snapshot-lineage"] = (
        MANIFEST_SCHEMA_ID
    )
    schema_version: Literal[1] = MANIFEST_SCHEMA_VERSION
    qualification_scope: Literal["fixture_only_not_live_evidence"] = (
        FIXTURE_EVIDENCE_LABEL
    )
    dataset_schema_id: str = Field(min_length=1)
    dataset_schema_version: str = Field(min_length=1)
    source_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    transformation: TransformationLineage
    artifacts: tuple[SnapshotArtifact, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def artifact_paths_are_unique(self) -> SnapshotManifest:
        identities = [
            (artifact.role, artifact.path) for artifact in self.artifacts
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Snapshot artifact role/path pairs must be unique")
        if not any(artifact.role == "input" for artifact in self.artifacts):
            raise ValueError("Snapshot manifest requires at least one input")
        if not any(artifact.role == "output" for artifact in self.artifacts):
            raise ValueError("Snapshot manifest requires at least one output")
        return self


def sha256_file(path: Path) -> str:
    """Return the SHA256 digest of a regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(manifest: SnapshotManifest) -> bytes:
    """Serialize a manifest to stable UTF-8 JSON."""
    payload = manifest.model_dump(mode="json")
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _qualified_artifact(
    path: Path,
    *,
    fixture_root: Path,
    role: Literal["input", "output"],
) -> SnapshotArtifact:
    root = fixture_root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if path.is_symlink():
        raise ValueError(f"Symlinked fixture artifacts are forbidden: {path}")
    if not resolved.is_file():
        raise ValueError(f"Snapshot artifact must be a regular file: {path}")
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(
            f"Artifact is outside the fixture root: {path}"
        ) from error
    normalized = PurePosixPath(relative.as_posix())
    forbidden = {
        part.casefold()
        for part in normalized.parts
        if part.casefold() in FORBIDDEN_PATH_PARTS
        or part.casefold().startswith(".env")
    }
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise ValueError(f"Artifact path contains forbidden segments: {names}")
    return SnapshotArtifact(
        role=role,
        path=normalized.as_posix(),
        sha256=sha256_file(resolved),
        size_bytes=resolved.stat().st_size,
    )


def build_fixture_snapshot_manifest(
    *,
    fixture_root: Path,
    input_paths: Iterable[Path],
    output_paths: Iterable[Path],
    source_catalog_path: Path,
    dataset_schema_id: str,
    dataset_schema_version: str,
    transformation_command: Iterable[str],
    package_commit: str,
) -> SnapshotManifest:
    """Build a deterministic qualification manifest for local fixtures only."""
    artifacts = [
        *(
            _qualified_artifact(path, fixture_root=fixture_root, role="input")
            for path in input_paths
        ),
        *(
            _qualified_artifact(path, fixture_root=fixture_root, role="output")
            for path in output_paths
        ),
    ]
    artifacts.sort(key=lambda artifact: (artifact.role, artifact.path))
    command = tuple(transformation_command)
    return SnapshotManifest(
        dataset_schema_id=dataset_schema_id,
        dataset_schema_version=dataset_schema_version,
        source_catalog_sha256=sha256_file(
            source_catalog_path.resolve(strict=True)
        ),
        transformation=TransformationLineage(
            command=command,
            package_commit=package_commit,
        ),
        artifacts=tuple(artifacts),
    )


def write_snapshot_manifest(
    manifest: SnapshotManifest,
    destination: Path,
) -> Path:
    """Write deterministic manifest JSON without copying source payloads."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical_json_bytes(manifest))
    return destination


def verify_snapshot_manifest(
    manifest_path: Path,
    *,
    fixture_root: Path,
    source_catalog_path: Path,
) -> SnapshotManifest:
    """Validate a manifest and reject changed, missing, or forbidden artifacts."""
    manifest = SnapshotManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    if sha256_file(source_catalog_path.resolve(strict=True)) != (
        manifest.source_catalog_sha256
    ):
        raise ValueError("Source catalog digest does not match the manifest")
    for artifact in manifest.artifacts:
        qualified = _qualified_artifact(
            fixture_root / PurePosixPath(artifact.path),
            fixture_root=fixture_root,
            role=artifact.role,
        )
        if qualified != artifact:
            raise ValueError(
                f"Artifact digest or size mismatch: {artifact.path}"
            )
    return manifest
