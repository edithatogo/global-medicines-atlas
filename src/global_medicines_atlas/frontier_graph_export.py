"""Offline lossless reference/Cypher export of portable candidate Gold tables.

Statements use fixed labels and parameter data, including JSON copies of every
portable field. Export is not graph admission, rights clearance or execution.
Use an isolated empty catalogue for experiments; engine parity is unqualified.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from operator import itemgetter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

from .mbs_gold_graph import MBS_GOLD_EDGE_SCHEMA, MBS_GOLD_NODE_SCHEMA
from .pbs_gold_graph import PBS_GOLD_EDGE_SCHEMA, PBS_GOLD_NODE_SCHEMA

NODE_STATEMENT = (
    "UNWIND $nodes AS row CREATE (n:GmaCandidate "
    "{node_id: row.node_id, payload_json: row.payload_json})"
)
EDGE_STATEMENT = (
    "UNWIND $edges AS row "
    "MATCH (s:GmaCandidate {node_id: row.source_node_id}), "
    "(t:GmaCandidate {node_id: row.target_node_id}) "
    "CREATE (s)-[:GMA_CANDIDATE "
    "{edge_id: row.edge_id, payload_json: row.payload_json}]->(t)"
)


@dataclass(frozen=True)
class GoldGraphExport:
    """Immutable export with SHA-256 over reference_json UTF-8 bytes only.

    The digest does not attest the statements or parameter envelope. No live
    engine execution or engine-parity qualification is implied.
    """

    reference_json: str
    parameters_json: str
    sha256: str
    node_statement: str = NODE_STATEMENT
    edge_statement: str = EDGE_STATEMENT


def export_rdf_star(
    nodes: pa.Table,
    edges: pa.Table,
    *,
    max_rows: int = 100_000,
    max_bytes: int = 64 * 1024 * 1024,
) -> str:
    """Return a deterministic RDF-star/N-Triples preview of Gold tables.

    The quoted edge statement carries the complete source row as a JSON
    literal, so this is a lossless, rebuildable projection rather than a
    semantic assertion.  It deliberately performs the same schema, identity,
    closure, and size checks as :func:`export_gold_tables`; no RDF engine or
    terminology vocabulary is required.
    """
    exported = export_gold_tables(
        nodes, edges, max_rows=max_rows, max_bytes=max_bytes
    )
    payload = json.loads(exported.reference_json)
    lines: list[str] = []
    for row in payload["nodes"]:
        subject = _rdf_id("node", row["node_id"])
        lines.append(
            f"{subject} <urn:gma:payload-json> {_rdf_literal(_json(row))} ."
        )
    for row in payload["edges"]:
        source = _rdf_id("node", row["source_node_id"])
        target = _rdf_id("node", row["target_node_id"])
        edge = _rdf_id("edge", row["edge_id"])
        quoted = f"<<{source} <urn:gma:connects-to> {target}>>"
        lines.extend((
            f"{quoted} <urn:gma:edge-id> {_rdf_literal(row['edge_id'])} .",
            f"{quoted} <urn:gma:edge-resource> {edge} .",
            f"{edge} <urn:gma:payload-json> {_rdf_literal(_json(row))} .",
        ))
    result = "\n".join(lines) + ("\n" if lines else "")
    if len(result.encode("utf-8")) > max_bytes:
        raise ValueError("serialized graph byte bound exceeded")
    return result


def _rdf_id(kind: str, value: str) -> str:
    return (
        "<urn:gma:"
        + kind
        + ":"
        + value.replace("%", "%25").replace("#", "%23")
        + ">"
    )


def _rdf_literal(value: str) -> str:
    # JSON string escaping is a valid conservative N-Triples string escape.
    return json.dumps(value, ensure_ascii=True)


def _json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def export_gold_tables(
    nodes: pa.Table,
    edges: pa.Table,
    *,
    max_rows: int = 100_000,
    max_bytes: int = 64 * 1024 * 1024,
) -> GoldGraphExport:
    """Preserve all fields from matching MBS/PBS portable table schemas.

    Reject schema drift, duplicate identities and dangling edges. Bounds apply
    before Arrow conversion and again to the serialized output. Rights and
    candidate controls remain unchanged in payload JSON; nothing is promoted.
    """
    if type(max_rows) is not int or type(max_bytes) is not int:
        raise ValueError("graph bounds must be integers")
    if max_rows < 1 or max_bytes < 1:
        raise ValueError("graph bounds must be positive")
    schemas = (
        (MBS_GOLD_NODE_SCHEMA, MBS_GOLD_EDGE_SCHEMA),
        (PBS_GOLD_NODE_SCHEMA, PBS_GOLD_EDGE_SCHEMA),
    )
    if not any(
        nodes.schema.equals(left, check_metadata=True)
        and edges.schema.equals(right, check_metadata=True)
        for left, right in schemas
    ):
        raise ValueError("unsupported or mismatched Gold schema")
    if nodes.num_rows + edges.num_rows > max_rows:
        raise ValueError("graph row bound exceeded")
    if nodes.nbytes + edges.nbytes > max_bytes:
        raise ValueError("graph byte bound exceeded")
    node_rows = nodes.to_pylist()
    edge_rows = edges.to_pylist()
    for rows, key in ((node_rows, "node_id"), (edge_rows, "edge_id")):
        ids = [row[key] for row in rows]
        if any(not isinstance(value, str) or not value for value in ids):
            raise ValueError("invalid graph identity")
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate graph identity")
        rows.sort(key=itemgetter(key))
    node_ids = {row["node_id"] for row in node_rows}
    if any(
        row["source_node_id"] not in node_ids
        or row["target_node_id"] not in node_ids
        for row in edge_rows
    ):
        raise ValueError("graph edge endpoint missing")
    reference = _json({"nodes": node_rows, "edges": edge_rows})
    parameters = _json({
        "nodes": [
            {"node_id": row["node_id"], "payload_json": _json(row)}
            for row in node_rows
        ],
        "edges": [
            {
                "edge_id": row["edge_id"],
                "source_node_id": row["source_node_id"],
                "target_node_id": row["target_node_id"],
                "payload_json": _json(row),
            }
            for row in edge_rows
        ],
    })
    if len(reference) + len(parameters) > max_bytes:
        raise ValueError("serialized graph byte bound exceeded")
    return GoldGraphExport(
        reference, parameters, hashlib.sha256(reference.encode()).hexdigest()
    )
