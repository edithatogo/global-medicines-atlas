"""Engine-free parity checks for graph preview projections."""

import json
from urllib.parse import quote

import pyarrow as pa
import pytest
from test_mbs_gold_graph import graph

from global_medicines_atlas.frontier_graph_export import (
    export_gold_tables,
    export_rdf_star,
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
