"""Bounded local configuration for read-only historical change inspection.

The document is an operator-provided transport input, not an admission record.
Each entry is revalidated as a ``HistoricalChange`` before it reaches the
shared paging service.  Loading performs no acquisition, persistence, or
publication.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field

from .historical_change import HistoricalChange, HistoricalChangeService
from .models import FrozenModel

MAX_HISTORY_EVIDENCE_BYTES = 4 * 1024 * 1024
MAX_HISTORY_EVIDENCE_CHANGES = 10_000


class HistoricalChangeDocument(FrozenModel):
    """A bounded, versioned sequence of already-computed observations."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["1.0"]
    changes: tuple[HistoricalChange, ...] = Field(
        max_length=MAX_HISTORY_EVIDENCE_CHANGES
    )


def _read(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError("historical evidence must be a regular file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("historical evidence must be a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            payload = stream.read(MAX_HISTORY_EVIDENCE_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(payload) > MAX_HISTORY_EVIDENCE_BYTES:
        raise ValueError("historical evidence exceeds byte bound")
    return payload


def load_historical_change_service(path: Path) -> HistoricalChangeService:
    """Load validated evidence into the shared bounded paging service."""
    document = HistoricalChangeDocument.model_validate_json(_read(path))
    return HistoricalChangeService(document.changes)


__all__ = [
    "MAX_HISTORY_EVIDENCE_BYTES",
    "MAX_HISTORY_EVIDENCE_CHANGES",
    "HistoricalChangeDocument",
    "load_historical_change_service",
]
