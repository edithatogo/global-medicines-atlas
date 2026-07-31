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
    StableV1ReleaseCandidateReceipt,
)

ROOT = Path(__file__).resolve().parents[1]
COMMITTED_RECEIPT = (
    ROOT / "quality/qualifications/stable-v1-release-candidate.json"
)


@pytest.mark.integration
@pytest.mark.timeout(600)
def test_clean_clones_match_and_consume_artifacts() -> None:
    """Build twice from clean clones and exercise the shared receipt."""
    git = shutil.which("git")
    assert git is not None

    with tempfile.TemporaryDirectory(
        prefix="gma-stable-v1-clean-clone-", ignore_cleanup_errors=True
    ) as temporary:
        temporary_root = Path(temporary)
        clones = tuple(
            temporary_root / f"repository-{index}" for index in range(2)
        )
        stages = tuple(
            temporary_root / f"candidate-{index}" for index in range(2)
        )
        receipts = tuple(
            temporary_root / f"receipt-{index}.json" for index in range(2)
        )
        for clone, stage, receipt in zip(clones, stages, receipts, strict=True):
            subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
                [git, "clone", "--no-local", str(ROOT), str(clone)],
                check=True,
                capture_output=True,
            )
            build_candidate(clone, stage, receipt)

        assert receipts[0].read_bytes() == receipts[1].read_bytes()
        first_files = {
            path.relative_to(stages[0]): path.read_bytes()
            for path in stages[0].rglob("*")
            if path.is_file()
        }
        second_files = {
            path.relative_to(stages[1]): path.read_bytes()
            for path in stages[1].rglob("*")
            if path.is_file()
        }
        assert first_files == second_files

        for role in (ArtifactRole.WHEEL, ArtifactRole.SDIST):
            result = consume_candidate(
                root=clones[1],
                stage=stages[1],
                receipt_path=receipts[0],
                artifact_role=role,
                environment=temporary_root / f"consumer-{role.value}",
            )
            assert result["state"] == "passed"


@pytest.mark.integration
@pytest.mark.timeout(600)
def test_committed_receipt_reproduces_from_durable_source_commit() -> None:
    """Rebuild the committed candidate from its canonical remote commit."""
    git = shutil.which("git")
    assert git is not None
    committed_bytes = COMMITTED_RECEIPT.read_bytes()
    receipt = StableV1ReleaseCandidateReceipt.model_validate_json(
        committed_bytes
    )

    with tempfile.TemporaryDirectory(
        prefix="gma-stable-v1-committed-receipt-", ignore_cleanup_errors=True
    ) as temporary:
        temporary_root = Path(temporary)
        clone = temporary_root / "repository"
        stage = temporary_root / "candidate"
        rebuilt_receipt = temporary_root / "receipt.json"
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [
                git,
                "clone",
                "--no-checkout",
                receipt.source_repository,
                str(clone),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [git, "checkout", "--detach", receipt.source_commit],
            cwd=clone,
            check=True,
            capture_output=True,
        )

        build_candidate(clone, stage, rebuilt_receipt)

        assert rebuilt_receipt.read_bytes() == committed_bytes
        for role in (ArtifactRole.WHEEL, ArtifactRole.SDIST):
            result = consume_candidate(
                root=clone,
                stage=stage,
                receipt_path=rebuilt_receipt,
                artifact_role=role,
                environment=temporary_root / f"consumer-{role.value}",
            )
            assert result["state"] == "passed"
