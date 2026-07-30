"""Transactional helpers for governed dependency-contract updates."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path


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


def replace_files_atomically(updates: Mapping[Path, bytes]) -> None:
    """Replace a small set of files and restore every predecessor on failure."""
    originals = {path: path.read_bytes() for path in updates}
    staged = _stage(updates)
    replaced: list[Path] = []
    try:
        for path, temporary_path in staged.items():
            os.replace(temporary_path, path)  # ruff: ignore[os-replace]
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            restoration = path.with_name(f".{path.name}.rollback")
            restoration.write_bytes(originals[path])
            os.replace(restoration, path)  # ruff: ignore[os-replace]
        raise
    finally:
        for temporary_path in staged.values():
            temporary_path.unlink(missing_ok=True)
