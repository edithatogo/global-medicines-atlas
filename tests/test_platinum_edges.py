"""Bounded structural Gold adjacency projection tests."""

import pyarrow as pa
import pytest
from test_mbs_gold_graph import (
    _admitted_input,  # ruff: ignore[import-private-name] -- shared fixture
    _admitted_table,  # ruff: ignore[import-private-name] -- shared fixture
    graph,
)

from global_medicines_atlas.mbs_gold_graph import (
    build_mbs_gold_graph_from_admitted_silver,
    project_mbs_gold_graph_arrow,
)
from global_medicines_atlas.platinum_edges import (
    gold_edge_payload,
    select_gold_edges,
)


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
    with pytest.raises(ValueError, match="bound exceeded"):
        select_gold_edges(edges, max_rows=1)


def test_empty_selection_preserves_schema() -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    selected = select_gold_edges(edges, source_node_id="missing")
    assert selected.num_rows == 0
    assert selected.schema.equals(edges.schema, check_metadata=True)


def test_edge_payload_decodes_evidence_and_controls() -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())

    payload = gold_edge_payload(edges)

    assert payload["total"] == edges.num_rows
    assert payload["qualification"] == "synthetic_silver_candidate_only"
    assert payload["items"][0]["evidence"]["source_id"] == "au-mbs"
    assert payload["items"][0]["inferred"] is False
    assert payload["items"][0]["controls"]["review_state"] == "not_reviewed"


def test_edge_selection_accepts_exact_admitted_mbs_v3_metadata() -> None:
    candidate = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input(),
    )
    _, edges = project_mbs_gold_graph_arrow(candidate)

    payload = gold_edge_payload(edges)

    assert payload["schema_version"] == "3.0"
    assert payload["qualification"] == "admitted_real_silver_candidate_only"
    assert payload["items"][0]["controls"]["review_state"] == "not_reviewed"
    assert payload["admission_bindings"] == {
        "input_admission_sha256": "a" * 64,
        "input_semantic_manifest_sha256": "b" * 64,
        "graph_sha256": candidate.graph_sha256,
    }


def test_edge_selection_rejects_unbound_admitted_metadata() -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    metadata = dict(edges.schema.metadata or {})
    metadata[b"qualification"] = b"admitted_real_silver_candidate_only"
    forged = edges.replace_schema_metadata(metadata)

    with pytest.raises(ValueError, match="unsupported"):
        select_gold_edges(forged)

    admitted = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input(),
    )
    _, admitted_edges = project_mbs_gold_graph_arrow(admitted)
    invalid_digest_metadata = dict(admitted_edges.schema.metadata or {})
    invalid_digest_metadata[b"graph_sha256"] = b"g" * 64

    with pytest.raises(ValueError, match="unsupported"):
        select_gold_edges(
            admitted_edges.replace_schema_metadata(invalid_digest_metadata)
        )
