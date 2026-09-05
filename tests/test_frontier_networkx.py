"""Actual optional graph engine preserves candidate Gold semantics."""

import importlib
import json

import pyarrow as pa
import pytest
from test_mbs_gold_graph import graph
from test_pbs_gold_graph import graph as pbs_graph

from global_medicines_atlas.frontier_networkx import qualify_networkx_graph
from global_medicines_atlas.mbs_gold_graph import project_mbs_gold_graph_arrow
from global_medicines_atlas.pbs_gold_graph import project_pbs_gold_graph_arrow


def test_optional_engine_absence_is_explicit(monkeypatch):
    nodes, edges = project_mbs_gold_graph_arrow(graph())

    def missing(_name):
        raise ModuleNotFoundError("networkx")

    monkeypatch.setattr(importlib, "import_module", missing)
    with pytest.raises(RuntimeError, match="optional NetworkX"):
        qualify_networkx_graph(nodes, edges)


@pytest.mark.parametrize("family", ["mbs", "pbs"])
def test_actual_networkx_preserves_all_gold_fields(family):
    pytest.importorskip("networkx")
    nodes, edges = (
        project_mbs_gold_graph_arrow(graph())
        if family == "mbs"
        else project_pbs_gold_graph_arrow(pbs_graph())
    )
    receipt = qualify_networkx_graph(nodes, edges)
    assert receipt.disposition == "retain-preview"
    assert receipt.engine_version
    recovered = json.loads(receipt.recovered_json)
    assert recovered["nodes"] == nodes.to_pylist()
    assert recovered["edges"] == edges.to_pylist()
    assert (
        qualify_networkx_graph(
            nodes.take(list(reversed(range(len(nodes))))),
            edges.take(list(reversed(range(len(edges))))),
        )
        == receipt
    )


def test_parallel_edges_cycles_and_isolates_have_exact_parity():
    pytest.importorskip("networkx")
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    ids = nodes["node_id"].to_pylist()
    template = edges.to_pylist()[0]
    rows = [
        {
            **template,
            "edge_id": str(index),
            "source_node_id": source,
            "target_node_id": target,
        }
        for index, (source, target) in enumerate([
            (ids[0], ids[1]),
            (ids[0], ids[1]),
            (ids[1], ids[0]),
            (ids[1], ids[2]),
            (ids[2], ids[2]),
        ])
    ]
    receipt = qualify_networkx_graph(
        nodes, pa.Table.from_pylist(rows, schema=edges.schema)
    )
    queries = json.loads(receipt.query_json)
    assert queries[ids[0]]["out_degree"] == 2
    assert queries[ids[0]]["descendants"] == sorted(ids[1:3])
    assert queries[ids[3]]["descendants"] == []
    assert queries[ids[2]]["out_degree"] == 1


def test_empty_graph_parity():
    pytest.importorskip("networkx")
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    result = qualify_networkx_graph(nodes.slice(0, 0), edges.slice(0, 0))
    assert json.loads(result.query_json) == {}


def test_all_node_query_bound_is_enforced_before_engine_import():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="query bound"):
        qualify_networkx_graph(pa.concat_tables([nodes] * 251), edges)


def test_engine_direction_regression_is_detected(monkeypatch):
    nx = pytest.importorskip("networkx")
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    monkeypatch.setattr(nx, "descendants", lambda *_: set())
    with pytest.raises(ValueError, match="query semantics differ"):
        qualify_networkx_graph(nodes, edges)


def test_engine_parallel_edge_loss_is_detected(monkeypatch):
    nx = pytest.importorskip("networkx")
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    original = nx.MultiDiGraph.add_edge

    def discard_payload(self, left, right, **kwargs):
        kwargs["payload"] = {}
        return original(self, left, right, **kwargs)

    monkeypatch.setattr(nx.MultiDiGraph, "add_edge", discard_payload)
    with pytest.raises((ValueError, KeyError), match=r"fields|edge_id"):
        qualify_networkx_graph(nodes, edges)
