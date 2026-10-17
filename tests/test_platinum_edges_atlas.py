from __future__ import annotations

import json
from typing import cast

import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from test_atlas_e2e import StateService
from test_mbs_gold_graph import graph
from typer.testing import CliRunner

from global_medicines_atlas.api import create_app
from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.cli import app as cli
from global_medicines_atlas.mbs_gold_graph import project_mbs_gold_graph_arrow
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
        params={"source_node_id": edges["source_node_id"][0].as_py()},
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
