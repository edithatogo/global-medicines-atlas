"""Verify and restore the preserved nzmedicines Git history."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast

EXPECTED_BUNDLE_SHA256: Final = (
    "f4414798f1b35558c69472d86d29b0b83facb2e799c9a20692b62fc889847223"
)
EXPECTED_BUNDLE_SIZE: Final = 37_832
REQUIRED_COMMIT: Final = "6a8ecfae67f15d635750d11d5f446b93d76c1865"
GIT_OBJECT_ID_LENGTH: Final = 40
SHA256_LENGTH: Final = 64
PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]
BUILD_ROOT: Final = PROJECT_ROOT / "build"
VENDOR_SNAPSHOT: Final = PROJECT_ROOT / "vendor" / "nzmedicines"


class RestorationError(RuntimeError):
    """Raised when history verification or restoration fails."""


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without modifying it."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_git_bytes(*arguments: str, cwd: Path | None = None) -> bytes:
    git_executable = shutil.which("git")
    if git_executable is None:
        raise RestorationError("Git executable is not available")
    # ruff: ignore[subprocess-without-shell-equals-true]
    result = subprocess.run(
        [git_executable, *arguments],
        cwd=cwd,
        check=False,
        capture_output=True,
        timeout=60,
        shell=False,
    )
    if result.returncode:
        detail_bytes = result.stderr.strip() or result.stdout.strip()
        detail = detail_bytes.decode(errors="replace")
        raise RestorationError(f"Git command failed: {detail}")
    return result.stdout


def _run_git(*arguments: str, cwd: Path | None = None) -> str:
    return (
        _run_git_bytes(
            *arguments,
            cwd=cwd,
        )
        .decode(errors="strict")
        .strip()
    )


def _validate_bundle_path(bundle_path: Path) -> Path:
    resolved = bundle_path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise RestorationError("Bundle path must identify a regular file")
    return resolved


def _validate_destination(destination: Path) -> Path:
    requested = destination.expanduser()
    _reject_symlink_components(requested)

    resolved = requested.resolve(strict=False)
    anchor = Path(resolved.anchor)
    if resolved == anchor:
        raise RestorationError("Filesystem roots are unsafe destinations")

    if resolved.exists():
        if not resolved.is_dir():
            raise RestorationError("Destination must be a directory")
        if any(resolved.iterdir()):
            raise RestorationError("Destination must be empty")
    else:
        parent = resolved.parent
        if not parent.exists() or not parent.is_dir():
            raise RestorationError(
                "Destination parent must be an existing directory"
            )
    return resolved


def _reject_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            raise RestorationError(
                f"Path contains a symbolic-link component: {current.name}"
            )


def _verify_commit_in_bundle(
    bundle_path: Path,
    required_commit: str,
) -> str:
    if len(required_commit) != GIT_OBJECT_ID_LENGTH:
        raise RestorationError("Required commit must be a full Git object ID")
    try:
        int(required_commit, 16)
    except ValueError as error:
        raise RestorationError(
            "Required commit must be a hexadecimal Git object ID"
        ) from error

    with tempfile.TemporaryDirectory(
        prefix="nzmedicines-bundle-verification-"
    ) as temporary:
        repository = Path(temporary) / "verification.git"
        _run_git("init", "--bare", str(repository))
        verification = _run_git(
            "bundle",
            "verify",
            str(bundle_path),
            cwd=repository,
        )
        _run_git(
            "fetch",
            "--quiet",
            str(bundle_path),
            "refs/*:refs/*",
            cwd=repository,
        )
        object_type = _run_git(
            "cat-file",
            "-t",
            required_commit,
            cwd=repository,
        )
        if object_type != "commit":
            raise RestorationError("Required object in bundle is not a commit")
        return verification


def _git_tree_entries(
    repository: Path,
    commit: str,
) -> dict[str, tuple[str, str]]:
    output = _run_git(
        "ls-tree",
        "-r",
        "--full-tree",
        commit,
        cwd=repository,
    )
    entries: dict[str, tuple[str, str]] = {}
    for line in output.splitlines():
        metadata, path = line.split("\t", maxsplit=1)
        mode, object_type, object_id = metadata.split()
        if object_type != "blob":
            raise RestorationError(
                f"Unsupported tree object {object_type} at {path}"
            )
        entries[path] = (mode, object_id)
    return entries


def _verify_vendor_snapshot(
    repository: Path,
    required_commit: str,
    vendor_snapshot: Path,
) -> dict[str, object]:
    vendor = vendor_snapshot.resolve(strict=True)
    if not vendor.is_dir():
        raise RestorationError("Vendor snapshot must be a directory")
    _reject_symlink_components(vendor_snapshot)

    tree_entries = _git_tree_entries(repository, required_commit)
    vendor_files = {
        path.relative_to(vendor).as_posix(): path
        for path in vendor.rglob("*")
        if path.is_file()
    }
    if set(tree_entries) != set(vendor_files):
        missing = sorted(set(tree_entries) - set(vendor_files))
        additional = sorted(set(vendor_files) - set(tree_entries))
        raise RestorationError(
            "Vendor snapshot membership mismatch: "
            f"missing={missing}, additional={additional}"
        )

    raw_exact_count = 0
    attribute_normalized_count = 0
    for relative_path, vendor_path in vendor_files.items():
        _, restored_object_id = tree_entries[relative_path]
        raw_object_id = _run_git(
            "hash-object",
            "--no-filters",
            str(vendor_path),
            cwd=PROJECT_ROOT,
        )
        if restored_object_id == raw_object_id:
            raw_exact_count += 1
            continue
        try:
            attribute_path = vendor_path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            attribute_path = relative_path
        vendor_object_id = _run_git(
            "hash-object",
            f"--path={attribute_path}",
            str(vendor_path),
            cwd=PROJECT_ROOT,
        )
        if restored_object_id != vendor_object_id:
            raise RestorationError(
                f"Vendor snapshot byte mismatch: {relative_path}"
            )
        attribute_normalized_count += 1

    tree_id = _run_git(
        "rev-parse",
        f"{required_commit}^{{tree}}",
        cwd=repository,
    )
    return {
        "file_count": len(vendor_files),
        "membership": "exact",
        "bytes": "exact-or-checkout-normalized",
        "checkout_attributes_applied": True,
        "raw_exact_file_count": raw_exact_count,
        "attribute_normalized_file_count": attribute_normalized_count,
        "tree_id": tree_id,
    }


def _validate_receipt_path(receipt_path: Path) -> Path:
    _reject_symlink_components(receipt_path)
    resolved = receipt_path.resolve(strict=False)
    build_root = BUILD_ROOT.resolve(strict=False)
    if not resolved.is_relative_to(build_root) or resolved == build_root:
        raise RestorationError(
            "Receipt path must be a file beneath repository build/"
        )
    if resolved.exists() and (resolved.is_dir() or resolved.is_symlink()):
        raise RestorationError("Receipt path must identify a regular file")
    return resolved


def _write_receipt_atomic(
    receipt_path: Path,
    payload: dict[str, object],
) -> None:
    destination = _validate_receipt_path(receipt_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(destination.parent)
    serialized = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _remove_staging_tree(path: Path) -> None:
    """Remove a temporary Git tree, including read-only object files."""

    def make_writable_and_retry(
        function: Callable[[str], object],
        failed_path: str,
        _error: BaseException,
    ) -> None:
        Path(failed_path).chmod(0o700)
        function(failed_path)

    shutil.rmtree(path, onexc=make_writable_and_retry)


def verify_and_restore(
    bundle_path: Path,
    destination: Path,
    *,
    expected_sha256: str = EXPECTED_BUNDLE_SHA256,
    expected_size: int = EXPECTED_BUNDLE_SIZE,
    required_commit: str = REQUIRED_COMMIT,
    receipt_path: Path | None = None,
    vendor_snapshot: Path = VENDOR_SNAPSHOT,
) -> dict[str, object]:
    """Verify a bundle and restore it into a safe, empty destination."""
    bundle = _validate_bundle_path(bundle_path)
    validated_receipt = (
        _validate_receipt_path(receipt_path)
        if receipt_path is not None
        else None
    )
    if len(expected_sha256) != SHA256_LENGTH:
        raise RestorationError("Expected SHA-256 must contain 64 characters")
    try:
        int(expected_sha256, 16)
    except ValueError as error:
        raise RestorationError(
            "Expected SHA-256 must be hexadecimal"
        ) from error

    actual_sha256 = sha256_file(bundle)
    if actual_sha256 != expected_sha256.lower():
        raise RestorationError(
            "Bundle SHA-256 mismatch: "
            f"expected {expected_sha256.lower()}, got {actual_sha256}"
        )
    actual_size = bundle.stat().st_size
    if expected_size < 0:
        raise RestorationError("Expected bundle size must not be negative")
    if actual_size != expected_size:
        raise RestorationError(
            f"Bundle size mismatch: expected {expected_size}, got {actual_size}"
        )

    bundle_verification = _verify_commit_in_bundle(
        bundle,
        required_commit.lower(),
    )
    target = _validate_destination(destination)
    target_existed = target.exists()
    staging_parent = Path(
        tempfile.mkdtemp(
            prefix=f".{target.name}.qualification-",
            dir=target.parent,
        )
    )
    staging = staging_parent / "restored"
    try:
        _run_git("clone", "--quiet", str(bundle), str(staging))
        restored_commit_type = _run_git(
            "cat-file",
            "-t",
            required_commit.lower(),
            cwd=staging,
        )
        if restored_commit_type != "commit":
            raise RestorationError("Restored repository lacks required commit")

        restored_head = _run_git("rev-parse", "HEAD", cwd=staging)
        restored_head_tree = _run_git(
            "rev-parse",
            "HEAD^{tree}",
            cwd=staging,
        )
        vendor_comparison = _verify_vendor_snapshot(
            staging,
            required_commit.lower(),
            vendor_snapshot,
        )
        if target_existed:
            target.rmdir()
        staging.replace(target)
    finally:
        _remove_staging_tree(staging_parent)
    receipt: dict[str, object] = {
        "schema_version": "1",
        "status": "verified",
        "observed_at": datetime.now(UTC).isoformat(),
        "command_contract": {
            "command": "verify_nzmedicines_history.py",
            "bundle_argument": "explicit external path",
            "destination_argument": "explicit empty path",
            "receipt_argument": "optional repository build path",
        },
        "bundle": {
            "sha256": actual_sha256,
            "size_bytes": actual_size,
            "verify_status": "verified",
        },
        "git": {
            "platform": platform.system(),
            "version": _run_git("--version"),
        },
        "required_commit": required_commit.lower(),
        "restored": {
            "head_commit": restored_head,
            "head_tree": restored_head_tree,
            "required_commit_tree": cast(
                "str",
                vendor_comparison["tree_id"],
            ),
        },
        "vendor_snapshot_comparison": vendor_comparison,
        "bundle_verify_output_sha256": hashlib.sha256(
            bundle_verification.encode()
        ).hexdigest(),
        "restricted_payloads": {
            "included_in_receipt": False,
            "statement": (
                "No restricted medicine payload is copied into this receipt."
            ),
        },
    }
    if validated_receipt is not None:
        _write_receipt_atomic(validated_receipt, receipt)

    return {
        "bundle_path": str(bundle),
        "bundle_sha256": actual_sha256,
        "destination": str(target),
        "required_commit": required_commit.lower(),
        "status": "verified",
        "receipt": receipt,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument(
        "--expected-sha256",
        default=EXPECTED_BUNDLE_SHA256,
    )
    parser.add_argument(
        "--expected-size",
        default=EXPECTED_BUNDLE_SIZE,
        type=int,
    )
    parser.add_argument("--required-commit", default=REQUIRED_COMMIT)
    parser.add_argument("--receipt", type=Path)
    return parser


def main() -> int:
    """Run the restoration verifier CLI."""
    arguments = _parser().parse_args()
    try:
        receipt = verify_and_restore(
            arguments.bundle,
            arguments.destination,
            expected_sha256=arguments.expected_sha256,
            expected_size=arguments.expected_size,
            required_commit=arguments.required_commit,
            receipt_path=arguments.receipt,
        )
    except (OSError, RestorationError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}))
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
