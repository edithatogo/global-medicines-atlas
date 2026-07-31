from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

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


def test_rollback_publication_failure_recovers_active_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, destination = _recovery_fixture(tmp_path)
    receipt = restore_backup(bundle, destination)
    assert receipt.rollback_path is not None
    original_replace = Path.replace

    def fail_rollback_publication(path: Path, target: Path) -> Path:
        if path == receipt.rollback_path and target == destination:
            raise OSError("injected rollback publication failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_rollback_publication)

    with pytest.raises(RecoveryError, match="active destination recovered"):
        rollback_restore(receipt)

    assert (destination / "state.txt").read_text(encoding="utf-8") == "backup"
    assert (receipt.rollback_path / "state.txt").read_text(
        encoding="utf-8"
    ) == "current"
    assert not destination.with_name(".canonical.failed-restore").exists()


def test_compounded_rollback_failure_uses_active_safeguard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, destination = _recovery_fixture(tmp_path)
    receipt = restore_backup(bundle, destination)
    assert receipt.rollback_path is not None
    failed = destination.with_name(".canonical.failed-restore")
    original_replace = Path.replace

    def fail_primary_compensation(path: Path, target: Path) -> Path:
        if target == destination and path in {receipt.rollback_path, failed}:
            raise OSError(f"injected failure for {path.name}")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_primary_compensation)

    with pytest.raises(
        RecoveryError, match="verified active safeguard recovered"
    ):
        rollback_restore(receipt)

    assert (destination / "state.txt").read_text(encoding="utf-8") == "backup"
    assert (failed / "state.txt").read_text(encoding="utf-8") == "backup"
    assert (receipt.rollback_path / "state.txt").read_text(
        encoding="utf-8"
    ) == "current"


def test_rollback_quarantine_failure_retains_canonical_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, destination = _recovery_fixture(tmp_path)
    receipt = restore_backup(bundle, destination)
    failed = destination.with_name(".canonical.failed-restore")
    original_replace = Path.replace

    def fail_quarantine(path: Path, target: Path) -> Path:
        if path == destination and target == failed:
            raise OSError("injected quarantine failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_quarantine)

    with pytest.raises(RecoveryError, match="canonical retained"):
        rollback_restore(receipt)

    assert (destination / "state.txt").read_text(encoding="utf-8") == "backup"
    assert not failed.exists()


def test_rollback_retries_transient_quarantine_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, destination = _recovery_fixture(tmp_path)
    receipt = restore_backup(bundle, destination)
    failed = destination.with_name(".canonical.failed-restore")
    original_replace = Path.replace
    attempts = 0

    def fail_once(path: Path, target: Path) -> Path:
        nonlocal attempts
        if path == destination and target == failed:
            attempts += 1
            if attempts == 1:
                raise PermissionError("injected transient sharing violation")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_once)
    monkeypatch.setattr(
        "global_medicines_atlas.recovery.time.sleep", lambda _: None
    )

    rollback_restore(receipt)

    assert attempts == 2
    assert (destination / "state.txt").read_text(encoding="utf-8") == "current"


def test_rollback_rejects_existing_failed_restore_quarantine(
    tmp_path: Path,
) -> None:
    bundle, destination = _recovery_fixture(tmp_path)
    receipt = restore_backup(bundle, destination)
    failed = destination.with_name(".canonical.failed-restore")
    failed.mkdir()

    with pytest.raises(RecoveryError, match="quarantine already exists"):
        rollback_restore(receipt)

    assert (destination / "state.txt").read_text(encoding="utf-8") == "backup"
    assert receipt.rollback_path is not None
    assert (receipt.rollback_path / "state.txt").read_text(
        encoding="utf-8"
    ) == "current"


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


def _recovery_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "state.txt").write_text("backup", encoding="utf-8")
    bundle = tmp_path / "bundle"
    create_backup(source, bundle)
    destination = tmp_path / "canonical"
    destination.mkdir()
    (destination / "state.txt").write_text("current", encoding="utf-8")
    return bundle, destination


def test_first_rename_failure_keeps_verified_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, destination = _recovery_fixture(tmp_path)
    original_replace = Path.replace

    def fail_first(path: Path, target: Path) -> Path:
        if path == destination:
            raise OSError("injected predecessor staging failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_first)
    with pytest.raises(RecoveryError, match="canonical predecessor retained"):
        restore_backup(bundle, destination)
    assert (destination / "state.txt").read_text(encoding="utf-8") == "current"


def test_compounded_publication_and_rollback_failures_use_safeguard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, destination = _recovery_fixture(tmp_path)
    original_replace = Path.replace

    def fail_primary_paths(path: Path, target: Path) -> Path:
        if target == destination and path.name in {
            "restored",
            ".canonical.rollback",
        }:
            raise OSError(f"injected failure for {path.name}")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_primary_paths)
    with pytest.raises(
        RecoveryError, match="verified predecessor safeguard recovered"
    ):
        restore_backup(bundle, destination)
    assert (destination / "state.txt").read_text(encoding="utf-8") == "current"
    rollback = destination.with_name(".canonical.rollback")
    assert (rollback / "state.txt").read_text(encoding="utf-8") == "current"


def test_cleanup_failure_does_not_invalidate_verified_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, destination = _recovery_fixture(tmp_path)

    def fail_cleanup(path: Path) -> None:
        raise OSError(f"injected cleanup failure: {path}")

    monkeypatch.setattr(shutil, "rmtree", fail_cleanup)
    receipt = restore_backup(bundle, destination)
    assert receipt.rollback_path is not None
    assert (destination / "state.txt").read_text(encoding="utf-8") == "backup"
    assert (receipt.rollback_path / "state.txt").read_text(
        encoding="utf-8"
    ) == "current"


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    fail_first=st.booleans(),
    fail_publication=st.booleans(),
    fail_primary_rollback=st.booleans(),
)
def test_bounded_restore_failure_state_machine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_first: bool,
    fail_publication: bool,
    fail_primary_rollback: bool,
) -> None:
    case_root = Path(tempfile.mkdtemp(dir=tmp_path, prefix="recovery-state-"))
    bundle, destination = _recovery_fixture(case_root)
    original_replace = Path.replace

    def inject(path: Path, target: Path) -> Path:
        if fail_first and path == destination:
            raise OSError("first")
        if (
            fail_publication
            and path.name == "restored"
            and target == destination
        ):
            raise OSError("publication")
        if (
            fail_primary_rollback
            and path.name == ".canonical.rollback"
            and target == destination
        ):
            raise OSError("rollback")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", inject)
    if fail_first or fail_publication:
        with pytest.raises(RecoveryError):
            restore_backup(bundle, destination)
        assert (destination / "state.txt").read_text(
            encoding="utf-8"
        ) == "current"
    else:
        restore_backup(bundle, destination)
        assert (destination / "state.txt").read_text(
            encoding="utf-8"
        ) == "backup"
