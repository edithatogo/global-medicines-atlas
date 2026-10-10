"""Read-only API contract for bounded structural Gold edges."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import cast

import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient
from test_mbs_gold_graph import graph
from test_pbs_gold_graph import graph as pbs_graph
from typer.testing import CliRunner

from global_medicines_atlas.api import create_app
from global_medicines_atlas.cli import app
from global_medicines_atlas.gold_edge_review import build_gold_edge_review_queue
from global_medicines_atlas.matching_models import (
    AdjudicationEvent,
    ReviewState,
)
from global_medicines_atlas.mbs_gold_graph import project_mbs_gold_graph_arrow
from global_medicines_atlas.pbs_gold_graph import project_pbs_gold_graph_arrow
from global_medicines_atlas.platinum_edge_configuration import (
    MAX_EDGE_FILE_BYTES,
    load_gold_edges,
)
from global_medicines_atlas.query_service import ReadOnlyQueryService
from global_medicines_atlas.review_queue import (
    MAX_ADJUDICATION_FILE_BYTES,
    append_adjudication,
)

QUEUED_AT = datetime(2026, 10, 6, tzinfo=UTC)


def _synthetic_event(
    candidate_id: str,
    state: ReviewState,
    occurred_at: datetime,
    supersedes_event_id: str | None,
) -> AdjudicationEvent:
    reviewer_id = "synthetic-cli-reviewer"
    rationale = f"Synthetic {state.value} event."
    event_id = AdjudicationEvent.content_id(
        candidate_id=candidate_id,
        state=state,
        occurred_at=occurred_at,
        reviewer_id=reviewer_id,
        rationale=rationale,
        supersedes_event_id=supersedes_event_id,
    )
    return AdjudicationEvent(
        event_id=event_id,
        candidate_id=candidate_id,
        state=state,
        occurred_at=occurred_at,
        reviewer_id=reviewer_id,
        rationale=rationale,
        supersedes_event_id=supersedes_event_id,
    )


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


def test_pbs_edge_route_and_cli_preserve_source_structure(tmp_path) -> None:
    """Serve PBS containment candidates through both Platinum read surfaces."""
    _, edges = project_pbs_gold_graph_arrow(pbs_graph())
    client = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), gold_edges=edges)
    )
    response = client.get("/api/v1/edges")

    assert response.status_code == 200
    api_payload = response.json()
    assert api_payload["qualification"] == "synthetic_silver_candidate_only"
    assert api_payload["total"] == edges.num_rows
    assert api_payload["items"]
    assert all(
        item["evidence"]["source_id"] == "au-pbs"
        and item["kind"] == "source_contains_entity"
        and item["controls"]["inferred"] is False
        for item in api_payload["items"]
    )

    path = tmp_path / "pbs-edges.parquet"
    pq.write_table(edges, path)
    result = CliRunner().invoke(app, ["edges", "--edge-file", str(path)])

    assert result.exit_code == 0, result.stderr
    cli_payload = json.loads(result.stdout)
    assert cli_payload == api_payload


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


def test_gold_review_queue_cli_lists_pending_cases_without_promotion(
    tmp_path,
) -> None:
    candidate = graph()
    _, edges = project_mbs_gold_graph_arrow(candidate)
    edge_file = tmp_path / "edges.parquet"
    pq.write_table(edges, edge_file)
    expected = build_gold_edge_review_queue(
        candidate.edges,
        queued_at=QUEUED_AT,
    )

    result = CliRunner().invoke(
        app,
        [
            "gold-review-queue",
            "--edge-file",
            str(edge_file),
            "--queued-at",
            QUEUED_AT.isoformat(),
        ],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    assert payload["qualification"] == "synthetic_silver_candidate_only"
    assert payload["adjudication_event_count"] == 0
    assert payload["promotion_performed"] is False
    assert payload["cases"] == [
        case.model_dump(mode="json") for case in expected
    ]


def test_gold_review_queue_cli_applies_only_supplied_adjudications(
    tmp_path,
) -> None:
    candidate = graph()
    _, edges = project_mbs_gold_graph_arrow(candidate)
    edge_file = tmp_path / "edges.parquet"
    pq.write_table(edges, edge_file)
    expected = build_gold_edge_review_queue(
        candidate.edges,
        queued_at=QUEUED_AT,
    )
    case = expected[0]
    reviewer_id = "synthetic-cli-reviewer"
    state = ReviewState.ACCEPTED
    rationale = "Synthetic CLI fixture event."
    event_id = AdjudicationEvent.content_id(
        candidate_id=case.review_case_id,
        state=state,
        occurred_at=QUEUED_AT,
        reviewer_id=reviewer_id,
        rationale=rationale,
        supersedes_event_id=None,
    )
    event = AdjudicationEvent(
        event_id=event_id,
        candidate_id=case.review_case_id,
        state=state,
        occurred_at=QUEUED_AT,
        reviewer_id=reviewer_id,
        rationale=rationale,
        supersedes_event_id=None,
    )
    adjudication_file = tmp_path / "adjudications.jsonl"
    append_adjudication(adjudication_file, event)

    result = CliRunner().invoke(
        app,
        [
            "gold-review-queue",
            "--edge-file",
            str(edge_file),
            "--queued-at",
            QUEUED_AT.isoformat(),
            "--adjudications-file",
            str(adjudication_file),
        ],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["adjudication_event_count"] == 1
    assert payload["cases"] == [
        item.model_dump(mode="json")
        for item in expected
        if item.review_case_id != case.review_case_id
    ]
    assert payload["promotion_performed"] is False
    assert reviewer_id not in result.stdout
    assert rationale not in result.stdout


def test_gold_review_queue_cli_rejects_reordered_adjudication_events(
    tmp_path,
) -> None:
    candidate = graph()
    _, edges = project_mbs_gold_graph_arrow(candidate)
    edge_file = tmp_path / "edges.parquet"
    pq.write_table(edges, edge_file)
    expected = build_gold_edge_review_queue(
        candidate.edges,
        queued_at=QUEUED_AT,
    )
    case = expected[0]
    first = _synthetic_event(
        case.review_case_id,
        ReviewState.NEEDS_INFORMATION,
        QUEUED_AT,
        None,
    )
    second = _synthetic_event(
        case.review_case_id,
        ReviewState.ACCEPTED,
        QUEUED_AT + timedelta(seconds=1),
        first.event_id,
    )
    adjudication_file = tmp_path / "adjudications.jsonl"
    append_adjudication(adjudication_file, first)
    append_adjudication(adjudication_file, second)
    adjudication_file.write_text(
        "\n".join(reversed(adjudication_file.read_text().splitlines())) + "\n"
    )

    result = CliRunner().invoke(
        app,
        [
            "gold-review-queue",
            "--edge-file",
            str(edge_file),
            "--queued-at",
            QUEUED_AT.isoformat(),
            "--adjudications-file",
            str(adjudication_file),
        ],
    )

    assert result.exit_code == 2
    assert "invalid_request" in result.stderr


def test_gold_review_queue_cli_rejects_oversized_adjudication_file(
    tmp_path,
) -> None:
    _, edges = project_mbs_gold_graph_arrow(graph())
    edge_file = tmp_path / "edges.parquet"
    pq.write_table(edges, edge_file)
    adjudication_file = tmp_path / "oversized.jsonl"
    adjudication_file.write_bytes(b" " * (MAX_ADJUDICATION_FILE_BYTES + 1))

    result = CliRunner().invoke(
        app,
        [
            "gold-review-queue",
            "--edge-file",
            str(edge_file),
            "--queued-at",
            QUEUED_AT.isoformat(),
            "--adjudications-file",
            str(adjudication_file),
        ],
    )

    assert result.exit_code == 2
    assert "invalid_request" in result.stderr


def test_edge_loader_rejects_directory_and_oversized_file(tmp_path) -> None:
    directory = tmp_path / "edges"
    directory.mkdir()
    with pytest.raises(ValueError, match="regular"):
        load_gold_edges(directory)

    oversized = tmp_path / "oversized.parquet"
    oversized.write_bytes(b" " * (MAX_EDGE_FILE_BYTES + 1))
    with pytest.raises(ValueError, match="byte bound"):
        load_gold_edges(oversized)
