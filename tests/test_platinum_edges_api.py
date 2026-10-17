"""Read-only API contract for bounded structural Gold edges."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from typing import cast
from urllib.parse import parse_qs, urlsplit

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
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
from global_medicines_atlas.cli import app
from global_medicines_atlas.gold_edge_review import build_gold_edge_review_queue
from global_medicines_atlas.matching_models import (
    AdjudicationEvent,
    ReviewState,
)
from global_medicines_atlas.mbs_gold_graph import (
    build_mbs_gold_graph_from_admitted_silver,
    project_mbs_gold_graph_arrow,
)
from global_medicines_atlas.pbs_gold_graph import project_pbs_gold_graph_arrow
from global_medicines_atlas.platinum_edge_configuration import (
    MAX_EDGE_FILE_BYTES,
    MAX_EDGE_FILE_ROWS,
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
    assert payload["offset"] == 0
    assert payload["has_more"] is False


def test_admitted_mbs_v3_api_preserves_all_three_graph_bindings() -> None:
    candidate = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input(),
    )
    _, edges = project_mbs_gold_graph_arrow(candidate)
    response = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), gold_edges=edges)
    ).get("/api/v1/edges", params={"limit": 1})

    assert response.status_code == 200
    assert response.json()["admission_bindings"] == {
        "input_admission_sha256": candidate.input_admission_sha256,
        "input_semantic_manifest_sha256": (
            candidate.input_semantic_manifest_sha256
        ),
        "graph_sha256": candidate.graph_sha256,
    }


def _traverse_atlas_edge_pages(atlas, edge_kind: str) -> list[str]:
    edge_ids: list[str] = []
    offsets: list[int] = []
    params = {"limit": "1000", "offset": "0", "kind": edge_kind}
    while True:
        offset = int(params["offset"])
        offsets.append(offset)
        response = atlas.get("/gold/edges", params=params)
        assert response.status_code == 200
        page_ids = re.findall(r"<code>(edge:\d{4})</code>", response.text)
        edge_ids.extend(page_ids)
        next_link = re.search(r'<a href="([^"]+)">Next ', response.text)
        if next_link is None:
            break
        next_query = parse_qs(urlsplit(unescape(next_link.group(1))).query)
        assert next_query["kind"] == [edge_kind]
        assert next_query["limit"] == ["1000"]
        params = {key: values[0] for key, values in next_query.items()}
        assert int(params["offset"]) == offset + len(page_ids)

    assert offsets == [0, 1000]
    return edge_ids


def _assert_cli_api_edge_pages(
    api, edge_path, edge_kind: str, total: int
) -> None:
    for offset in (0, 1000):
        params = {"limit": 1000, "offset": offset, "kind": edge_kind}
        api_response = api.get("/api/v1/edges", params=params)
        cli_result = CliRunner().invoke(
            app,
            [
                "edges",
                "--edge-file",
                str(edge_path),
                "--limit",
                "1000",
                "--offset",
                str(offset),
                "--kind",
                edge_kind,
            ],
        )
        assert api_response.status_code == 200
        assert cli_result.exit_code == 0, cli_result.stderr
        api_page = api_response.json()
        assert api_page == json.loads(cli_result.stdout)
        assert api_page["offset"] == offset
        assert api_page["total"] == total
        assert len(api_page["items"]) == min(1000, total - offset)
        assert api_page["has_more"] is (offset + len(api_page["items"]) < total)


def test_file_backed_edge_consumers_traverse_multiple_pages(tmp_path) -> None:
    _, sample = project_mbs_gold_graph_arrow(graph())
    sample_row = sample.to_pylist()[0]
    rows = [
        {**sample_row, "edge_id": f"edge:{index:04d}"} for index in range(1001)
    ]
    edges = pa.Table.from_pylist(rows, schema=sample.schema)
    edge_path = tmp_path / "many-edges.parquet"
    pq.write_table(edges, edge_path)
    loaded = load_gold_edges(edge_path)
    api = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), gold_edges=loaded)
    )
    atlas = TestClient(create_atlas_app(StateService(), gold_edges=loaded))
    edge_kind = sample_row["kind"]

    _assert_cli_api_edge_pages(api, edge_path, edge_kind, edges.num_rows)
    atlas_ids = _traverse_atlas_edge_pages(atlas, edge_kind)
    assert atlas_ids == [f"edge:{index:04d}" for index in range(edges.num_rows)]


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
    assert payload["adjudication_authority_verified"] is False
    assert payload["promotion_performed"] is False
    assert payload["cases"] == [
        case.model_dump(mode="json") for case in expected
    ]


def test_gold_review_queue_cli_keeps_unverified_adjudications_pending(
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
    assert payload["adjudication_authority_verified"] is False
    assert payload["cases"] == [
        item.model_dump(mode="json") for item in expected
    ]
    assert payload["promotion_performed"] is False
    assert reviewer_id not in result.stdout
    assert rationale not in result.stdout


def test_gold_review_queue_refuses_truncated_paginated_candidates(
    tmp_path,
) -> None:
    candidate = graph()
    _, edges = project_mbs_gold_graph_arrow(candidate)
    edge_file = tmp_path / "oversized-queue.parquet"
    pq.write_table(pa.concat_tables([edges] * 201), edge_file)
    first_case = build_gold_edge_review_queue(
        candidate.edges,
        queued_at=QUEUED_AT,
    )[0]
    adjudications_file = tmp_path / "adjudications.jsonl"
    append_adjudication(
        adjudications_file,
        _synthetic_event(
            first_case.review_case_id,
            ReviewState.ACCEPTED,
            QUEUED_AT,
            None,
        ),
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
            str(adjudications_file),
            "--limit",
            "1",
        ],
    )
    assert result.exit_code == 2
    assert "invalid_request" in result.stderr
    assert "review queue edge row bound exceeded" not in result.stderr


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


def test_edge_loader_rejects_file_over_row_bound_before_read(tmp_path) -> None:
    _, sample = project_mbs_gold_graph_arrow(graph())
    sample_row = sample.to_pylist()[0]
    rows = [
        {**sample_row, "edge_id": f"edge:{index:05d}"}
        for index in range(MAX_EDGE_FILE_ROWS + 1)
    ]
    oversized = pa.Table.from_pylist(rows, schema=sample.schema)
    path = tmp_path / "too-many-edges.parquet"
    pq.write_table(oversized, path)

    with pytest.raises(ValueError, match="row bound"):
        load_gold_edges(path)


def test_edge_loader_rechecks_row_bound_after_parquet_read(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, sample = project_mbs_gold_graph_arrow(graph())
    sample_row = sample.to_pylist()[0]
    rows = [
        {**sample_row, "edge_id": f"edge:{index:05d}"}
        for index in range(MAX_EDGE_FILE_ROWS + 1)
    ]
    oversized = pa.Table.from_pylist(rows, schema=sample.schema)
    path = tmp_path / "metadata-underreports-rows.parquet"
    pq.write_table(oversized, path)

    class MisreportedParquetFile:
        metadata = type("Metadata", (), {"num_rows": 0})()

        def __init__(self, _stream) -> None:
            pass

        def read(self) -> pa.Table:
            return oversized

    monkeypatch.setattr(
        "global_medicines_atlas.platinum_edge_configuration.pq.ParquetFile",
        MisreportedParquetFile,
    )
    with pytest.raises(ValueError, match="row bound"):
        load_gold_edges(path)
