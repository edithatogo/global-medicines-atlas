"""Portable graph export preserves evidence and never interpolates labels."""

import json

import pyarrow as pa
import pytest
from test_mbs_gold_graph import graph
from test_pbs_gold_graph import graph as pbs_graph

from global_medicines_atlas.frontier_graph_export import (
    export_gold_tables,
    export_rdf_star,
)
from global_medicines_atlas.mbs_gold_graph import project_mbs_gold_graph_arrow
from global_medicines_atlas.pbs_gold_graph import project_pbs_gold_graph_arrow


def test_reference_and_cypher_parameters_preserve_every_portable_field():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    result = export_gold_tables(nodes, edges)
    reference = json.loads(result.reference_json)
    parameters = json.loads(result.parameters_json)
    assert reference["nodes"] == nodes.to_pylist()
    assert reference["edges"] == edges.to_pylist()
    assert [
        json.loads(row["payload_json"]) for row in parameters["nodes"]
    ] == reference["nodes"]
    assert [
        json.loads(row["payload_json"]) for row in parameters["edges"]
    ] == reference["edges"]
    assert export_gold_tables(nodes, edges) == result
    assert (
        export_gold_tables(nodes.take([3, 2, 1, 0]), edges.take([1, 0]))
        == result
    )


def test_hostile_native_text_is_only_parameter_data():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    rows = nodes.to_pylist()
    hostile = "'\\\n` MATCH (n) DETACH DELETE n; // 雪"
    rows[0]["fields_json"] = json.dumps({"native_value": hostile})
    result = export_gold_tables(
        pa.Table.from_pylist(rows, schema=nodes.schema), edges
    )
    assert hostile not in result.node_statement + result.edge_statement
    recovered = json.loads(
        json.loads(result.parameters_json)["nodes"][0]["payload_json"]
    )
    assert json.loads(recovered["fields_json"])["native_value"] == hostile


def test_duplicate_dangling_and_schema_mismatch_are_rejected():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="duplicate"):
        export_gold_tables(pa.concat_tables([nodes, nodes]), edges)
    with pytest.raises(ValueError, match="endpoint"):
        export_gold_tables(nodes.slice(0, 1), edges)
    with pytest.raises(ValueError, match="schema"):
        export_gold_tables(nodes.drop(["fields_json"]), edges)


def test_export_denominator_is_bounded():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="bound"):
        export_gold_tables(nodes, edges, max_rows=1)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_bounds(limit):
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="bound"):
        export_gold_tables(nodes, edges, max_bytes=limit)


def test_pbs_preserves_null_confidence_and_explicit_candidate_controls():
    nodes, edges = project_pbs_gold_graph_arrow(pbs_graph())
    result = export_gold_tables(nodes, edges)
    rows = json.loads(result.reference_json)["edges"]
    assert rows
    for row in rows:
        assert row["confidence"] is None
        assert row["review_state"] == "not_reviewed"
        assert json.loads(row["controls_json"])["inferred"] is False
    with pytest.raises(ValueError, match="schema"):
        export_gold_tables(nodes, project_mbs_gold_graph_arrow(graph())[1])


def test_empty_tables_and_byte_bounds():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    assert json.loads(
        export_gold_tables(nodes.slice(0, 0), edges.slice(0, 0)).reference_json
    ) == {"nodes": [], "edges": []}
    with pytest.raises(ValueError, match="byte bound"):
        export_gold_tables(nodes, edges, max_bytes=1)
    with pytest.raises(ValueError, match="serialized"):
        export_gold_tables(nodes, edges, max_bytes=nodes.nbytes + edges.nbytes)


def test_null_identity_rejected_even_with_nullable_arrow_field():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    rows = nodes.to_pylist()
    rows[0]["node_id"] = None
    with pytest.raises(ValueError, match="identity"):
        export_gold_tables(
            pa.Table.from_pylist(rows, schema=nodes.schema), edges
        )


def test_rdf_star_is_deterministic_lossless_and_quotes_edges():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    result = export_rdf_star(nodes, edges)
    assert result == export_rdf_star(nodes.take([3, 1, 0, 2]), edges.take([1, 0]))
    assert "<<<urn:gma:node:" in result
    assert "<urn:gma:payload-json>" in result
    assert "native_name" in result
    assert "urn:gma:edge-resource" in result


def test_rdf_star_reuses_fail_closed_bounds():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="bound"):
        export_rdf_star(nodes, edges, max_rows=1)
