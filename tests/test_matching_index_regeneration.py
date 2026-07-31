from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

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
