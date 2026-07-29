"""Fail-closed consistency checks for governed software release metadata."""

from __future__ import annotations

import re
import tomllib
from datetime import date
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Final, cast

from pydantic import Field, model_validator

from .models import FrozenModel

_SEMVER: Final = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_DIGEST: Final = re.compile(r"^[0-9a-f]{64}$")
_QUOTED_SCALAR_MIN_LENGTH: Final = 2
_UNDECIDED_LICENCE_MARKERS: Final = (
    "no software licence has yet been selected",
    "license has not been selected",
    "licence has not been selected",
    "pending explicit maintainer license selection",
    "pending explicit maintainer licence selection",
)


class MetadataGate(StrEnum):
    """Independently inspectable release-metadata gates."""

    DYNAMIC_VERSION = "dynamic_version"
    SEMVER = "semver"
    CHANGELOG = "changelog"
    CITATION = "citation"
    LICENCE = "licence"
    ARTIFACT_IDENTITIES = "artifact_identities"
    PREPUBLICATION_QUALIFICATION = "prepublication_qualification"


class GateResult(StrEnum):
    """Outcome of one metadata gate."""

    PASSED = "passed"
    FAILED = "failed"


class MetadataFinding(FrozenModel):
    """A stable, actionable reason a release is blocked."""

    gate: MetadataGate
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    path: str | None = None


class ImmutableArtifact(FrozenModel):
    """Expected content identity for one local release artifact."""

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)


class PrepublicationQualification(FrozenModel):
    """Independent qualification evidence bound to exact release artifacts."""

    release_version: str = Field(min_length=1)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    qualified: bool
    artifact_sha256: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def artifact_identities_are_canonical(self) -> PrepublicationQualification:
        if any(not _DIGEST.fullmatch(value) for value in self.artifact_sha256):
            raise ValueError(
                "qualification artifact digests must be lowercase SHA-256"
            )
        if tuple(sorted(set(self.artifact_sha256))) != self.artifact_sha256:
            raise ValueError(
                "qualification artifact digests must be unique and sorted"
            )
        return self


class ReleaseMetadataReport(FrozenModel):
    """Complete, deterministic release-metadata qualification decision."""

    release_version: str
    dynamic_version: str
    qualified: bool
    gates: dict[MetadataGate, GateResult]
    artifacts: tuple[ImmutableArtifact, ...]
    findings: tuple[MetadataFinding, ...]

    @model_validator(mode="after")
    def decision_matches_gates(self) -> ReleaseMetadataReport:
        passed = (
            len(self.gates) == len(MetadataGate)
            and all(
                result is GateResult.PASSED for result in self.gates.values()
            )
            and not self.findings
        )
        if self.qualified != passed:
            raise ValueError("qualified decision does not match gate outcomes")
        return self


def _top_level_cff_scalars(text: str) -> dict[str, str]:
    """Read only unambiguous top-level CFF scalar metadata.

    The validator deliberately does not attempt to interpret arbitrary YAML.
    Release gates use simple top-level CFF fields, so ambiguous or structured
    values remain absent and therefore fail closed.
    """

    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        if not raw_line or raw_line[0].isspace() or raw_line.startswith("#"):
            continue
        key, separator, raw_value = raw_line.partition(":")
        if not separator:
            continue
        value = raw_value.strip()
        if not value or value[0] in "[{>|":
            continue
        if (
            len(value) >= _QUOTED_SCALAR_MIN_LENGTH
            and value[0] == value[-1]
            and value[0] in "\"'"
        ):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _read_text(
    root: Path,
    relative_path: str,
    gate: MetadataGate,
    findings: list[MetadataFinding],
) -> str | None:
    path = root / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        findings.append(
            MetadataFinding(
                gate=gate,
                code="metadata-unreadable",
                message=f"Required metadata is not readable: {error}",
                path=relative_path,
            )
        )
        return None


def _add_finding(
    findings: list[MetadataFinding],
    *,
    gate: MetadataGate,
    code: str,
    message: str,
    path: str | None = None,
) -> None:
    findings.append(
        MetadataFinding(gate=gate, code=code, message=message, path=path)
    )


def _validate_versioning(
    *,
    root: Path,
    release_version: str,
    dynamic_version: str,
    findings: list[MetadataFinding],
) -> None:
    manifest_text = _read_text(
        root, "pyproject.toml", MetadataGate.DYNAMIC_VERSION, findings
    )
    if manifest_text is not None:
        try:
            manifest = tomllib.loads(manifest_text)
        except tomllib.TOMLDecodeError as error:
            _add_finding(
                findings,
                gate=MetadataGate.DYNAMIC_VERSION,
                code="invalid-pyproject",
                message=f"pyproject.toml is invalid: {error}",
                path="pyproject.toml",
            )
        else:
            project = manifest.get("project", {})
            hatch = manifest.get("tool", {}).get("hatch", {})
            dynamic = project.get("dynamic", [])
            version_config = hatch.get("version", {})
            if "version" not in dynamic or "version" in project:
                _add_finding(
                    findings,
                    gate=MetadataGate.DYNAMIC_VERSION,
                    code="dynamic-version-not-canonical",
                    message=(
                        "project version must be declared dynamic and must not "
                        "also contain a static version"
                    ),
                    path="pyproject.toml",
                )
            if version_config.get("source") != "vcs":
                _add_finding(
                    findings,
                    gate=MetadataGate.DYNAMIC_VERSION,
                    code="vcs-versioning-not-configured",
                    message="dynamic version must be derived from VCS metadata",
                    path="pyproject.toml",
                )

    normalized_release = release_version.removeprefix("v")
    if not _SEMVER.fullmatch(normalized_release):
        _add_finding(
            findings,
            gate=MetadataGate.SEMVER,
            code="invalid-semver",
            message="release version must be a complete Semantic Version",
        )
    if dynamic_version != normalized_release:
        _add_finding(
            findings,
            gate=MetadataGate.DYNAMIC_VERSION,
            code="dynamic-version-mismatch",
            message=(
                "resolved dynamic version must exactly equal the requested "
                "release version"
            ),
        )


def _validate_changelog(
    root: Path,
    release_version: str,
    findings: list[MetadataFinding],
) -> str | None:
    text = _read_text(root, "CHANGELOG.md", MetadataGate.CHANGELOG, findings)
    if text is None:
        return None
    version = re.escape(release_version.removeprefix("v"))
    heading = re.compile(
        rf"^## \[?{version}\]?(?: - (?P<date>\d{{4}}-\d{{2}}-\d{{2}}))?\s*$",
        re.MULTILINE,
    ).search(text)
    if heading is None:
        _add_finding(
            findings,
            gate=MetadataGate.CHANGELOG,
            code="release-missing-from-changelog",
            message="changelog must contain a heading for the exact release",
            path="CHANGELOG.md",
        )
        return None
    released_on = heading.group("date")
    if released_on is None:
        _add_finding(
            findings,
            gate=MetadataGate.CHANGELOG,
            code="changelog-release-date-missing",
            message="release changelog heading must include an ISO date",
            path="CHANGELOG.md",
        )
        return None
    try:
        date.fromisoformat(released_on)
    except ValueError:
        _add_finding(
            findings,
            gate=MetadataGate.CHANGELOG,
            code="changelog-release-date-invalid",
            message="release changelog date must be a valid ISO date",
            path="CHANGELOG.md",
        )
        return None
    return released_on


def _validate_citation(
    root: Path,
    release_version: str,
    findings: list[MetadataFinding],
) -> tuple[dict[str, str], str | None]:
    text = _read_text(root, "CITATION.cff", MetadataGate.CITATION, findings)
    if text is None:
        return {}, None
    citation = _top_level_cff_scalars(text)
    expected = release_version.removeprefix("v")
    if citation.get("version") != expected:
        _add_finding(
            findings,
            gate=MetadataGate.CITATION,
            code="citation-version-mismatch",
            message="CITATION.cff version must equal the release version",
            path="CITATION.cff",
        )
    released_on = citation.get("date-released")
    if released_on is None or not _is_iso_date(released_on):
        _add_finding(
            findings,
            gate=MetadataGate.CITATION,
            code="citation-release-date-invalid",
            message="CITATION.cff must contain a valid date-released",
            path="CITATION.cff",
        )
        released_on = None
    return citation, released_on


def _validate_release_dates_agree(
    *,
    changelog_date: str | None,
    citation_date: str | None,
    findings: list[MetadataFinding],
) -> None:
    if (
        changelog_date is not None
        and citation_date is not None
        and changelog_date != citation_date
    ):
        _add_finding(
            findings,
            gate=MetadataGate.CITATION,
            code="release-date-mismatch",
            message=(
                "CHANGELOG.md and CITATION.cff must record the same release date"
            ),
        )


def _validate_licence(
    root: Path,
    citation: dict[str, str],
    findings: list[MetadataFinding],
) -> None:
    manifest_text = _read_text(
        root, "pyproject.toml", MetadataGate.LICENCE, findings
    )
    notice = _read_text(root, "NOTICE", MetadataGate.LICENCE, findings)
    declared: str | None = None
    if manifest_text is not None:
        try:
            project: object = tomllib.loads(manifest_text).get("project", {})
        except tomllib.TOMLDecodeError:
            project = None
        project_metadata = (
            cast("dict[str, object]", project)
            if isinstance(project, dict)
            else {}
        )
        licence: object = project_metadata.get("license")
        if isinstance(licence, str):
            declared = licence.strip()

    citation_licence = citation.get("license")
    if not declared or not citation_licence:
        _add_finding(
            findings,
            gate=MetadataGate.LICENCE,
            code="software-licence-undecided",
            message=(
                "an explicit maintainer-approved software licence decision "
                "must appear in both pyproject.toml and CITATION.cff"
            ),
        )
    elif declared != citation_licence:
        _add_finding(
            findings,
            gate=MetadataGate.LICENCE,
            code="software-licence-mismatch",
            message="pyproject.toml and CITATION.cff licence values must agree",
        )

    if notice is not None and any(
        marker in notice.casefold() for marker in _UNDECIDED_LICENCE_MARKERS
    ):
        _add_finding(
            findings,
            gate=MetadataGate.LICENCE,
            code="notice-records-undecided-licence",
            message="NOTICE still records that no software licence was selected",
            path="NOTICE",
        )


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_artifacts(
    root: Path,
    artifacts: tuple[ImmutableArtifact, ...],
    findings: list[MetadataFinding],
) -> None:
    """Validate content through strictly resolved, root-contained paths.

    Resolution rejects symlink and junction escapes before the resolved target
    is opened. The digest and size are computed from that same open target.
    This limits, but cannot eliminate, a privileged concurrent filesystem
    mutation between resolution and open; publication must therefore run in a
    controlled workspace without concurrent writers.
    """

    if not artifacts:
        _add_finding(
            findings,
            gate=MetadataGate.ARTIFACT_IDENTITIES,
            code="artifact-identities-missing",
            message="at least one immutable release artifact identity is required",
        )
        return

    names = [artifact.path for artifact in artifacts]
    if len(names) != len(set(names)):
        _add_finding(
            findings,
            gate=MetadataGate.ARTIFACT_IDENTITIES,
            code="duplicate-artifact-path",
            message="release artifact paths must be unique",
        )
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        _add_finding(
            findings,
            gate=MetadataGate.ARTIFACT_IDENTITIES,
            code="artifact-root-unreadable",
            message=f"artifact root cannot be resolved: {error}",
        )
        return

    for artifact in artifacts:
        relative = Path(artifact.path)
        if relative.is_absolute() or ".." in relative.parts:
            _add_finding(
                findings,
                gate=MetadataGate.ARTIFACT_IDENTITIES,
                code="unsafe-artifact-path",
                message="artifact path must be relative and remain within the root",
                path=artifact.path,
            )
            continue
        try:
            resolved_path = (resolved_root / relative).resolve(strict=True)
            resolved_path.relative_to(resolved_root)
        except ValueError:
            _add_finding(
                findings,
                gate=MetadataGate.ARTIFACT_IDENTITIES,
                code="artifact-path-escape",
                message=(
                    "resolved artifact path escapes the controlled release root"
                ),
                path=artifact.path,
            )
            continue
        except OSError as error:
            _add_finding(
                findings,
                gate=MetadataGate.ARTIFACT_IDENTITIES,
                code="artifact-unreadable",
                message=f"release artifact is not readable: {error}",
                path=artifact.path,
            )
            continue
        try:
            # Read the already-resolved target, not the caller-provided path.
            payload = resolved_path.read_bytes()
        except OSError as error:
            _add_finding(
                findings,
                gate=MetadataGate.ARTIFACT_IDENTITIES,
                code="artifact-unreadable",
                message=f"resolved release artifact is not readable: {error}",
                path=artifact.path,
            )
            continue
        if len(payload) != artifact.size:
            _add_finding(
                findings,
                gate=MetadataGate.ARTIFACT_IDENTITIES,
                code="artifact-size-mismatch",
                message="recorded artifact size does not match its bytes",
                path=artifact.path,
            )
        if sha256(payload).hexdigest() != artifact.sha256:
            _add_finding(
                findings,
                gate=MetadataGate.ARTIFACT_IDENTITIES,
                code="artifact-digest-mismatch",
                message="recorded artifact SHA-256 does not match its bytes",
                path=artifact.path,
            )


def _validate_qualification(
    *,
    release_version: str,
    artifacts: tuple[ImmutableArtifact, ...],
    qualification: PrepublicationQualification | None,
    findings: list[MetadataFinding],
) -> None:
    if qualification is None:
        _add_finding(
            findings,
            gate=MetadataGate.PREPUBLICATION_QUALIFICATION,
            code="prepublication-qualification-missing",
            message="independent pre-publication qualification is required",
        )
        return
    if not qualification.qualified:
        _add_finding(
            findings,
            gate=MetadataGate.PREPUBLICATION_QUALIFICATION,
            code="prepublication-qualification-failed",
            message="pre-publication evidence does not qualify this release",
        )
    if qualification.release_version != release_version.removeprefix("v"):
        _add_finding(
            findings,
            gate=MetadataGate.PREPUBLICATION_QUALIFICATION,
            code="qualification-version-mismatch",
            message="qualification evidence targets a different release version",
        )
    artifact_digests = tuple(
        sorted({artifact.sha256 for artifact in artifacts})
    )
    if qualification.artifact_sha256 != artifact_digests:
        _add_finding(
            findings,
            gate=MetadataGate.PREPUBLICATION_QUALIFICATION,
            code="qualification-artifacts-mismatch",
            message="qualification evidence is not bound to the exact artifacts",
        )


def validate_release_metadata(
    *,
    root: Path,
    release_version: str,
    dynamic_version: str,
    artifacts: tuple[ImmutableArtifact, ...] = (),
    qualification: PrepublicationQualification | None = None,
) -> ReleaseMetadataReport:
    """Validate metadata and exact artifacts before any publication action."""

    findings: list[MetadataFinding] = []
    _validate_versioning(
        root=root,
        release_version=release_version,
        dynamic_version=dynamic_version,
        findings=findings,
    )
    changelog_date = _validate_changelog(root, release_version, findings)
    citation, citation_date = _validate_citation(
        root, release_version, findings
    )
    _validate_release_dates_agree(
        changelog_date=changelog_date,
        citation_date=citation_date,
        findings=findings,
    )
    _validate_licence(root, citation, findings)
    _validate_artifacts(root, artifacts, findings)
    _validate_qualification(
        release_version=release_version,
        artifacts=artifacts,
        qualification=qualification,
        findings=findings,
    )

    failed = {finding.gate for finding in findings}
    gates = {
        gate: GateResult.FAILED if gate in failed else GateResult.PASSED
        for gate in MetadataGate
    }
    ordered_findings = tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.gate.value,
                finding.code,
                finding.path or "",
            ),
        )
    )
    return ReleaseMetadataReport(
        release_version=release_version.removeprefix("v"),
        dynamic_version=dynamic_version,
        qualified=not ordered_findings,
        gates=gates,
        artifacts=artifacts,
        findings=ordered_findings,
    )
