from __future__ import annotations

import pyarrow.parquet as pq
import pytest
from test_mbs_gold_graph import (
    _admitted_input,  # ruff: ignore[import-private-name] -- shared fixture
    _admitted_table,  # ruff: ignore[import-private-name] -- shared fixture
)

import global_medicines_atlas.mbs_gold_consumer_qualification as consumer_qualification
from global_medicines_atlas.mbs_gold_candidate_export import (
    write_mbs_gold_candidate_edges,
)
from global_medicines_atlas.mbs_gold_consumer_qualification import (
    qualify_consumers,
)
from global_medicines_atlas.mbs_gold_graph import (
    build_mbs_gold_graph_from_admitted_silver,
)


def _candidate_artifact(tmp_path):
    candidate = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input(),
    )
    edge_path = tmp_path / "candidate.parquet"
    write_mbs_gold_candidate_edges(
        candidate,
        edge_path,
        expected_graph_sha256=candidate.graph_sha256,
    )
    qualification = {
        "graph": {
            "edge_count": len(candidate.edges),
            "graph_sha256": candidate.graph_sha256,
        }
    }
    expected_bindings = {
        "input_admission_sha256": candidate.input_admission_sha256,
        "input_semantic_manifest_sha256": candidate.input_semantic_manifest_sha256,
        "graph_sha256": candidate.graph_sha256,
    }
    return edge_path, qualification, expected_bindings, candidate


def test_candidate_consumer_receipt_traverses_each_surface_without_edge_ids(
    tmp_path,
) -> None:
    edge_path, qualification, expected_bindings, candidate = (
        _candidate_artifact(tmp_path)
    )

    receipt = qualify_consumers(
        edge_path,
        qualification,
        page_size=1,
        expected_bindings=expected_bindings,
    )

    assert receipt["candidate_only"] is True
    assert receipt["edge_count"] == len(candidate.edges)
    assert receipt["surfaces"] == ["API", "Atlas", "CLI"]
    assert receipt["page_offsets"] == [0, 1]
    assert receipt["surface_edge_id_sha256"] == {
        "API": receipt["surface_edge_id_sha256"]["CLI"],
        "Atlas": receipt["surface_edge_id_sha256"]["CLI"],
        "CLI": receipt["surface_edge_id_sha256"]["CLI"],
    }
    assert receipt["review_state"] == "not_reviewed"
    assert "items" not in receipt
    assert all(
        edge["edge_id"] not in str(receipt)
        for edge in pq.read_table(edge_path).to_pylist()
    )


def test_candidate_consumer_rejects_surfaces_agreeing_on_wrong_edge_ids(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    edge_path, qualification, expected_bindings, _candidate = (
        _candidate_artifact(tmp_path)
    )
    authoritative_ids = sorted(
        edge["edge_id"] for edge in pq.read_table(edge_path).to_pylist()
    )
    last = authoritative_ids[-1]
    replacement = last[:-1] + ("0" if last[-1] != "0" else "1")
    wrong_ids = [*authoritative_ids[:-1], replacement]
    monkeypatch.setattr(
        consumer_qualification, "_api_ids", lambda *_args: wrong_ids
    )
    monkeypatch.setattr(
        consumer_qualification, "_cli_ids", lambda *_args: wrong_ids
    )
    monkeypatch.setattr(
        consumer_qualification,
        "_atlas_ids",
        lambda *_args: (wrong_ids, [0, 1]),
    )

    with pytest.raises(ValueError, match="authoritative candidate edges"):
        qualify_consumers(
            edge_path,
            qualification,
            page_size=1,
            expected_bindings=expected_bindings,
        )
