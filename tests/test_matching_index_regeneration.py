from hashlib import sha256
from pathlib import Path

from global_medicines_atlas.matching_indexes import (
    MatchingIndexLineage,
    MatchingIndexRow,
    generate_lancedb_index,
)
from global_medicines_atlas.receipts import RightsState
from global_medicines_atlas.semantic_retrieval import (
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
    retriever = optional_semantic_retriever(
        tmp_path,
        index_version=lineage.index_version,
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
