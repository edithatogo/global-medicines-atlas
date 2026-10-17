from __future__ import annotations

import json
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from test_atlas_e2e import StateService
from test_mbs_gold_graph import (
    _admitted_input,  # ruff: ignore[import-private-name] -- shared fixture
    _admitted_table,  # ruff: ignore[import-private-name] -- shared fixture
    graph,
)
from test_pbs_gold_graph import graph as pbs_graph
from typer.testing import CliRunner

from global_medicines_atlas.api import create_app
from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.cli import app as cli
from global_medicines_atlas.mbs_gold_graph import (
    build_mbs_gold_graph_from_admitted_silver,
    project_mbs_gold_graph_arrow,
)
from global_medicines_atlas.pbs_gold_graph import project_pbs_gold_graph_arrow
from global_medicines_atlas.platinum_edges import gold_edge_payload
from global_medicines_atlas.query_service import ReadOnlyQueryService


def test_candidate_edges_are_bounded_and_visible_in_atlas(tmp_path) -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    edge_path = tmp_path / "candidate-edges.parquet"
    pq.write_table(edges, edge_path)
    client = TestClient(create_atlas_app(StateService(), gold_edges=edges))

    home = client.get("/")
    page = client.get("/gold/edges", params={"limit": 1})
    api = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), gold_edges=edges)
    ).get("/api/v1/edges")
    command = CliRunner().invoke(cli, ["edges", "--edge-file", str(edge_path)])

    assert home.status_code == 200
    assert 'href="/gold/edges"' in home.text
    assert page.status_code == 200
    assert "candidate" in page.text.lower()
    assert "not_reviewed" in page.text
    assert "confidence" in page.text.lower()
    assert "do not establish clinical equivalence" in page.text.lower()
    source_record_id = gold_edge_payload(edges)["items"][0]["evidence"][
        "source_record_id"
    ]
    assert f"<code>{source_record_id}</code>" in page.text
    assert "<dt>Review state</dt><dd>not_reviewed</dd>" in page.text
    assert "<dt>Confidence</dt><dd>Not calibrated</dd>" in page.text
    assert "Absence is not evidence of a negative" in page.text
    assert api.status_code == 200
    assert command.exit_code == 0, command.stderr
    cli_payload = json.loads(command.stdout)
    assert api.json() == cli_payload
    assert "Next 1 candidate edges" in page.text
    next_page = client.get("/gold/edges", params={"limit": 1, "offset": 1})
    assert next_page.status_code == 200
    assert "Next 1 candidate edges" not in next_page.text
    filtered = client.get(
        "/gold/edges",
        params={"source_node_id": edges.to_pylist()[0]["source_node_id"]},
    )
    assert filtered.status_code == 200
    assert filtered.text.count('<article class="result-card"') == 1
    empty = client.get("/gold/edges", params={"kind": "unmatched-kind"})
    assert empty.status_code == 200
    assert "No candidate edges match these filters" in empty.text
    assert "Absence is not evidence of a negative relationship" in empty.text


def test_gold_edge_atlas_is_absent_without_injected_graph() -> None:
    client = TestClient(create_atlas_app(StateService()))

    assert client.get("/").status_code == 200
    assert 'href="/gold/edges"' not in client.get("/").text
    assert client.get("/gold/edges").status_code == 404


def test_atlas_renders_admitted_mbs_v3_candidate_metadata() -> None:
    candidate = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input(),
    )
    _, edges = project_mbs_gold_graph_arrow(candidate)

    response = TestClient(
        create_atlas_app(StateService(), gold_edges=edges)
    ).get("/gold/edges", params={"limit": 1})

    assert response.status_code == 200
    assert "admitted_real_silver_candidate_only" in response.text
    assert "not_reviewed" in response.text
    assert "Not calibrated" in response.text
    for binding in (
        b"input_admission_sha256",
        b"input_semantic_manifest_sha256",
        b"graph_sha256",
    ):
        assert edges.schema.metadata[binding].decode() in response.text


def test_atlas_renders_pbs_top_level_review_controls() -> None:
    _, edges = project_pbs_gold_graph_arrow(pbs_graph())
    confidence_index = edges.schema.get_field_index("confidence")
    edges = edges.set_column(
        confidence_index,
        edges.schema.field("confidence"),
        pa.array([0.75] * edges.num_rows, type=pa.float64()),
    )

    response = TestClient(
        create_atlas_app(StateService(), gold_edges=edges)
    ).get("/gold/edges", params={"limit": 1})

    assert response.status_code == 200
    assert "not_reviewed" in response.text
    assert "<dt>Confidence</dt><dd>0.75</dd>" in response.text


def test_atlas_rejects_unsupported_edge_schema() -> None:
    response = TestClient(
        create_atlas_app(StateService(), gold_edges=pa.table({"wrong": []}))
    ).get("/gold/edges")

    assert response.status_code == 422
    assert "Gold edge selection is invalid" in response.text
