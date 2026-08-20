from __future__ import annotations

from pathlib import Path

from global_medicines_atlas.free_tier_git_mechanics import run_git_mechanics


def test_git_mechanics_exercises_conflict_rollback_and_restore(
    tmp_path: Path,
) -> None:
    receipt = run_git_mechanics(tmp_path)
    assert all(receipt["operations"].values())
    assert receipt["commits"]["accepted"] == receipt["commits"]["restored"]
    assert receipt["inventory"]
    assert receipt["observed_experimental_rpo_seconds"] == 0
    assert receipt["observed_restore_seconds"] >= 0
    assert receipt["core_dependency_added"] is False
    assert "immutable_history" in receipt["claims_explicitly_not_established"]
    assert receipt["operations"]["retention_reference_verified"] is True
