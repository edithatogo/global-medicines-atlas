"""Deterministic semantic checks for portable graph preview projections.

This module is deliberately engine-free.  It checks that the NetworkX
round-trip, parameterised Cypher envelope and RDF-star preview all describe
the same canonical Gold graph.  A passing report is a local integrity result,
not a claim that a live engine or vocabulary has been qualified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, cast

from .frontier_graph_export import EDGE_STATEMENT, NODE_STATEMENT


@dataclass(frozen=True)
class GraphParityReport:
    """Content-addressed parity result across the three preview surfaces."""

    graph_sha256: str
    node_count: int
    edge_count: int
    networkx_checked: bool
    rdf_star_checked: bool
    cypher_checked: bool
    disposition: str = "retain-preview"


def validate_graph_previews(
    reference_json: str,
    parameters_json: str,
    rdf_star: str,
    *,
    networkx_recovered_json: str | None = None,
    node_statement: str = NODE_STATEMENT,
    edge_statement: str = EDGE_STATEMENT,
) -> GraphParityReport:
    """Validate exact payload and relationship parity across previews.

    JSON is parsed strictly and canonicalised before comparison.  RDF-star is
    checked as a set of canonical lines (ordering is not semantic), while
    the expected lines are generated from the reference graph.  No RDF or
    graph package is imported and no payload is persisted by this function.
    """
    reference = _document(reference_json, "reference")
    parameters = _document(parameters_json, "parameters")
    nodes = _rows(reference, "nodes")
    edges = _rows(reference, "edges")
    if node_statement != NODE_STATEMENT or edge_statement != EDGE_STATEMENT:
        raise ValueError("graph statements differ from the fixed safe template")
    expected_parameters = {
        "nodes": [
            {"node_id": row["node_id"], "payload_json": _json(row)}
            for row in nodes
        ],
        "edges": [
            {
                "edge_id": row["edge_id"],
                "source_node_id": row["source_node_id"],
                "target_node_id": row["target_node_id"],
                "payload_json": _json(row),
            }
            for row in edges
        ],
    }
    if parameters != expected_parameters:
        raise ValueError("Cypher parameter payload parity differs")
    expected_rdf = _rdf_lines(nodes, edges)
    actual_rdf = frozenset(line for line in rdf_star.splitlines() if line)
    if actual_rdf != frozenset(expected_rdf):
        raise ValueError("RDF-star payload or relationship parity differs")
    if (
        networkx_recovered_json is not None
        and _document(networkx_recovered_json, "NetworkX") != reference
    ):
        raise ValueError("NetworkX payload parity differs")
    canonical = _json(reference)
    return GraphParityReport(
        graph_sha256=sha256(canonical.encode("utf-8")).hexdigest(),
        node_count=len(nodes),
        edge_count=len(edges),
        networkx_checked=networkx_recovered_json is not None,
        rdf_star_checked=True,
        cypher_checked=True,
    )


def _document(value: str, label: str) -> dict[str, Any]:
    try:
        result = json.loads(value)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label} JSON") from error
    if not isinstance(result, dict) or set(cast("dict[str, Any]", result)) != {
        "nodes",
        "edges",
    }:
        raise ValueError(f"invalid {label} graph envelope")
    return cast("dict[str, Any]", result)


def _rows(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = document[key]
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) for row in cast("list[object]", rows)
    ):
        raise ValueError("graph rows must be objects")
    return cast("list[dict[str, Any]]", rows)


def _json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _rdf_id(kind: str, value: str) -> str:
    return (
        "<urn:gma:"
        + kind
        + ":"
        + value.replace("%", "%25").replace("#", "%23")
        + ">"
    )


def _rdf_lines(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> list[str]:
    lines = [
        f"{_rdf_id('node', row['node_id'])} <urn:gma:payload-json> {json.dumps(_json(row), ensure_ascii=True)} ."
        for row in nodes
    ]
    for row in edges:
        source, target = (
            _rdf_id("node", row["source_node_id"]),
            _rdf_id("node", row["target_node_id"]),
        )
        edge, quoted = (
            _rdf_id("edge", row["edge_id"]),
            f"<<{source} <urn:gma:connects-to> {target}>>",
        )
        lines.extend((
            f"{quoted} <urn:gma:edge-id> {json.dumps(row['edge_id'], ensure_ascii=True)} .",
            f"{quoted} <urn:gma:edge-resource> {edge} .",
            f"{edge} <urn:gma:payload-json> {json.dumps(_json(row), ensure_ascii=True)} .",
        ))
    return lines
