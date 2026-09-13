"""Bounded read-only adjacency queries over qualified Gold edge tables.

The view is deliberately structural: it preserves source evidence and review
controls, but does not infer temporal validity from an edge without declared
temporal fields. Temporal ``as_of`` queries belong to the typed temporal
assertion surface.
"""

from __future__ import annotations

import json
from operator import itemgetter
from typing import Any

import pyarrow as pa

from .mbs_gold_graph import MBS_GOLD_EDGE_SCHEMA
from .pbs_gold_graph import PBS_GOLD_EDGE_SCHEMA

MAX_SELECTOR_LENGTH = 512
MAX_EDGE_ROWS = 1_000


def select_gold_edges(
    edges: pa.Table,
    *,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    kind: str | None = None,
    max_rows: int = MAX_EDGE_ROWS,
) -> pa.Table:
    """Select a deterministic bounded adjacency view from an admitted table."""
    if type(max_rows) is not int or isinstance(max_rows, bool) or max_rows < 1:
        raise ValueError("edge row bound must be a positive integer")
    if not any(
        edges.schema.equals(schema, check_metadata=True)
        for schema in (MBS_GOLD_EDGE_SCHEMA, PBS_GOLD_EDGE_SCHEMA)
    ):
        raise ValueError("unsupported Gold edge schema")
    for name, value in (
        ("source_node_id", source_node_id),
        ("target_node_id", target_node_id),
        ("kind", kind),
    ):
        if value is not None and (
            type(value) is not str
            or not value
            or len(value) > MAX_SELECTOR_LENGTH
        ):
            raise ValueError(f"invalid {name} selector")
    selected = [
        row
        for row in edges.to_pylist()
        if (source_node_id is None or row["source_node_id"] == source_node_id)
        and (target_node_id is None or row["target_node_id"] == target_node_id)
        and (kind is None or row["kind"] == kind)
    ]
    if len(selected) > max_rows:
        raise ValueError("edge row bound exceeded")
    selected.sort(key=itemgetter("edge_id"))
    return pa.Table.from_pylist(selected, schema=edges.schema)


def gold_edge_payload(
    edges: pa.Table,
    *,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    kind: str | None = None,
    max_rows: int = MAX_EDGE_ROWS,
) -> dict[str, Any]:
    """Render a bounded structural edge page with decoded provenance fields."""
    selected = select_gold_edges(
        edges,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        kind=kind,
        max_rows=max_rows,
    )
    items = selected.to_pylist()
    for item in items:
        item["evidence"] = json.loads(item.pop("evidence_json"))
        item["controls"] = json.loads(item.pop("controls_json"))
    return {
        "schema_name": selected.schema.metadata[b"schema_name"].decode(),
        "schema_version": selected.schema.metadata[b"schema_version"].decode(),
        "qualification": selected.schema.metadata[b"qualification"].decode(),
        "total": len(items),
        "items": items,
    }
