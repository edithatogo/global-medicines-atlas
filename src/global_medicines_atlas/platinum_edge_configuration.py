"""Bounded local loading of validated Gold edge projections."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .platinum_edges import MAX_EDGE_ROWS, select_gold_edges

MAX_EDGE_FILE_BYTES = 16 * 1024 * 1024


def load_gold_edges(
    path: Path,
    *,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    kind: str | None = None,
    max_rows: int = MAX_EDGE_ROWS,
) -> pa.Table:
    """Load one bounded regular Parquet file and validate its Gold schema."""
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        file_status = os.fstat(descriptor)
        if not stat.S_ISREG(file_status.st_mode):
            raise ValueError("Gold edge file must be regular")
        if file_status.st_size > MAX_EDGE_FILE_BYTES:
            raise ValueError("Gold edge file exceeds byte bound")
        filters = [
            (name, "=", value)
            for name, value in (
                ("source_node_id", source_node_id),
                ("target_node_id", target_node_id),
                ("kind", kind),
            )
            if value is not None
        ]
        table = pq.read_table(path, filters=filters or None)  # pyright: ignore[reportUnknownMemberType]
    finally:
        os.close(descriptor)
    return select_gold_edges(
        table,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        kind=kind,
        max_rows=max_rows,
    )
