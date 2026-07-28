from pathlib import Path

from global_medicines_atlas.semantic_retrieval import (
    UnavailableSemanticRetriever,
    optional_semantic_retriever,
)


def test_unavailable_semantic_retrieval_is_deterministic() -> None:
    retriever = UnavailableSemanticRetriever()

    assert not retriever.available
    assert retriever.search([0.1, 0.2], mapping_level="ingredient") == ()


def test_missing_index_returns_operational_fallback(tmp_path: Path) -> None:
    retriever = optional_semantic_retriever(tmp_path / "missing")

    assert not retriever.available
    assert retriever.search([0.1], mapping_level="product") == ()
