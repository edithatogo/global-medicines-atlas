"""Aggregate stable-v1 reproduction, migration, and recovery rehearsal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from global_medicines_atlas.stable_v1_rehearsal import (
    StableV1RehearsalError,
    run_stable_v1_rehearsal,
    verify_receipt_content,
)


def test_stable_v1_rehearsal_is_deterministic_and_honest(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    first = run_stable_v1_rehearsal(first_path)
    second = run_stable_v1_rehearsal(second_path)

    assert first == second
    assert first.passed
    assert first.clean_room.boundary == "independent_local_fixture_process"
    assert first.clean_room.artifact_only_release_reproduction is False
    assert first.canonical.regulatory_funding_separation_verified
    assert first.canonical.rollback_exact
    assert first.recovery.production_disaster_recovery_qualified is False
    assert first.external_publication_verified is False
    assert verify_receipt_content(first)
    assert first_path.read_bytes() == second_path.read_bytes()
    assert json.loads(first_path.read_text(encoding="utf-8"))["passed"]


def test_rehearsal_receipt_detects_tampering(tmp_path: Path) -> None:
    receipt = run_stable_v1_rehearsal(tmp_path / "receipt.json")
    tampered = receipt.model_copy(
        update={
            "canonical": receipt.canonical.model_copy(
                update={"rollback_exact": False}
            )
        }
    )

    assert not verify_receipt_content(tampered)


def test_rehearsal_fails_closed_on_child_identity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "global_medicines_atlas.stable_v1_rehearsal._run_clean_process",
        lambda: {
            "canonical_v1_sha256": "0" * 64,
            "canonical_v2_sha256": "1" * 64,
        },
    )

    with pytest.raises(
        StableV1RehearsalError, match="clean-process reproduction"
    ):
        run_stable_v1_rehearsal(tmp_path / "receipt.json")

    assert not (tmp_path / "receipt.json").exists()
