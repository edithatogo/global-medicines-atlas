"""Optional offline NetworkX execution with portable Gold query parity.

No production dependency is introduced: importing this module does not import
NetworkX. Execution is a bounded preview experiment, not graph admission.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from operator import itemgetter
from typing import TYPE_CHECKING, Any

from .frontier_graph_export import export_gold_tables

if TYPE_CHECKING:
    import pyarrow as pa

MAX_NODES = 1000
MAX_ROWS = 10000


@dataclass(frozen=True)
class NetworkXParity:
    """Deterministic engine execution evidence over one exact reference graph."""

    source_sha256: str
    engine_version: str
    recovered_json: str
    query_json: str
    disposition: str = "retain-preview"


def _json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _reachable(start: str, adjacency: dict[str, set[str]]) -> list[str]:
    seen = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        unseen = adjacency[current] - seen
        seen.update(unseen)
        pending.extend(unseen)
    return sorted(seen - {start})


def qualify_networkx_graph(nodes: pa.Table, edges: pa.Table) -> NetworkXParity:
    """Execute directed multigraph roundtrip and reachability/degree queries.

    Every portable field remains payload data, including null confidence,
    candidate/review state and restrictions. Pure Python table traversal is
    the independent query oracle; NetworkX answers must match exactly for
    every node. Parallel edges retain their source-native edge identifiers.
    """
    if nodes.num_rows > MAX_NODES:
        raise ValueError("NetworkX all-node query bound exceeded")
    export = export_gold_tables(nodes, edges, max_rows=MAX_ROWS)
    try:
        nx = importlib.import_module("networkx")
    except ModuleNotFoundError as error:
        raise RuntimeError("optional NetworkX engine is unavailable") from error
    source: dict[str, Any] = json.loads(export.reference_json)
    graph = nx.MultiDiGraph()
    forward: dict[str, set[str]] = {}
    reverse: dict[str, set[str]] = {}
    in_degree: dict[str, int] = {}
    out_degree: dict[str, int] = {}
    for row in source["nodes"]:
        node = row["node_id"]
        graph.add_node(node, payload=row)
        forward[node], reverse[node] = set(), set()
        in_degree[node] = out_degree[node] = 0
    for row in source["edges"]:
        left, right = row["source_node_id"], row["target_node_id"]
        graph.add_edge(left, right, key=row["edge_id"], payload=row)
        forward[left].add(right)
        reverse[right].add(left)
        out_degree[left] += 1
        in_degree[right] += 1
    recovered = {
        "nodes": sorted(
            (data["payload"] for _, data in graph.nodes(data=True)),
            key=itemgetter("node_id"),
        ),
        "edges": sorted(
            (
                data["payload"]
                for _, _, _, data in graph.edges(keys=True, data=True)
            ),
            key=itemgetter("edge_id"),
        ),
    }
    if recovered != source:
        raise ValueError("NetworkX lost portable Gold fields or identities")
    queries: dict[str, Any] = {}
    for node in sorted(forward):
        expected = {
            "descendants": _reachable(node, forward),
            "ancestors": _reachable(node, reverse),
            "in_degree": in_degree[node],
            "out_degree": out_degree[node],
        }
        observed = {
            "descendants": sorted(nx.descendants(graph, node)),
            "ancestors": sorted(nx.ancestors(graph, node)),
            "in_degree": graph.in_degree(node),
            "out_degree": graph.out_degree(node),
        }
        if observed != expected:
            raise ValueError("NetworkX directed query semantics differ")
        queries[node] = observed
    return NetworkXParity(
        export.sha256, str(nx.__version__), _json(recovered), _json(queries)
    )
