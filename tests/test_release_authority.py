from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.validate_release_authority import (
    DEFAULT_AUTHORITY,
    validate_release_authority,
)


def test_exact_release_candidate_is_authorized() -> None:
    authority = validate_release_authority(
        authority_path=DEFAULT_AUTHORITY,
        tag="v1.0.0rc1",
        release_type="prerelease",
        artifact_scope="software-only",
    )
    assert authority["commit_binding"] == (
        "tag-must-resolve-to-workflow-commit"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tag", "v1.0.0"),
        ("release_type", "release"),
        ("artifact_scope", "software-and-dataset"),
    ],
)
def test_unapproved_release_variation_fails_closed(
    field: str,
    value: str,
) -> None:
    inputs = {
        "tag": "v1.0.0rc1",
        "release_type": "prerelease",
        "artifact_scope": "software-only",
    }
    inputs[field] = value
    with pytest.raises(ValueError, match="not approved"):
        validate_release_authority(
            authority_path=DEFAULT_AUTHORITY,
            **inputs,
        )


def test_missing_approval_evidence_fails_closed(tmp_path: Path) -> None:
    authority = json.loads(DEFAULT_AUTHORITY.read_text(encoding="utf-8"))
    authority["approval_evidence"] = "missing.md"
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence is missing"):
        validate_release_authority(
            authority_path=path,
            tag="v1.0.0rc1",
            release_type="prerelease",
            artifact_scope="software-only",
        )
