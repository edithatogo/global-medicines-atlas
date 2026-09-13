"""Bounded local loading of validated Gold edge projections."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .platinum_edges import MAX_EDGE_ROWS, select_gold_edges

MAX_EDGE_FILE_BYTES = 16 * 1024 * 1024


def load_gold_edges(path: Path) -> pa.Table:
    """Load one bounded regular Parquet file and validate its Gold schema."""
    if not path.is_file() or path.stat().st_size > MAX_EDGE_FILE_BYTES:
        raise ValueError("Gold edge file is invalid or exceeds byte bound")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("Gold edge file must be regular")
        table = pq.read_table(path)  # pyright: ignore[reportUnknownMemberType]
    finally:
        os.close(descriptor)
    return select_gold_edges(table, max_rows=MAX_EDGE_ROWS)
