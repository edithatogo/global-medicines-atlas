"""Fail-closed packaging for public, free-tier experiment evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

_SHA256_LENGTH = 64


class ArtifactOrigin(StrEnum):
    """Origins permitted in an experiment inventory."""

    REPOSITORY_AUTHORED_SYNTHETIC = "repository_authored_synthetic"
    AGGREGATE_EVIDENCE = "aggregate_evidence"
    SOURCE_DERIVED = "source_derived"


class Sensitivity(StrEnum):
    """Publication sensitivity independent of licensing rights."""

    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"


@dataclass(frozen=True)
class PublicArtifact:
    """One proposed public artifact and its publication decision."""

    path: str
    origin: ArtifactOrigin
    license: str | None
    sensitivity: Sensitivity
    sha256: str
    contains_credentials: bool = False
    rights_resolved: bool = True

    def __post_init__(self) -> None:
        candidate = PurePosixPath(self.path)
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or not candidate.parts
        ):
            raise ValueError("artifact path must be relative and contained")
        if len(self.sha256) != _SHA256_LENGTH or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ValueError(
                "sha256 must be 64 lowercase hexadecimal characters"
            )

    @property
    def exclusion_reason(self) -> str | None:
        """Return the first fail-closed reason, or ``None`` when publishable."""
        if self.origin is ArtifactOrigin.SOURCE_DERIVED:
            return "source_derived_bytes_excluded"
        if self.contains_credentials:
            return "credential_material_excluded"
        if self.sensitivity is not Sensitivity.PUBLIC:
            return "non_public_sensitivity"
        if not self.rights_resolved:
            return "rights_unresolved"
        if self.license != "Apache-2.0":
            return "apache_2_0_license_required"
        return None

    @property
    def publication_state(self) -> str:
        """Return a stable allow/exclude state."""
        return (
            "approved_public" if self.exclusion_reason is None else "excluded"
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical manifest entry."""
        return {
            "path": self.path,
            "origin": self.origin.value,
            "license": self.license,
            "sensitivity": self.sensitivity.value,
            "sha256": self.sha256,
            "contains_credentials": self.contains_credentials,
            "rights_resolved": self.rights_resolved,
            "publication_state": self.publication_state,
            "exclusion_reason": self.exclusion_reason,
        }


def sha256_file(path: Path) -> str:
    """Hash an artifact without interpreting its bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_public_manifest(package_root: Path) -> dict[str, Any]:
    """Inventory the repository-authored files in a public package."""
    artifacts: list[dict[str, Any]] = []
    for path in sorted(
        item for item in package_root.rglob("*") if item.is_file()
    ):
        if path.name == "manifest.json":
            continue
        artifact = PublicArtifact(
            path=path.relative_to(package_root).as_posix(),
            origin=ArtifactOrigin.REPOSITORY_AUTHORED_SYNTHETIC,
            license="Apache-2.0",
            sensitivity=Sensitivity.PUBLIC,
            sha256=sha256_file(path),
        )
        artifacts.append(artifact.to_dict())
    return {
        "schema_version": "1.0",
        "package_id": "global-medicines-atlas-free-tier-evidence",
        "maintainer_authorization": "2026-08-21-public-synthetic-evidence-only",
        "artifacts": artifacts,
        "excluded_classes": [
            "credentials",
            "personal_or_sensitive_data",
            "source_derived_payload_bytes",
            "unresolved_rights_material",
        ],
    }


def verify_public_manifest(
    package_root: Path, manifest: dict[str, Any]
) -> None:
    """Verify that the manifest exactly covers the package and all files pass."""
    expected = build_public_manifest(package_root)
    if manifest != expected:
        raise ValueError(
            "public package does not match its deterministic manifest"
        )
    if any(
        artifact["publication_state"] != "approved_public"
        for artifact in manifest["artifacts"]
    ):
        raise ValueError("public package contains an excluded artifact")


def write_public_manifest(package_root: Path) -> Path:
    """Write and verify the deterministic package manifest."""
    manifest = build_public_manifest(package_root)
    target = package_root / "manifest.json"
    target.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    verify_public_manifest(package_root, manifest)
    return target
