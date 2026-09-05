"""Bounded structural Gold adjacency projection tests."""

import pyarrow as pa
import pytest
from test_mbs_gold_graph import graph

from global_medicines_atlas.mbs_gold_graph import project_mbs_gold_graph_arrow
from global_medicines_atlas.platinum_edges import select_gold_edges


def test_edge_selection_is_sorted_and_lossless() -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    source = edges.to_pylist()[0]["source_node_id"]
    selected = select_gold_edges(edges, source_node_id=source)
    assert [row["edge_id"] for row in selected.to_pylist()] == sorted(
        row["edge_id"]
        for row in edges.to_pylist()
        if row["source_node_id"] == source
    )
    assert selected.schema.equals(edges.schema, check_metadata=True)
    assert selected.to_pylist()[0]["evidence_json"]


def test_edge_selection_rejects_unbounded_or_unsupported_queries() -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="bound"):
        select_gold_edges(edges, max_rows=0)
    with pytest.raises(ValueError, match="unsupported"):
        select_gold_edges(pa.table({"edge_id": ["e"]}))
    with pytest.raises(ValueError, match="selector"):
        select_gold_edges(edges, kind="")


def test_empty_selection_preserves_schema() -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    selected = select_gold_edges(edges, source_node_id="missing")
    assert selected.num_rows == 0
    assert selected.schema.equals(edges.schema, check_metadata=True)
