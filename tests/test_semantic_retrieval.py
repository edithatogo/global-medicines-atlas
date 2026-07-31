from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.semantic_retrieval import (
    LanceDBSemanticRetriever,
    SemanticHit,
    SemanticIndexIdentity,
    UnavailableSemanticRetriever,
    augment_authoritative_candidates,
    optional_semantic_retriever,
)

DIGEST = "a" * 64


def identity(**overrides: object) -> SemanticIndexIdentity:
    values: dict[str, object] = {
        "schema_version": "semantic-index-v1",
        "index_version": "fixture-v1",
        "index_digest": DIGEST,
        "embedding_model_id": "maintainer/model",
        "embedding_model_revision": "revision-1",
        "source_snapshot_digest": "b" * 64,
        "vector_dimension": 2,
        "generated_at": datetime(2026, 7, 31, tzinfo=UTC),
    }
    values.update(overrides)
    return SemanticIndexIdentity.model_validate(values)


def test_unavailable_semantic_retrieval_is_deterministic() -> None:
    retriever = UnavailableSemanticRetriever()

    assert not retriever.available
    assert retriever.search([0.1, 0.2], mapping_level="ingredient") == ()


def test_missing_index_returns_operational_fallback(tmp_path: Path) -> None:
    expected = identity()
    retriever = optional_semantic_retriever(
        tmp_path / "missing",
        identity=expected,
        expected_identity=expected,
    )

    assert not retriever.available
    assert retriever.search([0.1], mapping_level="product") == ()


def test_semantic_identity_is_immutable_and_content_bound() -> None:
    governed = identity()

    with pytest.raises(ValidationError):
        governed.vector_dimension = 3  # type: ignore[misc]
    with pytest.raises(ValidationError):
        identity(index_digest="not-a-digest")
    with pytest.raises(ValidationError):
        identity(
            # An explicit negative-control fixture must remain timezone-naive.
            generated_at=datetime(  # ruff: ignore[call-datetime-without-tzinfo]
                2026, 7, 31
            )
        )


def test_identity_mismatch_fails_closed_before_lancedb_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "global_medicines_atlas.semantic_retrieval.import_module",
        lambda _name: pytest.fail("LanceDB must not be imported"),
    )

    retriever = optional_semantic_retriever(
        tmp_path,
        identity=identity(),
        expected_identity=identity(embedding_model_revision="revision-2"),
    )

    assert not retriever.available


def test_direct_retriever_rejects_identity_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="identity"):
        LanceDBSemanticRetriever(
            tmp_path,
            table_name="medicine_embeddings",
            identity=identity(),
            expected_identity=identity(source_snapshot_digest="c" * 64),
        )


def test_semantic_candidates_only_augment_authoritative_order() -> None:
    hits = (
        SemanticHit(
            concept_id="exact",
            mapping_level="ingredient",
            distance=0.01,
            index_version="semantic-index-v1",
        ),
        SemanticHit(
            concept_id="semantic-only",
            mapping_level="ingredient",
            distance=0.02,
            index_version="semantic-index-v1",
        ),
    )

    assert augment_authoritative_candidates(("exact", "lexical"), hits) == (
        "exact",
        "lexical",
        "semantic-only",
    )
