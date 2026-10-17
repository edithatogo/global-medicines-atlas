"""Write a local, non-published MBS Gold candidate edge projection."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .mbs_gold_graph import MbsGoldGraphCandidate, project_mbs_gold_graph_arrow
from .platinum_edge_configuration import MAX_EDGE_FILE_BYTES
from .platinum_edges import select_gold_edges


@dataclass(frozen=True, slots=True)
class GoldCandidateExport:
    """Value-free receipt for one locally written candidate edge table."""

    edge_count: int
    file_byte_count: int
    file_sha256: str
    graph_sha256: str
    path: Path


def _write_and_verify(
    descriptor: int,
    payload: bytes,
    expected_edges: pa.Table,
) -> str:
    with os.fdopen(os.dup(descriptor), "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 64 * 1024):
        chunks.append(chunk)
    actual_bytes = b"".join(chunks)
    if actual_bytes != payload:
        raise ValueError("written candidate edge bytes differ from payload")
    restored = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        pa.BufferReader(actual_bytes)
    )
    if (
        not restored.equals(expected_edges)
        or restored.schema.metadata != expected_edges.schema.metadata
    ):
        raise ValueError("written candidate edge file failed readback")
    return hashlib.sha256(actual_bytes).hexdigest()


def write_mbs_gold_candidate_edges(
    graph: MbsGoldGraphCandidate,
    output_path: Path,
    *,
    expected_graph_sha256: str,
    max_file_bytes: int = MAX_EDGE_FILE_BYTES,
) -> GoldCandidateExport:
    """Write one exact candidate Parquet file without replacing existing data.

    This creates a local, rebuildable projection only. It performs no product
    admission, publication, or edge review.
    """
    if graph.qualification != "admitted_real_silver_candidate_only":
        raise ValueError("only the admitted real MBS candidate can be exported")
    if graph.graph_sha256 != expected_graph_sha256:
        raise ValueError("graph digest differs from the qualified candidate")
    if type(max_file_bytes) is not int or max_file_bytes < 1:
        raise ValueError("file byte bound must be a positive integer")
    if output_path.suffix.lower() != ".parquet":
        raise ValueError("candidate edge output must use a .parquet suffix")
    if not output_path.parent.is_dir():
        raise ValueError("candidate edge output directory must exist")
    admission_sha256 = graph.input_admission_sha256
    semantic_manifest_sha256 = graph.input_semantic_manifest_sha256
    if admission_sha256 is None or semantic_manifest_sha256 is None:
        raise ValueError("candidate graph is missing admission bindings")

    _, edges = project_mbs_gold_graph_arrow(graph)
    metadata = edges.schema.metadata or {}
    if (
        metadata.get(b"graph_sha256") != expected_graph_sha256.encode()
        or metadata.get(b"input_admission_sha256") != admission_sha256.encode()
        or metadata.get(b"input_semantic_manifest_sha256")
        != semantic_manifest_sha256.encode()
    ):
        raise ValueError("candidate edge projection lost its exact bindings")
    # Reuse the consumer validator while keeping presentation pages bounded.
    select_gold_edges(edges, max_rows=1, allow_pagination=True)

    sink = pa.BufferOutputStream()
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        edges,
        sink,
        compression="zstd",
        version="2.6",
        use_dictionary=False,
        write_statistics=False,
    )
    payload = sink.getvalue().to_pybytes()
    if len(payload) > max_file_bytes:
        raise ValueError("candidate edge output exceeds the file byte bound")

    descriptor = os.open(
        output_path,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        verified_sha256 = _write_and_verify(descriptor, payload, edges)
    except BaseException:
        output_path.unlink(missing_ok=True)
        raise
    finally:
        os.close(descriptor)

    return GoldCandidateExport(
        edge_count=edges.num_rows,
        file_byte_count=len(payload),
        file_sha256=verified_sha256,
        graph_sha256=expected_graph_sha256,
        path=output_path,
    )
