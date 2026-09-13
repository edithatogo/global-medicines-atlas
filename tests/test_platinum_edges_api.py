"""Read-only API contract for bounded structural Gold edges."""

from __future__ import annotations

from typing import cast

import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from test_mbs_gold_graph import graph
from typer.testing import CliRunner

from global_medicines_atlas.api import create_app
from global_medicines_atlas.cli import app
from global_medicines_atlas.mbs_gold_graph import project_mbs_gold_graph_arrow
from global_medicines_atlas.query_service import ReadOnlyQueryService


def test_edge_route_returns_structural_evidence() -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    client = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), gold_edges=edges)
    )

    response = client.get("/api/v1/edges")

    assert response.status_code == 200
    payload = response.json()
    assert payload["qualification"] == "synthetic_silver_candidate_only"
    assert payload["items"][0]["evidence"]["source_id"] == "au-mbs"


def test_edge_route_is_typed_when_unavailable() -> None:
    response = TestClient(
        create_app(cast("ReadOnlyQueryService", object()))
    ).get("/api/v1/edges")

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"


def test_edge_route_rejects_invalid_selector() -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    response = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), gold_edges=edges)
    ).get("/api/v1/edges", params={"kind": ""})

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_edges_cli_reads_validated_parquet(tmp_path) -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    path = tmp_path / "edges.parquet"
    pq.write_table(edges, path)

    result = CliRunner().invoke(app, ["edges", "--edge-file", str(path)])

    assert result.exit_code == 0, result.stderr
    assert '"source_id":"au-mbs"' in result.stdout


def test_edges_cli_rejects_invalid_file(tmp_path) -> None:
    path = tmp_path / "edges.parquet"
    path.write_bytes(b"not parquet")

    result = CliRunner().invoke(app, ["edges", "--edge-file", str(path)])

    assert result.exit_code == 2
    assert "invalid_request" in result.stderr
