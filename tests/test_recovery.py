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


def test_restore_publication_failure_recovers_predecessor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "state.txt").write_text("backup", encoding="utf-8")
    bundle = tmp_path / "bundle"
    create_backup(source, bundle)
    destination = tmp_path / "canonical"
    destination.mkdir()
    (destination / "state.txt").write_text("current", encoding="utf-8")
    original_replace = Path.replace
    publication_attempts = 0

    def fail_replacement(path: Path, target: Path) -> Path:
        nonlocal publication_attempts
        if path.name == "restored" and target == destination:
            publication_attempts += 1
            raise OSError("injected publication failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_replacement)

    with pytest.raises(RecoveryError, match="predecessor recovered"):
        restore_backup(bundle, destination)

    assert publication_attempts == 1
    assert (destination / "state.txt").read_text(encoding="utf-8") == "current"
    assert not destination.with_name(".canonical.rollback").exists()


@pytest.mark.parametrize("destination_state", ["absent", "existing"])
def test_restore_failure_never_leaves_canonical_destination_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    destination_state: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a").write_bytes(b"a")
    (source / "nested").mkdir()
    (source / "nested/b").write_bytes(b"b")
    bundle = tmp_path / "bundle"
    create_backup(source, bundle)
    destination = tmp_path / "canonical"
    if destination_state == "existing":
        destination.mkdir()
        (destination / "old").write_bytes(b"old")
    original_replace = Path.replace

    def fail_replacement(path: Path, target: Path) -> Path:
        if path.name == "restored" and target == destination:
            raise OSError("injected publication failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_replacement)

    with pytest.raises(RecoveryError, match="publication failed"):
        restore_backup(bundle, destination)

    if destination_state == "existing":
        assert sorted(path.name for path in destination.iterdir()) == ["old"]
    else:
        assert not destination.exists()
