from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from global_medicines_atlas import semantic_retrieval
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
        "row_count": 2,
        "rows_digest": "c" * 64,
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
        setattr(governed, "vector_dimension", 3)  # ruff: ignore[set-attr-with-constant]
    with pytest.raises(ValidationError):
        identity(index_digest="not-a-digest")
    with pytest.raises(ValidationError):
        identity(row_count=0)
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
        lambda _name: pytest.fail("LanceDB must not be imported"),  # type: ignore[reportUnknownLambdaType]
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


def test_direct_retriever_connects_before_rejecting_invalid_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeDatabase:
        def open_table(self, name: str) -> object:
            observed["table_name"] = name
            return object()

    class FakeLanceDb:
        @staticmethod
        def connect(path: str) -> FakeDatabase:
            observed["path"] = path
            return FakeDatabase()

    monkeypatch.setattr(
        semantic_retrieval,
        "import_module",
        lambda _name: FakeLanceDb(),
    )
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="content receipt is invalid"):
        LanceDBSemanticRetriever(
            tmp_path,
            table_name="custom",
            identity=identity(),
            expected_identity=identity(),
        )

    assert observed == {
        "path": str(tmp_path),
        "table_name": "custom",
    }


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


@pytest.mark.parametrize(
    "missing",
    ["index_path", "identity", "expected_identity"],
)
def test_optional_retriever_requires_every_governed_input(
    missing: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values: dict[str, object] = {
        "index_path": tmp_path,
        "identity": identity(),
        "expected_identity": identity(),
    }
    values[missing] = None
    monkeypatch.setattr(
        semantic_retrieval,
        "LanceDBSemanticRetriever",
        lambda *_args, **_kwargs: pytest.fail(
            "incomplete identity must not open LanceDB"
        ),
    )

    retriever = optional_semantic_retriever(
        values["index_path"],  # type: ignore[arg-type]
        identity=values["identity"],  # type: ignore[arg-type]
        expected_identity=values["expected_identity"],  # type: ignore[arg-type]
    )

    assert isinstance(retriever, UnavailableSemanticRetriever)


@pytest.mark.parametrize(
    "error_type",
    [FileNotFoundError, ImportError, OSError, RuntimeError, ValueError],
)
def test_optional_retriever_falls_back_for_each_operational_failure(
    error_type: type[Exception],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise error_type("expected")

    monkeypatch.setattr(semantic_retrieval, "LanceDBSemanticRetriever", fail)
    retriever = optional_semantic_retriever(
        tmp_path,
        identity=identity(),
        expected_identity=identity(),
        table_name="custom",
    )

    assert isinstance(retriever, UnavailableSemanticRetriever)


def test_optional_retriever_preserves_constructor_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governed = identity()
    expected = identity()
    sentinel = UnavailableSemanticRetriever()
    observed: dict[str, object] = {}

    def construct(
        index_path: Path,
        *,
        table_name: str,
        identity: SemanticIndexIdentity,
        expected_identity: SemanticIndexIdentity,
    ) -> UnavailableSemanticRetriever:
        observed.update({
            "index_path": index_path,
            "table_name": table_name,
            "identity": identity,
            "expected_identity": expected_identity,
        })
        return sentinel

    monkeypatch.setattr(
        semantic_retrieval,
        "LanceDBSemanticRetriever",
        construct,
    )

    assert (
        optional_semantic_retriever(
            tmp_path,
            identity=governed,
            expected_identity=expected,
            table_name="custom",
        )
        is sentinel
    )
    assert observed == {
        "index_path": tmp_path,
        "table_name": "custom",
        "identity": governed,
        "expected_identity": expected,
    }


@pytest.mark.parametrize(
    "row",
    [
        {"vector": "not-a-vector"},
        {"vector": [0.1, "not-numeric"]},
    ],
)
def test_live_index_rows_reject_invalid_vectors(
    row: dict[str, object],
) -> None:
    matching_row = cast(
        "Callable[[dict[str, object]], object]",
        vars(semantic_retrieval)["_matching_row"],
    )

    with pytest.raises(TypeError, match="vector"):
        matching_row(row)
