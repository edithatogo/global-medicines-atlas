from datetime import UTC, datetime
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

import pytest

from global_medicines_atlas.matching_indexes import (
    MatchingIndexLineage,
    MatchingIndexRow,
    generate_lancedb_index,
)
from global_medicines_atlas.receipts import RightsState
from global_medicines_atlas.semantic_retrieval import (
    SemanticIndexIdentity,
    optional_semantic_retriever,
)


def test_lancedb_regeneration_and_offline_search(tmp_path: Path) -> None:
    rows = (
        MatchingIndexRow(
            concept_id="nz:paracetamol",
            mapping_level="ingredient",
            source_snapshot_id="fixture-snapshot",
            schema_version="1",
            text_selection_version="names-v1",
            embedding=(1.0, 0.0),
        ),
        MatchingIndexRow(
            concept_id="au:ibuprofen",
            mapping_level="ingredient",
            source_snapshot_id="fixture-snapshot",
            schema_version="1",
            text_selection_version="names-v1",
            embedding=(0.0, 1.0),
        ),
    )
    lineage = MatchingIndexLineage(
        index_version="fixture-v1",
        embedding_provider="externally-supplied",
        embedding_model="two-dimensional-fixture",
        embedding_version="1",
        generation_command="offline fixture generation",
        source_snapshot_sha256=sha256(b"fixture").hexdigest(),
        rights_state=RightsState.RESTRICTED,
    )

    first = generate_lancedb_index(rows, lineage, tmp_path)
    second = generate_lancedb_index(reversed(rows), lineage, tmp_path)
    identity = SemanticIndexIdentity(
        schema_version=first.manifest_version,
        index_version=lineage.index_version,
        index_digest=first.index_digest,
        embedding_model_id=lineage.embedding_model,
        embedding_model_revision=lineage.embedding_version,
        source_snapshot_digest=lineage.source_snapshot_sha256,
        vector_dimension=first.dimensions,
        row_count=first.row_count,
        rows_digest=first.rows_sha256,
        generated_at=datetime(2026, 7, 31, tzinfo=UTC),
    )
    retriever = optional_semantic_retriever(
        tmp_path,
        identity=identity,
        expected_identity=identity,
    )

    assert first == second
    assert retriever.available
    hits = retriever.search(
        [1.0, 0.0],
        mapping_level="ingredient",
        limit=1,
    )
    assert hits[0].concept_id == "nz:paracetamol"
    assert hits[0].index_version == "fixture-v1"


def test_lancedb_tampering_fails_closed_after_open(tmp_path: Path) -> None:
    row = MatchingIndexRow(
        concept_id="nz:paracetamol",
        mapping_level="ingredient",
        source_snapshot_id="fixture-snapshot",
        schema_version="1",
        text_selection_version="names-v1",
        embedding=(1.0, 0.0),
    )
    lineage = MatchingIndexLineage(
        index_version="fixture-v1",
        embedding_provider="externally-supplied",
        embedding_model="two-dimensional-fixture",
        embedding_version="1",
        generation_command="offline fixture generation",
        source_snapshot_sha256=sha256(b"fixture").hexdigest(),
        rights_state=RightsState.RESTRICTED,
    )
    manifest = generate_lancedb_index((row,), lineage, tmp_path)
    identity = SemanticIndexIdentity(
        schema_version=manifest.manifest_version,
        index_version=lineage.index_version,
        index_digest=manifest.index_digest,
        embedding_model_id=lineage.embedding_model,
        embedding_model_revision=lineage.embedding_version,
        source_snapshot_digest=lineage.source_snapshot_sha256,
        vector_dimension=manifest.dimensions,
        row_count=manifest.row_count,
        rows_digest=manifest.rows_sha256,
        generated_at=datetime(2026, 7, 31, tzinfo=UTC),
    )
    retriever = optional_semantic_retriever(
        tmp_path,
        identity=identity,
        expected_identity=identity,
    )
    assert retriever.available

    class MutableTable(Protocol):
        def update(
            self, *, where: str, values: dict[str, object]
        ) -> object: ...

    class MutableDatabase(Protocol):
        def open_table(self, name: str) -> MutableTable: ...

    class LanceDBModule(Protocol):
        def connect(self, uri: str) -> MutableDatabase: ...

    lancedb = cast("LanceDBModule", import_module("lancedb"))
    table = lancedb.connect(str(tmp_path)).open_table("medicine_embeddings")
    table.update(
        where="concept_id = 'nz:paracetamol'", values={"vector": [0.0, 1.0]}
    )

    with pytest.raises(ValueError, match="content"):
        retriever.search([1.0, 0.0], mapping_level="ingredient")


def test_lancedb_receipt_identity_mismatch_returns_fallback(
    tmp_path: Path,
) -> None:
    row = MatchingIndexRow(
        concept_id="nz:paracetamol",
        mapping_level="ingredient",
        source_snapshot_id="fixture-snapshot",
        schema_version="1",
        text_selection_version="names-v1",
        embedding=(1.0, 0.0),
    )
    lineage = MatchingIndexLineage(
        index_version="fixture-v1",
        embedding_provider="externally-supplied",
        embedding_model="two-dimensional-fixture",
        embedding_version="1",
        generation_command="offline fixture generation",
        source_snapshot_sha256=sha256(b"fixture").hexdigest(),
        rights_state=RightsState.RESTRICTED,
    )
    manifest = generate_lancedb_index((row,), lineage, tmp_path)
    governed = SemanticIndexIdentity(
        schema_version=manifest.manifest_version,
        index_version=lineage.index_version,
        index_digest=manifest.index_digest,
        embedding_model_id=lineage.embedding_model,
        embedding_model_revision=lineage.embedding_version,
        source_snapshot_digest=lineage.source_snapshot_sha256,
        vector_dimension=manifest.dimensions,
        row_count=manifest.row_count + 1,
        rows_digest=manifest.rows_sha256,
        generated_at=datetime(2026, 7, 31, tzinfo=UTC),
    )

    retriever = optional_semantic_retriever(
        tmp_path,
        identity=governed,
        expected_identity=governed,
    )

    assert not retriever.available
