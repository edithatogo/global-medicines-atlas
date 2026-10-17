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
_SHA256_HEX_LENGTH = 64
_ADMITTED_MBS_METADATA_KEYS = frozenset({
    b"schema_name",
    b"schema_version",
    b"qualification",
    b"input_admission_sha256",
    b"input_semantic_manifest_sha256",
    b"graph_sha256",
})


def _is_supported_edge_schema(edges: pa.Table) -> bool:
    """Accept only the pinned synthetic schemas or bound MBS v3 metadata."""
    if edges.schema.equals(MBS_GOLD_EDGE_SCHEMA, check_metadata=False):
        metadata = edges.schema.metadata or {}
        if metadata == MBS_GOLD_EDGE_SCHEMA.metadata:
            return True
        if frozenset(metadata) != _ADMITTED_MBS_METADATA_KEYS:
            return False
        return (
            metadata[b"schema_name"]
            == MBS_GOLD_EDGE_SCHEMA.metadata[b"schema_name"]
            and metadata[b"schema_version"] == b"3.0"
            and metadata[b"qualification"]
            == b"admitted_real_silver_candidate_only"
            and all(
                len(metadata[key]) == _SHA256_HEX_LENGTH
                and all(byte in b"0123456789abcdef" for byte in metadata[key])
                for key in _ADMITTED_MBS_METADATA_KEYS
                - {b"schema_name", b"schema_version", b"qualification"}
            )
        )
    return edges.schema.equals(PBS_GOLD_EDGE_SCHEMA, check_metadata=True)


def select_gold_edges(
    edges: pa.Table,
    *,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    kind: str | None = None,
    max_rows: int = MAX_EDGE_ROWS,
    offset: int = 0,
    allow_pagination: bool = False,
) -> pa.Table:
    """Select a deterministic bounded adjacency view from an admitted table."""
    if type(max_rows) is not int or isinstance(max_rows, bool) or max_rows < 1:
        raise ValueError("edge row bound must be a positive integer")
    if type(offset) is not int or isinstance(offset, bool) or offset < 0:
        raise ValueError("edge offset must be a non-negative integer")
    if not _is_supported_edge_schema(edges):
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
    if len(selected) > max_rows and not allow_pagination:
        raise ValueError("edge row bound exceeded")
    selected.sort(key=itemgetter("edge_id"))
    return pa.Table.from_pylist(
        selected[offset : offset + max_rows], schema=edges.schema
    )


def gold_edge_payload(
    edges: pa.Table,
    *,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    kind: str | None = None,
    max_rows: int = MAX_EDGE_ROWS,
    offset: int = 0,
    include_pagination: bool = False,
) -> dict[str, Any]:
    """Render a bounded structural edge page with decoded provenance fields."""
    selected = select_gold_edges(
        edges,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        kind=kind,
        max_rows=max_rows,
        offset=offset,
        allow_pagination=include_pagination,
    )
    items = selected.to_pylist()
    for item in items:
        item["evidence"] = json.loads(item.pop("evidence_json"))
        item["controls"] = json.loads(item.pop("controls_json"))
    payload: dict[str, Any] = {
        "schema_name": selected.schema.metadata[b"schema_name"].decode(),
        "schema_version": selected.schema.metadata[b"schema_version"].decode(),
        "qualification": selected.schema.metadata[b"qualification"].decode(),
        "total": len(items),
        "items": items,
    }
    metadata = selected.schema.metadata or {}
    if metadata.get(b"qualification") == b"admitted_real_silver_candidate_only":
        payload["admission_bindings"] = {
            "input_admission_sha256": metadata[
                b"input_admission_sha256"
            ].decode(),
            "input_semantic_manifest_sha256": metadata[
                b"input_semantic_manifest_sha256"
            ].decode(),
            "graph_sha256": metadata[b"graph_sha256"].decode(),
        }
    if include_pagination:
        matching_count = sum(
            1
            for row in edges.to_pylist()
            if (
                source_node_id is None
                or row["source_node_id"] == source_node_id
            )
            and (
                target_node_id is None
                or row["target_node_id"] == target_node_id
            )
            and (kind is None or row["kind"] == kind)
        )
        payload.update(
            offset=offset,
            has_more=offset + len(items) < matching_count,
        )
    return payload
