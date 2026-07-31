"""Independent detached-worktree reproduction for stable-v1 candidates."""

from __future__ import annotations

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tempfile
from pathlib import Path

import pytest
from scripts.build_stable_v1_release_candidate import (
    build_candidate,
    consume_candidate,
)

from global_medicines_atlas.stable_v1_release_candidate import (
    ArtifactRole,
    receipt_from_json,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
@pytest.mark.timeout(600)
def test_clean_clone_reproduces_receipt_and_consumes_artifacts() -> None:
    """Rebuild the recorded commit in a clone and match committed bytes."""
    git = shutil.which("git")
    assert git is not None
    committed_path = (
        ROOT / "quality/qualifications/stable-v1-release-candidate.json"
    )
    committed = receipt_from_json(committed_path)

    with tempfile.TemporaryDirectory(
        prefix="gma-stable-v1-clean-clone-", ignore_cleanup_errors=True
    ) as temporary:
        temporary_root = Path(temporary)
        clone = temporary_root / "repository"
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [git, "clone", "--no-local", str(ROOT), str(clone)],
            check=True,
            capture_output=True,
        )
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [git, "checkout", "--detach", committed.source_commit],
            cwd=clone,
            check=True,
            capture_output=True,
        )
        stage = temporary_root / "candidate"
        rebuilt_path = temporary_root / "rebuilt-receipt.json"
        build_candidate(clone, stage, rebuilt_path)
        rebuilt = receipt_from_json(rebuilt_path)

        expected = {
            item.role: (item.sha256, item.size) for item in committed.artifacts
        }
        actual = {
            item.role: (item.sha256, item.size) for item in rebuilt.artifacts
        }
        assert actual == expected
        assert rebuilt.manifest == committed.manifest
        assert rebuilt.checksums == committed.checksums
        assert rebuilt.content_sha256 == committed.content_sha256

        for role in (ArtifactRole.WHEEL, ArtifactRole.SDIST):
            result = consume_candidate(
                root=clone,
                stage=stage,
                receipt_path=committed_path,
                artifact_role=role,
                environment=temporary_root / f"consumer-{role.value}",
            )
            assert result["state"] == "passed"
