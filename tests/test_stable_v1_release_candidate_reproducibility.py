"""Independent detached-worktree reproduction for stable-v1 candidates."""

from __future__ import annotations

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path

import pytest
from scripts.build_stable_v1_release_candidate import (
    clean_detached_reproducibility,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_lf_and_crlf_policy_detached_worktrees_reproduce_exactly() -> None:
    """Build the exact commit in two clean, detached checkout policies."""
    git = shutil.which("git")
    assert git is not None
    status = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [git, "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status:
        pytest.skip(
            "detached-worktree evidence requires a committed clean tree"
        )

    evidence = clean_detached_reproducibility(ROOT)

    assert evidence["state"] == "passed"
    assert evidence["checkout_policies"] == ["autocrlf-false", "autocrlf-true"]
    assert evidence["cross_platform_ci_required"] is True
    assert len(evidence["artifacts"]) == 3
    assert all(item["sha256"] for item in evidence["artifacts"])
    assert all(
        item["line_ending"] == "lf" for item in evidence["packaged_text_inputs"]
    )
