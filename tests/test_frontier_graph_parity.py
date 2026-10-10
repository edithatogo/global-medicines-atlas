"""Engine-free parity checks for graph preview projections."""

import json
from urllib.parse import quote

import pyarrow as pa
import pytest
from test_mbs_gold_graph import graph

from global_medicines_atlas.frontier_graph_export import (
    export_gold_tables,
    export_rdf_star,
    rdf_iri_reference,
)
from global_medicines_atlas.frontier_graph_parity import validate_graph_previews
from global_medicines_atlas.frontier_networkx import qualify_networkx_graph
from global_medicines_atlas.mbs_gold_graph import project_mbs_gold_graph_arrow


def test_all_preview_surfaces_have_exact_semantic_parity() -> None:
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    export = export_gold_tables(nodes, edges)
    networkx = qualify_networkx_graph(nodes, edges)
    report = validate_graph_previews(
        export.reference_json,
        export.parameters_json,
        export_rdf_star(nodes, edges),
        networkx_recovered_json=networkx.recovered_json,
    )
    assert report.node_count == nodes.num_rows
    assert report.edge_count == edges.num_rows
    assert report.disposition == "retain-preview"


@pytest.mark.parametrize("field", ["parameters_json", "rdf_star"])
def test_projection_mutation_is_rejected(field: str) -> None:
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    export = export_gold_tables(nodes, edges)
    values = {
        "parameters_json": export.parameters_json,
        "rdf_star": export_rdf_star(nodes, edges),
    }
    if field == "parameters_json":
        document = json.loads(values[field])
        document["nodes"][0]["payload_json"] = "{}"
        values[field] = json.dumps(document)
    else:
        values[field] = values[field].replace("payload-json", "tampered", 1)
    with pytest.raises(ValueError, match="parity"):
        validate_graph_previews(
            export.reference_json, values["parameters_json"], values["rdf_star"]
        )


def test_non_fixed_cypher_templates_are_rejected() -> None:
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    export = export_gold_tables(nodes, edges)
    with pytest.raises(ValueError, match="template"):
        validate_graph_previews(
            export.reference_json,
            export.parameters_json,
            export_rdf_star(nodes, edges),
            node_statement="CREATE (n)",
        )


@pytest.mark.parametrize("field", ["reference_json", "parameters_json"])
def test_duplicate_json_object_keys_are_rejected(field: str) -> None:
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    export = export_gold_tables(nodes, edges)
    values = {
        "reference_json": export.reference_json,
        "parameters_json": export.parameters_json,
    }
    values[field] = '{"nodes":[], ' + values[field][1:]
    with pytest.raises(ValueError, match="duplicate JSON key: nodes"):
        validate_graph_previews(
            values["reference_json"],
            values["parameters_json"],
            export_rdf_star(nodes, edges),
        )


def test_graph_parity_uses_encoded_iri_identifiers():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    node_rows = nodes.to_pylist()
    edge_rows = edges.to_pylist()
    original = node_rows[0]["node_id"]
    hostile = "service id/雪%?#<tag>\\value"
    node_rows[0]["node_id"] = hostile
    for edge in edge_rows:
        if edge["source_node_id"] == original:
            edge["source_node_id"] = hostile
        if edge["target_node_id"] == original:
            edge["target_node_id"] = hostile
    nodes = pa.Table.from_pylist(node_rows, schema=nodes.schema)
    edges = pa.Table.from_pylist(edge_rows, schema=edges.schema)
    exported = export_gold_tables(nodes, edges)
    rdf = export_rdf_star(nodes, edges)

    report = validate_graph_previews(
        exported.reference_json, exported.parameters_json, rdf
    )

    expected = f"<urn:gma:node:{quote(hostile, safe='-._~:')}>"
    assert expected in rdf
    assert report.rdf_star_checked


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_node", "duplicate graph identity"),
        ("blank_node", "invalid graph identity"),
        ("duplicate_edge", "duplicate graph identity"),
        ("dangling_edge", "graph edge endpoint missing"),
        ("node_order", "not deterministically ordered"),
    ],
)
def test_parity_validator_rejects_consistent_malformed_graphs(
    mutation: str, message: str
) -> None:
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    reference = {
        "nodes": nodes.to_pylist(),
        "edges": edges.to_pylist(),
    }
    if mutation == "duplicate_node":
        reference["nodes"][1]["node_id"] = reference["nodes"][0]["node_id"]
    elif mutation == "blank_node":
        reference["nodes"][0]["node_id"] = ""
    elif mutation == "duplicate_edge":
        reference["edges"][1]["edge_id"] = reference["edges"][0]["edge_id"]
    elif mutation == "node_order":
        reference["nodes"].reverse()
    else:
        reference["edges"][0]["source_node_id"] = "missing-node"

    reference_json = json.dumps(
        reference, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    parameters_json = json.dumps(
        {
            "nodes": [
                {
                    "node_id": row["node_id"],
                    "payload_json": json.dumps(
                        row,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ),
                }
                for row in reference["nodes"]
            ],
            "edges": [
                {
                    "edge_id": row["edge_id"],
                    "source_node_id": row["source_node_id"],
                    "target_node_id": row["target_node_id"],
                    "payload_json": json.dumps(
                        row,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ),
                }
                for row in reference["edges"]
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    rdf_star = _rdf_for_reference(reference["nodes"], reference["edges"])

    with pytest.raises(ValueError, match=message):
        validate_graph_previews(reference_json, parameters_json, rdf_star)


def _rdf_for_reference(
    nodes: list[dict[str, object]], edges: list[dict[str, object]]
) -> str:
    lines = [
        f"{rdf_iri_reference('node', str(row['node_id']))} "
        "<urn:gma:payload-json> "
        f"{json.dumps(_canonical_json(row), ensure_ascii=True)} ."
        for row in nodes
    ]
    for row in edges:
        source = rdf_iri_reference("node", str(row["source_node_id"]))
        target = rdf_iri_reference("node", str(row["target_node_id"]))
        edge = rdf_iri_reference("edge", str(row["edge_id"]))
        quoted = f"<<{source} <urn:gma:connects-to> {target}>>"
        lines.extend((
            (
                f"{quoted} <urn:gma:edge-id> "
                f"{json.dumps(row['edge_id'], ensure_ascii=True)} ."
            ),
            f"{quoted} <urn:gma:edge-resource> {edge} .",
            (
                f"{edge} <urn:gma:payload-json> "
                f"{json.dumps(_canonical_json(row), ensure_ascii=True)} ."
            ),
        ))
    return "\n".join(lines)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
