"""End-to-end governed recovery rehearsal."""

from __future__ import annotations

import json
from pathlib import Path

from global_medicines_atlas.recovery_rehearsal import (
    RecoveryRehearsalReceipt,
    rehearse_governed_recovery,
)


def test_rehearsal_proves_restore_and_rollback_without_overclaim(
    tmp_path: Path,
) -> None:
    output = tmp_path / "receipt.json"
    receipt = rehearse_governed_recovery(output)
    assert receipt.backup_verified
    assert receipt.restore_verified
    assert receipt.rollback_verified
    assert receipt.failed_restore_quarantined
    assert receipt.original_tree_sha256 == receipt.restored_tree_sha256
    assert receipt.predecessor_tree_sha256 == receipt.rolled_back_tree_sha256
    assert not receipt.production_disaster_recovery_qualified
    assert (
        RecoveryRehearsalReceipt.model_validate_json(
            output.read_text(encoding="utf-8")
        )
        == receipt
    )
    assert json.loads(output.read_text())["evidence_class"] == (
        "synthetic_local_artifacts"
    )
