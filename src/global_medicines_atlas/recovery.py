"""Deterministic backup, restore, and rollback for governed local artifacts."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath


class RecoveryError(ValueError):
    """A recovery bundle or operation failed validation."""


@dataclass(frozen=True, slots=True)
class RecoveryFile:
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class BackupReceipt:
    receipt_id: str
    files: tuple[RecoveryFile, ...]
    file_count: int
    total_bytes: int


@dataclass(frozen=True, slots=True)
class RestoreReceipt:
    backup_receipt_id: str
    destination: Path
    rollback_path: Path | None


def _digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _files(root: Path) -> tuple[RecoveryFile, ...]:
    if root.is_symlink() or not root.is_dir():
        raise RecoveryError("governed root must be a regular directory")
    files: list[RecoveryFile] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RecoveryError(f"symlink is forbidden: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RecoveryError(f"non-regular artifact is forbidden: {path}")
        digest, size = _digest_file(path)
        files.append(
            RecoveryFile(
                path=path.relative_to(root).as_posix(),
                sha256=digest,
                size_bytes=size,
            )
        )
    return tuple(files)


def _receipt(files: tuple[RecoveryFile, ...]) -> BackupReceipt:
    body = [asdict(item) for item in files]
    canonical = json.dumps(
        body, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    receipt_id = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return BackupReceipt(
        receipt_id=receipt_id,
        files=files,
        file_count=len(files),
        total_bytes=sum(item.size_bytes for item in files),
    )


def _receipt_bytes(receipt: BackupReceipt) -> bytes:
    return (
        json.dumps(
            asdict(receipt),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def create_backup(source: Path, bundle: Path) -> BackupReceipt:
    """Copy regular governed files into a deterministic recovery bundle."""
    if bundle.exists() or bundle.is_symlink():
        raise RecoveryError("backup destination must not exist")
    files = _files(source)
    receipt = _receipt(files)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=bundle.parent, prefix=f".{bundle.name}.backup-"
    ) as temporary:
        staging = Path(temporary)
        payload_root = staging / "payload"
        for item in files:
            relative = PurePosixPath(item.path)
            target = payload_root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.joinpath(*relative.parts).read_bytes())
        (staging / "receipt.json").write_bytes(_receipt_bytes(receipt))
        staging.replace(bundle)
    return receipt


def _load_backup(bundle: Path) -> BackupReceipt:
    if bundle.is_symlink() or not bundle.is_dir():
        raise RecoveryError("backup bundle must be a regular directory")
    try:
        raw = json.loads((bundle / "receipt.json").read_text(encoding="utf-8"))
        files = tuple(RecoveryFile(**item) for item in raw["files"])
        receipt = BackupReceipt(
            receipt_id=raw["receipt_id"],
            files=files,
            file_count=raw["file_count"],
            total_bytes=raw["total_bytes"],
        )
    except (KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        raise RecoveryError("backup receipt is invalid") from error
    if receipt != _receipt(files):
        raise RecoveryError("backup receipt digest is invalid")
    payload = bundle / "payload"
    if _files(payload) != files:
        raise RecoveryError("backup payload digest does not match receipt")
    return receipt


def restore_backup(bundle: Path, destination: Path) -> RestoreReceipt:
    """Atomically restore a verified backup and retain a rollback directory."""
    receipt = _load_backup(bundle)
    if destination.is_symlink():
        raise RecoveryError("restore destination must not be a symlink")
    destination.parent.mkdir(parents=True, exist_ok=True)
    rollback = destination.with_name(f".{destination.name}.rollback")
    if rollback.exists() or rollback.is_symlink():
        raise RecoveryError("rollback destination already exists")
    with tempfile.TemporaryDirectory(
        dir=destination.parent,
        prefix=f".{destination.name}.restore-",
    ) as temporary:
        staging = Path(temporary) / "restored"
        staging.mkdir()
        for item in receipt.files:
            relative = PurePosixPath(item.path)
            target = staging.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(
                bundle.joinpath("payload", *relative.parts).read_bytes()
            )
        if _files(staging) != receipt.files:
            raise RecoveryError("staged restore verification failed")
        if destination.exists():
            destination.replace(rollback)
        staging.replace(destination)
    return RestoreReceipt(
        backup_receipt_id=receipt.receipt_id,
        destination=destination,
        rollback_path=rollback if rollback.exists() else None,
    )


def rollback_restore(receipt: RestoreReceipt) -> None:
    """Replace a restored destination with its retained predecessor."""
    rollback = receipt.rollback_path
    if rollback is None or not rollback.is_dir() or rollback.is_symlink():
        raise RecoveryError("no valid rollback is available")
    failed = receipt.destination.with_name(
        f".{receipt.destination.name}.failed-restore"
    )
    if failed.exists() or failed.is_symlink():
        raise RecoveryError("failed-restore quarantine already exists")
    receipt.destination.replace(failed)
    rollback.replace(receipt.destination)
