"""Optional semantic candidate retrieval over externally supplied embeddings."""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from pydantic import AwareDatetime, Field

from .matching_indexes import (
    MatchingIndexManifest,
    MatchingIndexRow,
    build_manifest,
)
from .models import FrozenModel


class SemanticHit(FrozenModel):
    """A non-authoritative candidate returned by a semantic index."""

    concept_id: str = Field(min_length=1)
    mapping_level: str = Field(min_length=1)
    distance: float = Field(ge=0)
    index_version: str = Field(min_length=1)


class SemanticIndexIdentity(FrozenModel):
    """Immutable identity binding a derived index to governed inputs."""

    schema_version: str = Field(min_length=1)
    index_version: str = Field(min_length=1)
    index_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_model_id: str = Field(min_length=1)
    embedding_model_revision: str = Field(min_length=1)
    source_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    vector_dimension: int = Field(gt=0)
    row_count: int = Field(gt=0)
    rows_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: AwareDatetime


class SemanticRetriever(Protocol):
    """Candidate retrieval boundary; matching does not depend on availability."""

    @property
    def available(self) -> bool: ...

    def search(
        self,
        embedding: Sequence[float],
        *,
        mapping_level: str,
        limit: int = 10,
    ) -> tuple[SemanticHit, ...]: ...


class UnavailableSemanticRetriever:
    """Deterministic fallback used when no governed index is available."""

    @property
    def available(self) -> bool:
        return False

    def search(
        self,
        embedding: Sequence[float],
        *,
        mapping_level: str,
        limit: int = 10,
    ) -> tuple[SemanticHit, ...]:
        del embedding, mapping_level, limit
        return ()


class LanceDBSemanticRetriever:
    """Thin optional LanceDB adapter over a pre-generated index."""

    def __init__(
        self,
        index_path: Path,
        *,
        table_name: str,
        identity: SemanticIndexIdentity,
        expected_identity: SemanticIndexIdentity,
    ) -> None:
        if not index_path.exists():
            raise FileNotFoundError(index_path)
        if identity != expected_identity:
            raise ValueError(
                "semantic index identity does not match expectation"
            )
        lancedb = import_module("lancedb")
        database = lancedb.connect(str(index_path))
        self._database = database
        self._table_name = table_name
        self._table = database.open_table(table_name)
        self._index_path = index_path
        self._identity = identity
        self._verify_content()

    @property
    def available(self) -> bool:
        return True

    def search(
        self,
        embedding: Sequence[float],
        *,
        mapping_level: str,
        limit: int = 10,
    ) -> tuple[SemanticHit, ...]:
        self._verify_content()
        if limit < 1:
            raise ValueError("limit must be positive")
        vector = tuple(float(value) for value in embedding)
        if not vector:
            raise ValueError("embedding must not be empty")
        if len(vector) != self._identity.vector_dimension:
            raise ValueError(
                "embedding dimension does not match index identity"
            )
        query = self._table.search(list(vector)).where(
            f"mapping_level = '{_quoted(mapping_level)}'"
        )
        rows = cast(
            "list[dict[str, object]]",
            query.limit(limit).to_list(),
        )
        distances = tuple(_distance(row.get("_distance")) for row in rows)
        return tuple(
            SemanticHit(
                concept_id=str(row["concept_id"]),
                mapping_level=str(row["mapping_level"]),
                distance=distance,
                index_version=self._identity.index_version,
            )
            for row, distance in zip(rows, distances, strict=True)
        )

    def _verify_content(self) -> None:
        """Recompute the governed receipt from live index rows."""

        manifest_path = self._index_path / "manifest.json"
        try:
            self._table = self._database.open_table(self._table_name)
            manifest = MatchingIndexManifest.model_validate_json(
                manifest_path.read_bytes()
            )
            live_rows = tuple(
                _matching_row(row)
                for row in cast(
                    "list[dict[str, object]]",
                    self._table
                    .search()
                    .limit(manifest.row_count + 1)
                    .to_list(),
                )
            )
            actual = build_manifest(live_rows, manifest.lineage)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ValueError(
                "semantic index content receipt is invalid"
            ) from error

        expected = self._identity
        receipt_identity = (
            manifest.manifest_version,
            manifest.lineage.index_version,
            manifest.index_digest,
            manifest.lineage.embedding_model,
            manifest.lineage.embedding_version,
            manifest.lineage.source_snapshot_sha256,
            manifest.dimensions,
            manifest.row_count,
            manifest.rows_sha256,
        )
        declared_identity = (
            expected.schema_version,
            expected.index_version,
            expected.index_digest,
            expected.embedding_model_id,
            expected.embedding_model_revision,
            expected.source_snapshot_digest,
            expected.vector_dimension,
            expected.row_count,
            expected.rows_digest,
        )
        if manifest != actual or receipt_identity != declared_identity:
            raise ValueError("semantic index content does not match identity")


def optional_semantic_retriever(
    index_path: Path | None,
    *,
    identity: SemanticIndexIdentity | None = None,
    expected_identity: SemanticIndexIdentity | None = None,
    table_name: str = "medicine_embeddings",
) -> SemanticRetriever:
    """Return a usable fallback when the optional index cannot be opened."""

    if index_path is None or identity is None or expected_identity is None:
        return UnavailableSemanticRetriever()
    try:
        return LanceDBSemanticRetriever(
            index_path,
            table_name=table_name,
            identity=identity,
            expected_identity=expected_identity,
        )
    except FileNotFoundError, ImportError, OSError, RuntimeError, ValueError:
        return UnavailableSemanticRetriever()


def augment_authoritative_candidates(
    authoritative_concept_ids: Sequence[str],
    semantic_hits: Sequence[SemanticHit],
) -> tuple[str, ...]:
    """Append semantic candidates without replacing authoritative ordering."""

    ordered = list(dict.fromkeys(authoritative_concept_ids))
    seen = set(ordered)
    for hit in semantic_hits:
        if hit.concept_id not in seen:
            ordered.append(hit.concept_id)
            seen.add(hit.concept_id)
    return tuple(ordered)


def _quoted(value: str) -> str:
    return value.replace("'", "''")


def _distance(value: object) -> float:
    if not isinstance(value, int | float):
        raise TypeError("LanceDB result has no numeric distance")
    return float(value)


def _matching_row(row: dict[str, object]) -> MatchingIndexRow:
    vector = row["vector"]
    if not isinstance(vector, Sequence) or isinstance(vector, str | bytes):
        raise TypeError("semantic index vector is invalid")
    values = cast("Sequence[object]", vector)
    numeric_vector = tuple(_vector_value(value) for value in values)
    return MatchingIndexRow(
        concept_id=str(row["concept_id"]),
        mapping_level=str(row["mapping_level"]),
        source_snapshot_id=str(row["source_snapshot_id"]),
        schema_version=str(row["schema_version"]),
        text_selection_version=str(row["text_selection_version"]),
        embedding=numeric_vector,
    )


def _vector_value(value: object) -> float:
    if not isinstance(value, int | float):
        raise TypeError("semantic index vector value is invalid")
    return float(value)
