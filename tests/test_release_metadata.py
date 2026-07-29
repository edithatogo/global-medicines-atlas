"""Tests for fail-closed governed release-metadata qualification."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.release_metadata import (
    GateResult,
    ImmutableArtifact,
    MetadataGate,
    PrepublicationQualification,
    validate_release_metadata,
)

VERSION = "0.7.0"
EVIDENCE_DIGEST = "e" * 64


def _write_release_metadata(
    root: Path,
    *,
    project_license: str | None = "Apache-2.0",
    citation_license: str | None = "Apache-2.0",
    citation_version: str | None = VERSION,
    citation_date: str | None = "2026-07-29",
    changelog_heading: str = "## [0.7.0] - 2026-07-29",
    notice: str = "Software licence decision: Apache-2.0.\n",
    vcs_source: str = "vcs",
) -> None:
    licence_line = (
        f'license = "{project_license}"\n'
        if project_license is not None
        else ""
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "global-medicines-atlas"\n'
        'dynamic = ["version"]\n'
        f"{licence_line}"
        "[tool.hatch.version]\n"
        f'source = "{vcs_source}"\n',
        encoding="utf-8",
    )
    citation_lines = [
        "cff-version: 1.2.0",
        'title: "Global Medicines Atlas"',
    ]
    if citation_version is not None:
        citation_lines.append(f'version: "{citation_version}"')
    if citation_date is not None:
        citation_lines.append(f"date-released: {citation_date}")
    if citation_license is not None:
        citation_lines.append(f"license: {citation_license}")
    (root / "CITATION.cff").write_text(
        "\n".join(citation_lines) + "\n", encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n{changelog_heading}\n\n- Qualified release.\n",
        encoding="utf-8",
    )
    (root / "NOTICE").write_text(notice, encoding="utf-8")


def _artifact(
    root: Path, payload: bytes = b"immutable release\n"
) -> ImmutableArtifact:
    artifact_path = root / "dist" / "release.tar.gz"
    artifact_path.parent.mkdir()
    artifact_path.write_bytes(payload)
    return ImmutableArtifact(
        path="dist/release.tar.gz",
        sha256=sha256(payload).hexdigest(),
        size=len(payload),
    )


def _qualification(
    artifact: ImmutableArtifact,
    *,
    qualified: bool = True,
    version: str = VERSION,
    digest: str | None = None,
) -> PrepublicationQualification:
    return PrepublicationQualification(
        release_version=version,
        evidence_sha256=EVIDENCE_DIGEST,
        qualified=qualified,
        artifact_sha256=(digest or artifact.sha256,),
    )


def _qualified_report(root: Path):
    _write_release_metadata(root)
    artifact = _artifact(root)
    return validate_release_metadata(
        root=root,
        release_version=VERSION,
        dynamic_version=VERSION,
        artifacts=(artifact,),
        qualification=_qualification(artifact),
    )


@pytest.mark.unit
def test_consistent_release_metadata_qualifies(tmp_path: Path) -> None:
    report = _qualified_report(tmp_path)

    assert report.qualified is True
    assert not report.findings
    assert set(report.gates) == set(MetadataGate)
    assert all(result is GateResult.PASSED for result in report.gates.values())


@pytest.mark.unit
def test_v_prefixed_requested_version_is_normalized(tmp_path: Path) -> None:
    _write_release_metadata(tmp_path)
    artifact = _artifact(tmp_path)

    report = validate_release_metadata(
        root=tmp_path,
        release_version="v0.7.0",
        dynamic_version=VERSION,
        artifacts=(artifact,),
        qualification=_qualification(artifact),
    )

    assert report.qualified
    assert report.release_version == VERSION


@pytest.mark.parametrize(
    ("version", "code"),
    [
        ("0.7", "invalid-semver"),
        ("01.7.0", "invalid-semver"),
        ("0.7.0-01", "invalid-semver"),
        ("0.7.0.dev1", "invalid-semver"),
    ],
)
@pytest.mark.unit
def test_non_semver_release_is_blocked(
    tmp_path: Path, version: str, code: str
) -> None:
    _write_release_metadata(tmp_path, citation_version=version)
    artifact = _artifact(tmp_path)

    report = validate_release_metadata(
        root=tmp_path,
        release_version=version,
        dynamic_version=version,
        artifacts=(artifact,),
        qualification=_qualification(artifact, version=version),
    )

    assert not report.qualified
    assert code in {finding.code for finding in report.findings}
    assert report.gates[MetadataGate.SEMVER] is GateResult.FAILED


@pytest.mark.unit
def test_dynamic_version_must_match_release(tmp_path: Path) -> None:
    report = _qualified_report(tmp_path)
    artifact = report.artifacts[0]

    mismatched = validate_release_metadata(
        root=tmp_path,
        release_version=VERSION,
        dynamic_version="0.7.1.dev1",
        artifacts=(artifact,),
        qualification=_qualification(artifact),
    )

    assert "dynamic-version-mismatch" in {
        finding.code for finding in mismatched.findings
    }


@pytest.mark.parametrize(
    ("manifest", "code"),
    [
        (
            "\n".join((
                "[project]",
                'name="x"',
                'version="0.7.0"',
                "[tool.hatch.version]",
                'source="vcs"',
            )),
            "dynamic-version-not-canonical",
        ),
        (
            "\n".join((
                "[project]",
                'name="x"',
                'dynamic=["version"]',
                "[tool.hatch.version]",
                'source="code"',
            )),
            "vcs-versioning-not-configured",
        ),
        ("not = [valid", "invalid-pyproject"),
    ],
)
@pytest.mark.unit
def test_dynamic_version_configuration_is_fail_closed(
    tmp_path: Path, manifest: str, code: str
) -> None:
    _write_release_metadata(tmp_path)
    (tmp_path / "pyproject.toml").write_text(manifest, encoding="utf-8")
    artifact = _artifact(tmp_path)

    report = validate_release_metadata(
        root=tmp_path,
        release_version=VERSION,
        dynamic_version=VERSION,
        artifacts=(artifact,),
        qualification=_qualification(artifact),
    )

    assert code in {finding.code for finding in report.findings}


@pytest.mark.parametrize(
    ("heading", "code"),
    [
        ("## Unreleased", "release-missing-from-changelog"),
        ("## [0.7.0]", "changelog-release-date-missing"),
        ("## [0.7.0] - 2026-02-31", "changelog-release-date-invalid"),
    ],
)
@pytest.mark.unit
def test_changelog_requires_exact_version_and_valid_date(
    tmp_path: Path, heading: str, code: str
) -> None:
    _write_release_metadata(tmp_path, changelog_heading=heading)
    artifact = _artifact(tmp_path)

    report = validate_release_metadata(
        root=tmp_path,
        release_version=VERSION,
        dynamic_version=VERSION,
        artifacts=(artifact,),
        qualification=_qualification(artifact),
    )

    assert code in {finding.code for finding in report.findings}
    assert report.gates[MetadataGate.CHANGELOG] is GateResult.FAILED


@pytest.mark.parametrize(
    ("citation_version", "citation_date", "code"),
    [
        (None, "2026-07-29", "citation-version-mismatch"),
        ("0.7.1", "2026-07-29", "citation-version-mismatch"),
        (VERSION, None, "citation-release-date-invalid"),
        (VERSION, "2026-02-31", "citation-release-date-invalid"),
    ],
)
@pytest.mark.unit
def test_citation_requires_matching_version_and_valid_date(
    tmp_path: Path,
    citation_version: str | None,
    citation_date: str | None,
    code: str,
) -> None:
    _write_release_metadata(
        tmp_path,
        citation_version=citation_version,
        citation_date=citation_date,
    )
    artifact = _artifact(tmp_path)

    report = validate_release_metadata(
        root=tmp_path,
        release_version=VERSION,
        dynamic_version=VERSION,
        artifacts=(artifact,),
        qualification=_qualification(artifact),
    )

    assert code in {finding.code for finding in report.findings}


@pytest.mark.parametrize(
    (
        "project_license",
        "citation_license",
        "notice",
        "expected_code",
    ),
    [
        (
            None,
            None,
            "No software licence has yet been selected.\n",
            "software-licence-undecided",
        ),
        (
            "Apache-2.0",
            "MIT",
            "Software licence decision recorded.\n",
            "software-licence-mismatch",
        ),
        (
            "Apache-2.0",
            "Apache-2.0",
            "No software licence has yet been selected.\n",
            "notice-records-undecided-licence",
        ),
    ],
)
@pytest.mark.unit
def test_licence_gate_never_infers_a_decision(
    tmp_path: Path,
    project_license: str | None,
    citation_license: str | None,
    notice: str,
    expected_code: str,
) -> None:
    _write_release_metadata(
        tmp_path,
        project_license=project_license,
        citation_license=citation_license,
        notice=notice,
    )
    artifact = _artifact(tmp_path)

    report = validate_release_metadata(
        root=tmp_path,
        release_version=VERSION,
        dynamic_version=VERSION,
        artifacts=(artifact,),
        qualification=_qualification(artifact),
    )

    assert expected_code in {finding.code for finding in report.findings}
    assert report.gates[MetadataGate.LICENCE] is GateResult.FAILED


@pytest.mark.unit
def test_current_repository_metadata_fails_closed_without_licence() -> None:
    root = Path(__file__).resolve().parents[1]

    report = validate_release_metadata(
        root=root,
        release_version=VERSION,
        dynamic_version=VERSION,
    )

    codes = {finding.code for finding in report.findings}
    assert "software-licence-undecided" in codes
    assert "notice-records-undecided-licence" in codes
    assert "release-missing-from-changelog" in codes
    assert "citation-version-mismatch" in codes
    assert not report.qualified


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("missing", "artifact-identities-missing"),
        ("digest", "artifact-digest-mismatch"),
        ("size", "artifact-size-mismatch"),
        ("unreadable", "artifact-unreadable"),
        ("unsafe", "unsafe-artifact-path"),
        ("duplicate", "duplicate-artifact-path"),
    ],
)
@pytest.mark.unit
def test_artifacts_require_verified_immutable_identities(
    tmp_path: Path, mutation: str, code: str
) -> None:
    _write_release_metadata(tmp_path)
    artifact = _artifact(tmp_path)
    artifacts = (artifact,)
    if mutation == "missing":
        artifacts = ()
    elif mutation == "digest":
        artifacts = (artifact.model_copy(update={"sha256": "0" * 64}),)
    elif mutation == "size":
        artifacts = (artifact.model_copy(update={"size": artifact.size + 1}),)
    elif mutation == "unreadable":
        artifacts = (
            artifact.model_copy(update={"path": "dist/missing.tar.gz"}),
        )
    elif mutation == "unsafe":
        artifacts = (artifact.model_copy(update={"path": "../release.tar.gz"}),)
    elif mutation == "duplicate":
        artifacts = (artifact, artifact)

    report = validate_release_metadata(
        root=tmp_path,
        release_version=VERSION,
        dynamic_version=VERSION,
        artifacts=artifacts,
        qualification=(
            _qualification(artifact) if mutation != "missing" else None
        ),
    )

    assert code in {finding.code for finding in report.findings}
    assert report.gates[MetadataGate.ARTIFACT_IDENTITIES] is GateResult.FAILED


@pytest.mark.parametrize(
    ("qualification_kind", "code"),
    [
        ("missing", "prepublication-qualification-missing"),
        ("failed", "prepublication-qualification-failed"),
        ("version", "qualification-version-mismatch"),
        ("artifacts", "qualification-artifacts-mismatch"),
    ],
)
@pytest.mark.unit
def test_prepublication_qualification_is_required_and_exact(
    tmp_path: Path, qualification_kind: str, code: str
) -> None:
    _write_release_metadata(tmp_path)
    artifact = _artifact(tmp_path)
    qualification = _qualification(artifact)
    if qualification_kind == "missing":
        qualification = None
    elif qualification_kind == "failed":
        qualification = _qualification(artifact, qualified=False)
    elif qualification_kind == "version":
        qualification = _qualification(artifact, version="0.7.1")
    elif qualification_kind == "artifacts":
        qualification = _qualification(artifact, digest="0" * 64)

    report = validate_release_metadata(
        root=tmp_path,
        release_version=VERSION,
        dynamic_version=VERSION,
        artifacts=(artifact,),
        qualification=qualification,
    )

    assert code in {finding.code for finding in report.findings}
    assert (
        report.gates[MetadataGate.PREPUBLICATION_QUALIFICATION]
        is GateResult.FAILED
    )


@pytest.mark.unit
def test_qualification_rejects_noncanonical_artifact_digest_set() -> None:
    with pytest.raises(ValidationError, match="unique and sorted"):
        PrepublicationQualification(
            release_version=VERSION,
            evidence_sha256=EVIDENCE_DIGEST,
            qualified=True,
            artifact_sha256=("f" * 64, "a" * 64, "f" * 64),
        )


@pytest.mark.unit
def test_missing_metadata_files_produce_findings(tmp_path: Path) -> None:
    report = validate_release_metadata(
        root=tmp_path,
        release_version=VERSION,
        dynamic_version=VERSION,
    )

    unreadable_paths = {
        finding.path
        for finding in report.findings
        if finding.code == "metadata-unreadable"
    }
    assert unreadable_paths == {
        "CHANGELOG.md",
        "CITATION.cff",
        "NOTICE",
        "pyproject.toml",
    }
    assert not report.qualified


@pytest.mark.unit
def test_findings_are_deterministically_ordered(tmp_path: Path) -> None:
    first = validate_release_metadata(
        root=tmp_path,
        release_version="bad",
        dynamic_version="different",
    )
    second = validate_release_metadata(
        root=tmp_path,
        release_version="bad",
        dynamic_version="different",
    )

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    keys = [
        (finding.gate.value, finding.code, finding.path or "")
        for finding in first.findings
    ]
    assert keys == sorted(keys)
