"""Deterministic end-to-end rehearsal of governed local recovery."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field

from .models import FrozenModel
from .recovery import create_backup, restore_backup, rollback_restore

FIXTURE_FILE_COUNT = 2


class RecoveryRehearsalReceipt(FrozenModel):
    """Machine-readable proof of a complete local recovery cycle."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    evidence_class: Literal["synthetic_local_artifacts"] = (
        "synthetic_local_artifacts"
    )
    backup_receipt_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    original_tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    predecessor_tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    restored_tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rolled_back_tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    backup_verified: bool
    restore_verified: bool
    rollback_verified: bool
    failed_restore_quarantined: bool
    production_disaster_recovery_qualified: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=1)


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def rehearse_governed_recovery(output: Path) -> RecoveryRehearsalReceipt:
    """Create, restore, rollback, verify, and persist synthetic evidence."""

    with tempfile.TemporaryDirectory(prefix="gma-recovery-rehearsal-") as raw:
        root = Path(raw)
        governed = root / "governed"
        governed.mkdir()
        (governed / "catalog.json").write_text(
            '{"source":"synthetic","version":1}\n',
            encoding="utf-8",
        )
        nested = governed / "snapshots"
        nested.mkdir()
        (nested / "assertions.jsonl").write_text(
            '{"concept_id":"example","kind":"regulatory"}\n',
            encoding="utf-8",
        )
        original_digest = _tree_digest(governed)
        bundle = root / "backup"
        backup = create_backup(governed, bundle)

        (governed / "catalog.json").write_text(
            '{"source":"synthetic","version":2}\n',
            encoding="utf-8",
        )
        predecessor_digest = _tree_digest(governed)
        restore = restore_backup(bundle, governed)
        restored_digest = _tree_digest(governed)
        rollback_restore(restore)
        rolled_back_digest = _tree_digest(governed)
        failed_restore = governed.with_name(".governed.failed-restore")

        receipt = RecoveryRehearsalReceipt(
            backup_receipt_id=backup.receipt_id,
            original_tree_sha256=original_digest,
            predecessor_tree_sha256=predecessor_digest,
            restored_tree_sha256=restored_digest,
            rolled_back_tree_sha256=rolled_back_digest,
            backup_verified=(backup.file_count == FIXTURE_FILE_COUNT),
            restore_verified=(restored_digest == original_digest),
            rollback_verified=(rolled_back_digest == predecessor_digest),
            failed_restore_quarantined=failed_restore.is_dir(),
            limitations=(
                "The rehearsal covers deterministic local fixture artifacts.",
                (
                    "Independent storage, retention, RPO, RTO, and crash "
                    "consistency remain authority-gated production controls."
                ),
            ),
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            receipt.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt
