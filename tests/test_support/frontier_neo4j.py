"""Disposable Neo4j execution for synthetic portable Gold graph previews.

This experiment exercises the fixed parameterized Cypher projection against
an isolated Neo4j database. It is not graph admission, rights clearance, or
production engine qualification.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from typing import cast
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from global_medicines_atlas.frontier_graph_export import GoldGraphExport

_QUERY_TIMEOUT_SECONDS = 10.0
_DISCOVERY_ATTEMPTS = 60


def execute_query(
    base_url: str,
    statement: str,
    parameters: Mapping[str, object],
    *,
    timeout: float = _QUERY_TIMEOUT_SECONDS,
) -> tuple[list[str], list[list[object]]]:
    """Execute one parameterized statement through Neo4j Query API v2."""
    url = _query_url(base_url)
    body = json.dumps(
        {"statement": statement, "parameters": parameters},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    request = Request(  # ruff: ignore[suspicious-url-open-usage] - root URL validated below
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    payload = _read_json(request, timeout)
    if not isinstance(payload, dict):
        raise TypeError("Neo4j query response must be an object")
    document = cast("dict[str, object]", payload)
    errors = document.get("errors", [])
    if errors:
        if not isinstance(errors, list):
            raise TypeError("Neo4j query errors must be a list")
        codes = [
            cast("dict[str, object]", error).get("code", "unknown")
            for error in cast("list[object]", errors)
            if isinstance(error, dict)
        ]
        raise RuntimeError(f"Neo4j query failed: {codes}")
    result = document.get("data")
    if result is None and document.get("queryType") in {"rw", "w", "s"}:
        return [], []
    if not isinstance(result, dict):
        raise TypeError("Neo4j query response has no result data")
    return _tabular_data(cast("dict[str, object]", result))


def _tabular_data(
    data: dict[str, object],
) -> tuple[list[str], list[list[object]]]:
    fields_object = data.get("fields")
    values_object = data.get("values")
    if not isinstance(fields_object, list) or not isinstance(
        values_object, list
    ):
        raise TypeError("Neo4j query result has an invalid tabular shape")
    fields = cast("list[object]", fields_object)
    if any(not isinstance(field, str) for field in fields):
        raise TypeError("Neo4j query result has invalid field names")
    rows: list[list[object]] = []
    for row_object in cast("list[object]", values_object):
        if not isinstance(row_object, list):
            raise TypeError("Neo4j query result row must be a list")
        row = cast("list[object]", row_object)
        if len(row) != len(fields):
            raise TypeError("Neo4j query result row width differs from fields")
        rows.append(row)
    return cast("list[str]", fields), rows


def qualify_graph_exports(
    base_url: str,
    exports: Mapping[str, GoldGraphExport],
) -> dict[str, object]:
    """Execute and compare exports in an initially empty disposable database."""
    engine_version = _discover_version(base_url)
    fields, values = execute_query(
        base_url, "MATCH (n) RETURN count(n) AS count", {}
    )
    if fields != ["count"] or values != [[0]]:
        raise RuntimeError("Neo4j experiment database must start empty")

    cases: dict[str, object] = {}
    try:
        for family, export in sorted(exports.items()):
            cases[family] = _qualify_one_export(base_url, family, export)
    finally:
        execute_query(
            base_url,
            "MATCH (n:GmaCandidate) DETACH DELETE n",
            {},
        )
    return {
        "schema_id": "global-medicines-atlas.neo4j-synthetic-graph-parity",
        "schema_version": 1,
        "engine": "neo4j",
        "engine_version": engine_version,
        "api": "query-v2",
        "disposition": "retain-preview",
        "source_scope": "synthetic-mbs-pbs-only",
        "source_payloads_accessed": False,
        "rights_clearance_claimed": False,
        "production_authority_promoted": False,
        "cases": cases,
    }


def _qualify_one_export(
    base_url: str, family: str, export: GoldGraphExport
) -> dict[str, object]:
    reference = _strict_object(export.reference_json)
    node_rows = reference.get("nodes")
    edge_rows = reference.get("edges")
    parameters = _strict_object(export.parameters_json)
    nodes_object = parameters.get("nodes")
    edges_object = parameters.get("edges")
    if not isinstance(nodes_object, list) or not isinstance(edges_object, list):
        raise TypeError("Neo4j export parameters have invalid rows")
    if not isinstance(node_rows, list) or not isinstance(edge_rows, list):
        raise TypeError("Neo4j reference graph has invalid rows")
    nodes = cast("list[object]", nodes_object)
    edges = cast("list[object]", edges_object)
    typed_node_rows = cast("list[object]", node_rows)
    typed_edge_rows = cast("list[object]", edge_rows)

    execute_query(base_url, "MATCH (n:GmaCandidate) DETACH DELETE n", {})
    execute_query(base_url, export.node_statement, {"nodes": nodes})
    execute_query(base_url, export.edge_statement, {"edges": edges})
    recovered = _read_graph(base_url)
    if _canonical_json(recovered) != export.reference_json:
        raise ValueError(f"Neo4j graph semantics differ for {family} fixture")
    return {
        "graph_sha256": hashlib.sha256(
            export.reference_json.encode("utf-8")
        ).hexdigest(),
        "node_count": len(typed_node_rows),
        "edge_count": len(typed_edge_rows),
        "exact_payload_and_direction_parity": True,
    }


def _query_url(base_url: str) -> str:
    return f"{_root_url(base_url)}/db/neo4j/query/v2"


def _root_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("endpoint must be an HTTP(S) Neo4j root URL")
    if not parsed.hostname:
        raise ValueError("endpoint must be an HTTP(S) Neo4j root URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("endpoint must be an HTTP(S) Neo4j root URL")
    if parsed.path not in {"", "/"}:
        raise ValueError("endpoint must be an HTTP(S) Neo4j root URL")
    if parsed.query or parsed.fragment:
        raise ValueError("endpoint must be an HTTP(S) Neo4j root URL")
    return f"{parsed.scheme}://{parsed.netloc}"


def _discover_version(base_url: str) -> str:
    url = f"{_root_url(base_url)}/"
    last_error: Exception | None = None
    for attempt in range(_DISCOVERY_ATTEMPTS):
        try:
            payload = _get_discovery(url)
        except (OSError, URLError, json.JSONDecodeError) as error:
            last_error = error
            if attempt + 1 < _DISCOVERY_ATTEMPTS:
                time.sleep(0.5)
        else:
            return _discovery_version(payload)
    raise RuntimeError("Neo4j service did not become ready") from last_error


def _get_discovery(url: str) -> object:
    request = Request(  # ruff: ignore[suspicious-url-open-usage] - root URL validated below
        url, headers={"Accept": "application/json"}
    )
    return _read_json(request, timeout=2.0)


def _read_json(request: Request, timeout: float) -> object:
    with urlopen(request, timeout=timeout) as response:  # ruff: ignore[suspicious-url-open-usage] - endpoint restricted to HTTP(S)
        return json.loads(response.read())


def _discovery_version(payload: object) -> str:
    if not isinstance(payload, dict):
        raise TypeError("Neo4j discovery response must be an object")
    version = cast("dict[str, object]", payload).get("neo4j_version")
    if not isinstance(version, str):
        raise TypeError("Neo4j discovery version must be a string")
    if not version:
        raise ValueError("Neo4j discovery omitted its engine version")
    return version


def _read_graph(base_url: str) -> dict[str, object]:
    fields, values = execute_query(
        base_url,
        "MATCH (n:GmaCandidate) "
        "RETURN n.node_id AS node_id, n.payload_json AS payload_json "
        "ORDER BY node_id",
        {},
    )
    nodes = _decode_rows(fields, values, ["node_id", "payload_json"])
    fields, values = execute_query(
        base_url,
        "MATCH (s:GmaCandidate)-[r:GMA_CANDIDATE]->(t:GmaCandidate) "
        "RETURN r.edge_id AS edge_id, s.node_id AS source_node_id, "
        "t.node_id AS target_node_id, r.payload_json AS payload_json "
        "ORDER BY edge_id",
        {},
    )
    edges = _decode_rows(
        fields,
        values,
        ["edge_id", "source_node_id", "target_node_id", "payload_json"],
    )
    return {"nodes": nodes, "edges": edges}


def _decode_rows(
    fields: list[str], values: list[list[object]], expected: list[str]
) -> list[dict[str, object]]:
    if fields != expected:
        raise ValueError("Neo4j query returned unexpected fields")
    rows: list[dict[str, object]] = []
    for values_row in values:
        row = dict(zip(fields, values_row, strict=True))
        payload_json = row.pop("payload_json")
        if not isinstance(payload_json, str):
            raise TypeError("Neo4j payload must remain a JSON string")
        payload = _strict_object(payload_json)
        rows.append({**row, **payload})
    return rows


def _strict_object(value: str) -> dict[str, object]:
    result = json.loads(value)
    if not isinstance(result, dict):
        raise TypeError("Neo4j graph envelope must be an object")
    return cast("dict[str, object]", result)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
