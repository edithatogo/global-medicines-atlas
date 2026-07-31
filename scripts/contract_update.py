"""Transactional helpers for governed dependency-contract updates."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path


class ContractUpdateError(RuntimeError):
    """A governed update failed and canonical recovery was incomplete."""

    def __init__(
        self,
        message: str,
        *,
        recovery_locations: Mapping[Path, Path],
    ) -> None:
        super().__init__(message)
        self.recovery_locations = dict(recovery_locations)


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _verify_content(path: Path, expected: bytes, *, label: str) -> None:
    if _digest(path.read_bytes()) != _digest(expected):
        raise OSError(f"{label} verification failed: {path}")


def _stage(updates: Mapping[Path, bytes]) -> dict[Path, Path]:
    staged: dict[Path, Path] = {}
    for path, content in updates.items():
        descriptor, temporary = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        os.close(descriptor)
        temporary_path = Path(temporary)
        temporary_path.write_bytes(content)
        staged[path] = temporary_path
    return staged


def _create_safeguards(
    originals: Mapping[Path, bytes],
    safeguards: dict[Path, Path],
) -> None:
    for path, content in originals.items():
        descriptor, temporary = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.predecessor.",
            suffix=".recovery",
        )
        os.close(descriptor)
        safeguard = Path(temporary)
        safeguard.write_bytes(content)
        safeguards[path] = safeguard
        _verify_content(safeguard, content, label="predecessor safeguard")


def _safeguard(originals: Mapping[Path, bytes]) -> dict[Path, Path]:
    safeguards: dict[Path, Path] = {}
    try:
        _create_safeguards(originals, safeguards)
    except Exception:
        for safeguard in safeguards.values():
            safeguard.unlink(missing_ok=True)
        raise
    return safeguards


def _verify_updates(updates: Mapping[Path, bytes]) -> None:
    for path, content in updates.items():
        _verify_content(path, content, label="published contract")


def _canonical_contracts_are_coherent(
    originals: Mapping[Path, bytes],
) -> bool:
    """Return true only when every canonical predecessor is readable and exact."""
    for path, content in originals.items():
        try:
            if not path.is_file() or _digest(path.read_bytes()) != _digest(
                content
            ):
                return False
        except OSError:
            return False
    return True


def replace_files_atomically(updates: Mapping[Path, bytes]) -> None:
    """Replace governed files, preserving verified recovery copies on failure."""
    originals = {path: path.read_bytes() for path in updates}
    staged = _stage(updates)
    safeguards = _safeguard(originals)
    replaced: list[Path] = []
    retain_safeguards = False
    try:
        for path, temporary_path in staged.items():
            os.replace(temporary_path, path)  # ruff: ignore[os-replace]
            replaced.append(path)
        _verify_updates(updates)
    except Exception as publication_error:
        restoration_errors: dict[Path, Exception] = {}
        for path in reversed(replaced):
            try:
                restoration = path.with_name(f".{path.name}.rollback")
                restoration.write_bytes(safeguards[path].read_bytes())
                os.replace(restoration, path)  # ruff: ignore[os-replace]
            except Exception as restoration_error:
                restoration_errors[path] = restoration_error

        if not _canonical_contracts_are_coherent(originals):
            retain_safeguards = True
            recovery_locations = dict(safeguards)
            affected = ", ".join(str(path) for path in originals)
            detail = "; ".join(
                f"{path}: {error}" for path, error in restoration_errors.items()
            )
            raise ContractUpdateError(
                f"governed update failed and canonical restoration was "
                f"incomplete for {affected}; verified predecessors are retained"
                + (f" ({detail})" if detail else ""),
                recovery_locations=recovery_locations,
            ) from publication_error
        raise
    finally:
        for temporary_path in staged.values():
            temporary_path.unlink(missing_ok=True)
        if not retain_safeguards:
            for safeguard in safeguards.values():
                safeguard.unlink(missing_ok=True)
