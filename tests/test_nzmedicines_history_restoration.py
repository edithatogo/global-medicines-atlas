"""Tests for governed nzmedicines Git-bundle restoration."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path

import pytest
import scripts.verify_nzmedicines_history as restoration
from scripts.verify_nzmedicines_history import (
    RestorationError,
    verify_and_restore,
)


def run_git(*arguments: str, cwd: Path | None = None) -> str:
    git_executable = shutil.which("git")
    if git_executable is None:
        pytest.fail("Git executable is required for restoration tests")
    # ruff: ignore[subprocess-without-shell-equals-true]
    result = subprocess.run(
        [git_executable, *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    return result.stdout.strip()


@pytest.fixture
def bundle_fixture(tmp_path: Path) -> tuple[Path, str, str, Path]:
    source = tmp_path / "source"
    source.mkdir()
    run_git("init", "-b", "main", cwd=source)
    run_git("config", "user.name", "Fixture Author", cwd=source)
    run_git(
        "config",
        "user.email",
        "fixture@example.invalid",
        cwd=source,
    )
    (source / "README.md").write_text("fixture\n", encoding="utf-8")
    run_git("add", "README.md", cwd=source)
    run_git("commit", "-m", "fixture", cwd=source)
    commit = run_git("rev-parse", "HEAD", cwd=source)

    bundle = tmp_path / "history.bundle"
    run_git("bundle", "create", str(bundle), "--all", cwd=source)
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "README.md").write_bytes(b"fixture\n")
    return bundle, digest, commit, vendor


def test_restores_verified_bundle(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, digest, commit, source = bundle_fixture
    destination = tmp_path / "restored"

    receipt = verify_and_restore(
        bundle,
        destination,
        expected_sha256=digest,
        expected_size=bundle.stat().st_size,
        required_commit=commit,
        vendor_snapshot=source,
    )

    assert receipt["status"] == "verified"
    assert receipt["bundle_sha256"] == digest
    assert run_git("cat-file", "-t", commit, cwd=destination) == "commit"
    assert (destination / "README.md").read_text() == "fixture\n"


def test_accepts_existing_empty_destination(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, digest, commit, source = bundle_fixture
    destination = tmp_path / "empty"
    destination.mkdir()

    verify_and_restore(
        bundle,
        destination,
        expected_sha256=digest,
        expected_size=bundle.stat().st_size,
        required_commit=commit,
        vendor_snapshot=source,
    )

    assert (destination / ".git").is_dir()


def test_rejects_digest_mismatch_before_creating_destination(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, _, commit, source = bundle_fixture
    destination = tmp_path / "untouched"

    with pytest.raises(RestorationError, match="SHA-256 mismatch"):
        verify_and_restore(
            bundle,
            destination,
            expected_sha256="0" * 64,
            expected_size=bundle.stat().st_size,
            required_commit=commit,
            vendor_snapshot=source,
        )

    assert not destination.exists()


def test_rejects_size_mismatch_before_creating_destination(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, digest, commit, source = bundle_fixture
    destination = tmp_path / "untouched"

    with pytest.raises(RestorationError, match="size mismatch"):
        verify_and_restore(
            bundle,
            destination,
            expected_sha256=digest,
            expected_size=bundle.stat().st_size + 1,
            required_commit=commit,
            vendor_snapshot=source,
        )

    assert not destination.exists()


def test_rejects_missing_commit_before_creating_destination(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, digest, _, source = bundle_fixture
    destination = tmp_path / "untouched"

    with pytest.raises(RestorationError, match="Git command failed"):
        verify_and_restore(
            bundle,
            destination,
            expected_sha256=digest,
            expected_size=bundle.stat().st_size,
            required_commit="0" * 40,
            vendor_snapshot=source,
        )

    assert not destination.exists()


def test_rejects_nonempty_destination(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, digest, commit, source = bundle_fixture
    destination = tmp_path / "occupied"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(RestorationError, match="must be empty"):
        verify_and_restore(
            bundle,
            destination,
            expected_sha256=digest,
            expected_size=bundle.stat().st_size,
            required_commit=commit,
            vendor_snapshot=source,
        )

    assert sentinel.read_text() == "keep"


def test_rejects_unsafe_root_destination(
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, digest, commit, source = bundle_fixture
    root = Path(bundle.anchor)

    with pytest.raises(RestorationError, match="unsafe"):
        verify_and_restore(
            bundle,
            root,
            expected_sha256=digest,
            expected_size=bundle.stat().st_size,
            required_commit=commit,
            vendor_snapshot=source,
        )


def test_rejects_invalid_identity_values(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, _, _, source = bundle_fixture

    with pytest.raises(RestorationError, match="SHA-256"):
        verify_and_restore(
            bundle,
            tmp_path / "digest",
            expected_sha256="not-a-digest",
            expected_size=bundle.stat().st_size,
            vendor_snapshot=source,
        )

    with pytest.raises(RestorationError, match="commit"):
        verify_and_restore(
            bundle,
            tmp_path / "commit",
            expected_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),
            expected_size=bundle.stat().st_size,
            required_commit="not-a-commit",
            vendor_snapshot=source,
        )


def test_writes_portable_atomic_receipt_under_build(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, digest, commit, vendor = bundle_fixture
    build_root = tmp_path / "repository" / "build"
    monkeypatch.setattr(restoration, "BUILD_ROOT", build_root)
    receipt_path = build_root / "receipts" / "history.json"

    result = verify_and_restore(
        bundle,
        tmp_path / "restored",
        expected_sha256=digest,
        expected_size=bundle.stat().st_size,
        required_commit=commit,
        receipt_path=receipt_path,
        vendor_snapshot=vendor,
    )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt == result["receipt"]
    assert receipt["bundle"]["size_bytes"] == bundle.stat().st_size
    assert receipt["bundle"]["sha256"] == digest
    assert receipt["bundle"]["verify_status"] == "verified"
    assert receipt["required_commit"] == commit
    assert receipt["restored"]["head_commit"] == commit
    assert receipt["restored"]["head_tree"]
    assert receipt["vendor_snapshot_comparison"] == {
        "attribute_normalized_file_count": 0,
        "bytes": "exact-or-checkout-normalized",
        "checkout_attributes_applied": True,
        "file_count": 1,
        "membership": "exact",
        "raw_exact_file_count": 1,
        "tree_id": receipt["restored"]["required_commit_tree"],
    }
    assert receipt["git"]["platform"]
    assert receipt["git"]["version"].startswith("git version")
    assert receipt["observed_at"].endswith("+00:00")
    assert receipt["restricted_payloads"]["included_in_receipt"] is False
    assert str(bundle) not in receipt_path.read_text(encoding="utf-8")
    assert not list(receipt_path.parent.glob("*.tmp"))


def test_rejects_receipt_outside_build(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, digest, commit, vendor = bundle_fixture
    monkeypatch.setattr(
        restoration,
        "BUILD_ROOT",
        tmp_path / "repository" / "build",
    )

    with pytest.raises(RestorationError, match="beneath repository build"):
        verify_and_restore(
            bundle,
            tmp_path / "restored",
            expected_sha256=digest,
            expected_size=bundle.stat().st_size,
            required_commit=commit,
            receipt_path=tmp_path / "outside.json",
            vendor_snapshot=vendor,
        )


def test_rejects_vendor_membership_or_byte_mismatch(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, digest, commit, vendor = bundle_fixture
    (vendor / "README.md").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(RestorationError, match="byte mismatch"):
        verify_and_restore(
            bundle,
            tmp_path / "restored",
            expected_sha256=digest,
            expected_size=bundle.stat().st_size,
            required_commit=commit,
            vendor_snapshot=vendor,
        )


def test_git_bundle_verify_is_enforced(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, _, commit, vendor = bundle_fixture
    damaged = tmp_path / "damaged.bundle"
    damaged.write_bytes(bundle.read_bytes()[:-32])
    damaged_digest = hashlib.sha256(damaged.read_bytes()).hexdigest()

    with pytest.raises(RestorationError, match="Git command failed"):
        verify_and_restore(
            damaged,
            tmp_path / "restored",
            expected_sha256=damaged_digest,
            expected_size=damaged.stat().st_size,
            required_commit=commit,
            vendor_snapshot=vendor,
        )


def test_rejects_nested_destination_symlink(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, digest, commit, vendor = bundle_fixture
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this platform")

    with pytest.raises(RestorationError, match="symbolic-link component"):
        verify_and_restore(
            bundle,
            link / "restored",
            expected_sha256=digest,
            expected_size=bundle.stat().st_size,
            required_commit=commit,
            vendor_snapshot=vendor,
        )


def test_failed_post_clone_qualification_leaves_no_destination(
    tmp_path: Path,
    bundle_fixture: tuple[Path, str, str, Path],
) -> None:
    bundle, digest, commit, vendor = bundle_fixture
    destination = tmp_path / "restored"
    (vendor / "README.md").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(RestorationError, match="byte mismatch"):
        verify_and_restore(
            bundle,
            destination,
            expected_sha256=digest,
            expected_size=bundle.stat().st_size,
            required_commit=commit,
            vendor_snapshot=vendor,
        )

    assert not destination.exists()
    assert not list(tmp_path.glob(".restored.qualification-*"))
