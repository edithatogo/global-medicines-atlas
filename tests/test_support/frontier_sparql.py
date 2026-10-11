"""Disposable Oxigraph execution for synthetic RDF 1.2 Gold previews.

This test-only adapter does not admit graphs, resolve rights, or grant
production authority.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from global_medicines_atlas.frontier_graph_export import (
    GoldGraphExport,
    rdf_iri_reference,
)

_ENGINE_VERSION = "0.5.9"
_IMAGE_DIGEST = (
    "sha256:e68b3625743db4a4b18129a907ae36766f89bb6deeb8ab50d35685dbabe00b0e"
)
_QUERY_TIMEOUT_SECONDS = 10.0
_DISCOVERY_ATTEMPTS = 60
_NODE_QUERY = """
SELECT ?node ?payload WHERE {
  ?node <urn:gma:payload-json> ?payload .
  FILTER(STRSTARTS(STR(?node), "urn:gma:node:"))
}
"""
_EDGE_QUERY = """
SELECT ?source ?target ?edge ?edgeId ?payload WHERE {
  ?edge <urn:gma:source> ?source .
  ?edge <urn:gma:target> ?target .
  ?edge <urn:gma:edge-id> ?edgeId .
  ?edge <urn:gma:payload-json> ?payload .
}
"""
_REIFIED_EDGE_QUERY = """
VERSION "1.2"
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?edge ?source ?target WHERE {
  ?edge rdf:reifies <<( ?source <urn:gma:connects-to> ?target )>> .
}
ORDER BY STR(?edge)
"""


def execute_query(
    base_url: str,
    query: str,
    *,
    timeout: float = _QUERY_TIMEOUT_SECONDS,
) -> tuple[list[str], list[list[dict[str, str]]]]:
    """Execute one read-only query through the SPARQL 1.1 HTTP protocol."""
    url = f"{_root_url(base_url)}/query?default"
    request = Request(  # ruff: ignore[suspicious-url-open-usage] - root URL validated above
        url,
        data=query.encode("utf-8"),
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/sparql-query",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # ruff: ignore[suspicious-url-open-usage] - endpoint restricted to HTTP(S)
            payload = json.loads(response.read())
    except HTTPError as error:
        raise RuntimeError(
            f"SPARQL query failed with HTTP status {error.code}"
        ) from error
    except json.JSONDecodeError as error:
        raise ValueError("SPARQL query response is not valid JSON") from error
    if not isinstance(payload, dict):
        raise TypeError("SPARQL query response must be an object")
    document = cast("dict[str, object]", payload)
    head = document.get("head")
    result = document.get("results")
    if not isinstance(head, dict) or not isinstance(result, dict):
        raise TypeError("SPARQL query response has an invalid shape")
    variables = cast("dict[str, object]", head).get("vars")
    bindings = cast("dict[str, object]", result).get("bindings")
    if not isinstance(variables, list) or not isinstance(bindings, list):
        raise TypeError(
            "SPARQL query response is missing variables or bindings"
        )
    variable_names = cast("list[object]", variables)
    if any(not isinstance(variable, str) for variable in variable_names):
        raise TypeError("SPARQL query response has invalid variable names")
    rows: list[list[dict[str, str]]] = []
    for binding_object in cast("list[object]", bindings):
        if not isinstance(binding_object, dict):
            raise TypeError("SPARQL query binding must be an object")
        binding = cast("dict[str, object]", binding_object)
        row: list[dict[str, str]] = []
        for variable in cast("list[str]", variable_names):
            term = binding.get(variable)
            if not isinstance(term, dict):
                raise TypeError("SPARQL query binding is missing a term")
            term_object = cast("dict[str, object]", term)
            if not all(
                isinstance(term_object.get(key), str)
                for key in ("type", "value")
            ):
                raise TypeError("SPARQL query binding has an invalid term")
            row.append({
                "type": cast("str", term_object["type"]),
                "value": cast("str", term_object["value"]),
            })
        rows.append(row)
    return cast("list[str]", variables), rows


def qualify_graph_exports(
    base_url: str,
    exports: Mapping[str, tuple[GoldGraphExport, str]],
) -> dict[str, object]:
    """Execute previews in an initially empty, disposable Oxigraph store."""
    _wait_until_ready(base_url)
    fields, values = execute_query(
        base_url, "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
    )
    if fields != ["count"] or _result_literal(values, 0, 0) != "0":
        raise RuntimeError("Oxigraph experiment store must start empty")

    cases: dict[str, object] = {}
    for family, (export, rdf_graph) in sorted(exports.items()):
        if cases:
            _execute_update(base_url, "DELETE WHERE { ?s ?p ?o }")
        _load_graph(base_url, rdf_graph)
        if not verify_reified_edge_semantics(base_url, export):
            raise ValueError(
                f"SPARQL RDF 1.2 reified triple-term semantics differ for {family} fixture"
            )
        recovered = _read_graph(base_url)
        if _canonical_json(recovered) != export.reference_json:
            raise ValueError(
                f"SPARQL graph semantics differ for {family} fixture"
            )
        reference = _strict_object(export.reference_json)
        nodes = cast("list[object]", reference["nodes"])
        edges = cast("list[object]", reference["edges"])
        cases[family] = {
            "graph_sha256": hashlib.sha256(
                export.reference_json.encode("utf-8")
            ).hexdigest(),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "exact_payload_and_direction_parity": True,
            "rdf12_reified_triple_term_parity": True,
        }
    return {
        "schema_id": "global-medicines-atlas.oxigraph-synthetic-graph-parity",
        "schema_version": 1,
        "engine": "oxigraph",
        "engine_version": _ENGINE_VERSION,
        "engine_image_digest": _IMAGE_DIGEST,
        "api": "sparql-1.1-protocol-rdf-1.2",
        "rdf12_reification_query": "sparql-1.2-triple-term-pattern",
        "rdf12_reified_triple_term_parity": True,
        "disposition": "retain-preview",
        "source_scope": "synthetic-mbs-pbs-only",
        "source_payloads_accessed": False,
        "rights_clearance_claimed": False,
        "production_authority_promoted": False,
        "cases": cases,
    }


def verify_reified_edge_semantics(
    base_url: str,
    export: GoldGraphExport,
) -> bool:
    """Compare actual RDF 1.2 reified triple terms with directed Gold edges."""
    reference = _strict_object(export.reference_json)
    edges_object = reference.get("edges")
    if not isinstance(edges_object, list) or any(
        not isinstance(edge, dict)
        for edge in cast("list[object]", edges_object)
    ):
        raise TypeError("graph reference edges must be objects")
    edges = cast("list[dict[str, object]]", edges_object)
    expected: list[tuple[str, str, str]] = []
    for edge in edges:
        edge_id = edge.get("edge_id")
        source_id = edge.get("source_node_id")
        target_id = edge.get("target_node_id")
        if any(
            not isinstance(value, str) or not value
            for value in (edge_id, source_id, target_id)
        ):
            raise ValueError("graph reference edge has invalid RDF identity")
        expected.append((
            _iri_value("edge", cast("str", edge_id)),
            _iri_value("node", cast("str", source_id)),
            _iri_value("node", cast("str", target_id)),
        ))

    fields, rows = execute_query(base_url, _REIFIED_EDGE_QUERY)
    if fields != ["edge", "source", "target"]:
        raise ValueError("SPARQL reification query returned unexpected fields")
    observed = [(_uri(row, 0), _uri(row, 1), _uri(row, 2)) for row in rows]
    if sorted(observed) != sorted(expected):
        raise ValueError(
            "SPARQL RDF 1.2 reified triple-term semantics differ from directed edges"
        )
    return True


def _wait_until_ready(base_url: str) -> None:
    last_error: Exception | None = None
    for attempt in range(_DISCOVERY_ATTEMPTS):
        try:
            fields, values = execute_query(
                base_url,
                "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }",
                timeout=2.0,
            )
        except (OSError, URLError, RuntimeError, ValueError) as error:
            last_error = error
            if attempt + 1 < _DISCOVERY_ATTEMPTS:
                time.sleep(0.5)
        else:
            if fields != ["count"] or _result_literal(values, 0, 0) is None:
                raise RuntimeError(
                    "Oxigraph returned an invalid readiness result"
                )
            return
    raise RuntimeError("Oxigraph service did not become ready") from last_error


def _load_graph(base_url: str, rdf_star: str) -> None:
    url = f"{_root_url(base_url)}/store?default"
    request = Request(  # ruff: ignore[suspicious-url-open-usage] - root URL validated below
        url,
        data=rdf_star.encode("utf-8"),
        headers={"Content-Type": "application/n-triples"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=_QUERY_TIMEOUT_SECONDS) as response:  # ruff: ignore[suspicious-url-open-usage] - endpoint restricted to HTTP(S)
            response.read()
    except HTTPError as error:
        raise RuntimeError(
            f"RDF graph upload failed with HTTP status {error.code}"
        ) from error


def _execute_update(base_url: str, update: str) -> None:
    url = f"{_root_url(base_url)}/update?default"
    request = Request(  # ruff: ignore[suspicious-url-open-usage] - root URL validated below
        url,
        data=update.encode("utf-8"),
        headers={"Content-Type": "application/sparql-update"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=_QUERY_TIMEOUT_SECONDS) as response:  # ruff: ignore[suspicious-url-open-usage] - endpoint restricted to HTTP(S)
            response.read()
    except HTTPError as error:
        raise RuntimeError(
            f"SPARQL update failed with HTTP status {error.code}"
        ) from error


def _read_graph(base_url: str) -> dict[str, object]:
    return {
        "nodes": _read_nodes(base_url),
        "edges": _read_edges(base_url),
    }


def _read_nodes(base_url: str) -> list[dict[str, object]]:
    node_fields, node_rows = execute_query(base_url, _NODE_QUERY)
    if node_fields != ["node", "payload"]:
        raise ValueError("SPARQL node query returned unexpected fields")
    nodes: list[dict[str, object]] = []
    for row in node_rows:
        node_iri = _uri(row, 0)
        payload = _json_literal(row, 1)
        node = json.loads(payload)
        if not isinstance(node, dict):
            raise TypeError("SPARQL node payload must be a JSON object")
        node_row = cast("dict[str, object]", node)
        if node_iri != _iri_value(
            "node", cast("str", node_row.get("node_id", ""))
        ):
            raise ValueError("SPARQL node identity differs from its payload")
        nodes.append(node_row)

    nodes.sort(key=lambda row: cast("str", row["node_id"]))
    return nodes


def _read_edges(base_url: str) -> list[dict[str, object]]:
    edge_fields, edge_rows = execute_query(base_url, _EDGE_QUERY)
    if edge_fields != ["source", "target", "edge", "edgeId", "payload"]:
        raise ValueError("SPARQL edge query returned unexpected fields")
    edges: list[dict[str, object]] = []
    for row in edge_rows:
        source = _uri(row, 0)
        target = _uri(row, 1)
        edge = _uri(row, 2)
        edge_id = _literal(row, 3)
        payload = _json_literal(row, 4)
        decoded = json.loads(payload)
        if not isinstance(decoded, dict):
            raise TypeError("SPARQL edge payload must be a JSON object")
        edge_row = cast("dict[str, object]", decoded)
        if (
            not isinstance(edge_id, str)
            or edge != _iri_value("edge", edge_id)
            or edge_row.get("edge_id") != edge_id
            or source
            != _iri_value(
                "node", cast("str", edge_row.get("source_node_id", ""))
            )
            or target
            != _iri_value(
                "node", cast("str", edge_row.get("target_node_id", ""))
            )
        ):
            raise ValueError("SPARQL edge direction differs from its payload")
        edges.append(edge_row)
    edges.sort(key=lambda row: cast("str", row["edge_id"]))
    return edges


def _uri(row: list[dict[str, str]], index: int) -> str:
    term = row[index]
    if term.get("type") != "uri":
        raise TypeError("SPARQL binding must be a URI")
    return term["value"]


def _iri_value(kind: str, identifier: str) -> str:
    """Return the SPARQL result value for a generated RDF IRI."""
    return rdf_iri_reference(kind, identifier)[1:-1]


def _literal(row: list[dict[str, str]], index: int) -> str | None:
    term = row[index]
    if term.get("type") not in {"literal", "typed-literal"}:
        return None
    return term.get("value")


def _result_literal(
    rows: list[list[dict[str, str]]], row: int, column: int
) -> str | None:
    return _literal(rows[row], column)


def _json_literal(row: list[dict[str, str]], index: int) -> str:
    value = _literal(row, index)
    if value is None:
        raise TypeError("SPARQL payload binding must be a literal")
    return value


def _strict_object(value: str) -> dict[str, object]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise TypeError("graph export must be a JSON object")
    return cast("dict[str, object]", decoded)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _root_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("endpoint must be an HTTP(S) Oxigraph root URL")
    if not parsed.hostname:
        raise ValueError("endpoint must be an HTTP(S) Oxigraph root URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("endpoint must be an HTTP(S) Oxigraph root URL")
    if parsed.path not in {"", "/"}:
        raise ValueError("endpoint must be an HTTP(S) Oxigraph root URL")
    if parsed.query or parsed.fragment:
        raise ValueError("endpoint must be an HTTP(S) Oxigraph root URL")
    return f"{parsed.scheme}://{parsed.netloc}"
