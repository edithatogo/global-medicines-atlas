from __future__ import annotations

import json
from pathlib import Path

import pytest

from global_medicines_atlas.recovery import (
    RecoveryError,
    create_backup,
    restore_backup,
    rollback_restore,
)

pytestmark = pytest.mark.integration


def test_backup_restore_and_rollback_are_content_addressed(
    tmp_path: Path,
) -> None:
    governed = tmp_path / "governed"
    governed.mkdir()
    (governed / "a.json").write_text('{"a":1}\n', encoding="utf-8")
    (governed / "nested").mkdir()
    (governed / "nested/b.txt").write_text("b\n", encoding="utf-8")
    bundle = tmp_path / "backup"

    backup = create_backup(governed, bundle)
    assert backup.file_count == 2
    assert json.loads((bundle / "receipt.json").read_text())["receipt_id"] == (
        backup.receipt_id
    )

    (governed / "a.json").write_text("changed\n", encoding="utf-8")
    restore = restore_backup(bundle, governed)
    assert (governed / "a.json").read_text(encoding="utf-8") == '{"a":1}\n'
    assert restore.rollback_path is not None

    rollback_restore(restore)
    assert (governed / "a.json").read_text(encoding="utf-8") == "changed\n"


def test_restore_rejects_tampering_and_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a").write_bytes(b"a")
    bundle = tmp_path / "bundle"
    create_backup(source, bundle)
    (bundle / "payload/a").write_bytes(b"tampered")

    with pytest.raises(RecoveryError, match="digest"):
        restore_backup(bundle, tmp_path / "target")

    link = source / "link"
    try:
        link.symlink_to(source / "a")
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(RecoveryError, match="symlink"):
        create_backup(source, tmp_path / "linked")
