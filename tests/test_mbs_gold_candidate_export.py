from __future__ import annotations

import hashlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_gold_graph import (
    _admitted_input,  # ruff: ignore[import-private-name] -- shared fixture
    _admitted_table,  # ruff: ignore[import-private-name] -- shared fixture
)

from global_medicines_atlas import mbs_gold_candidate_export
from global_medicines_atlas.mbs_gold_candidate_export import (
    write_mbs_gold_candidate_edges,
)
from global_medicines_atlas.mbs_gold_graph import (
    build_mbs_gold_graph_from_admitted_silver,
)
from global_medicines_atlas.platinum_edge_configuration import load_gold_edges


def _candidate():
    return build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input(),
    )


def test_export_writes_bound_parquet_without_overwriting(tmp_path) -> None:
    candidate = _candidate()
    output = tmp_path / "candidate-edges.parquet"

    receipt = write_mbs_gold_candidate_edges(
        candidate,
        output,
        expected_graph_sha256=candidate.graph_sha256,
    )
    restored = load_gold_edges(output)

    assert receipt.edge_count == len(candidate.edges)
    assert receipt.graph_sha256 == candidate.graph_sha256
    assert receipt.file_byte_count == output.stat().st_size
    assert (
        receipt.file_sha256 == hashlib.sha256(output.read_bytes()).hexdigest()
    )
    assert restored.num_rows == receipt.edge_count
    assert restored.schema.metadata[b"qualification"] == (
        b"admitted_real_silver_candidate_only"
    )
    assert restored.schema.metadata[b"graph_sha256"] == (
        candidate.graph_sha256.encode()
    )
    with pytest.raises(FileExistsError):
        write_mbs_gold_candidate_edges(
            candidate,
            output,
            expected_graph_sha256=candidate.graph_sha256,
        )


def test_export_rejects_graph_digest_mismatch_and_oversized_projection(
    tmp_path,
) -> None:
    candidate = _candidate()
    output = tmp_path / "candidate-edges.parquet"

    with pytest.raises(ValueError, match="differs"):
        write_mbs_gold_candidate_edges(
            candidate,
            output,
            expected_graph_sha256="f" * 64,
        )
    with pytest.raises(ValueError, match="byte bound"):
        write_mbs_gold_candidate_edges(
            candidate,
            output,
            expected_graph_sha256=candidate.graph_sha256,
            max_file_bytes=1,
        )
    assert not output.exists()


def test_exported_table_preserves_exact_admission_bindings(tmp_path) -> None:
    candidate = _candidate()
    output = tmp_path / "candidate-edges.parquet"
    write_mbs_gold_candidate_edges(
        candidate,
        output,
        expected_graph_sha256=candidate.graph_sha256,
    )

    restored = pq.read_table(output)

    assert restored.schema.metadata[b"input_admission_sha256"] == (
        candidate.input_admission_sha256.encode()
    )
    assert restored.schema.metadata[b"input_semantic_manifest_sha256"] == (
        candidate.input_semantic_manifest_sha256.encode()
    )


def test_export_rejects_changed_value_during_parquet_readback(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _candidate()
    output = tmp_path / "candidate-edges.parquet"
    original_read_table = pq.read_table
    altered_edges = mbs_gold_candidate_export.project_mbs_gold_graph_arrow(
        candidate
    )[1]
    altered_edges = altered_edges.set_column(
        0,
        altered_edges.schema.field(0),
        pa.array(["changed-edge-id"] * altered_edges.num_rows),
    )

    def read_changed_table(source):
        original_read_table(source)
        return altered_edges

    monkeypatch.setattr(
        mbs_gold_candidate_export.pq, "read_table", read_changed_table
    )
    with pytest.raises(ValueError, match="failed readback"):
        write_mbs_gold_candidate_edges(
            candidate,
            output,
            expected_graph_sha256=candidate.graph_sha256,
        )
    assert not output.exists()
