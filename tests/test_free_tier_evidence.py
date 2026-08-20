from __future__ import annotations

import json
from pathlib import Path

import pytest

from global_medicines_atlas.free_tier_evidence import (
    ArtifactOrigin,
    PublicArtifact,
    Sensitivity,
    build_public_manifest,
    sha256_file,
    verify_public_manifest,
    write_public_manifest,
)


def artifact(**overrides: object) -> PublicArtifact:
    values = {
        "path": "synthetic/records.json",
        "origin": ArtifactOrigin.REPOSITORY_AUTHORED_SYNTHETIC,
        "license": "Apache-2.0",
        "sensitivity": Sensitivity.PUBLIC,
        "sha256": "a" * 64,
    }
    values.update(overrides)
    return PublicArtifact(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        (
            {"origin": ArtifactOrigin.SOURCE_DERIVED},
            "source_derived_bytes_excluded",
        ),
        ({"contains_credentials": True}, "credential_material_excluded"),
        ({"sensitivity": Sensitivity.SENSITIVE}, "non_public_sensitivity"),
        ({"rights_resolved": False}, "rights_unresolved"),
        ({"license": None}, "apache_2_0_license_required"),
    ],
)
def test_publication_decision_fails_closed(
    overrides: dict[str, object], reason: str
) -> None:
    candidate = artifact(**overrides)
    assert candidate.publication_state == "excluded"
    assert candidate.exclusion_reason == reason


def test_publication_decision_approves_repo_synthetic_artifact() -> None:
    candidate = artifact()
    assert candidate.publication_state == "approved_public"
    assert candidate.exclusion_reason is None


def test_artifact_path_cannot_escape_package() -> None:
    with pytest.raises(ValueError, match="relative and contained"):
        artifact(path="../secret")


def test_manifest_is_deterministic_exact_and_digest_bound(
    tmp_path: Path,
) -> None:
    (tmp_path / "synthetic").mkdir()
    fixture = tmp_path / "synthetic" / "records.json"
    fixture.write_text('[{"native_id":"A-001","value":1}]\n', encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# Synthetic evidence\n", encoding="utf-8"
    )

    target = write_public_manifest(tmp_path)
    manifest = json.loads(target.read_text(encoding="utf-8"))
    verify_public_manifest(tmp_path, manifest)
    assert manifest == build_public_manifest(tmp_path)
    entries = {item["path"]: item for item in manifest["artifacts"]}
    assert entries["synthetic/records.json"]["sha256"] == sha256_file(fixture)

    fixture.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        verify_public_manifest(tmp_path, manifest)
