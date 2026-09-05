"""Engine-free parity checks for graph preview projections."""

import json

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
        export.reference_json, export.parameters_json, export_rdf_star(nodes, edges),
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
        validate_graph_previews(export.reference_json, values["parameters_json"], values["rdf_star"])


def test_non_fixed_cypher_templates_are_rejected() -> None:
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    export = export_gold_tables(nodes, edges)
    with pytest.raises(ValueError, match="template"):
        validate_graph_previews(export.reference_json, export.parameters_json, export_rdf_star(nodes, edges), node_statement="CREATE (n)")
