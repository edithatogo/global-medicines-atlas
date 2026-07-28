"""Optional semantic candidate retrieval over externally supplied embeddings."""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from pydantic import Field

from .models import FrozenModel


class SemanticHit(FrozenModel):
    """A non-authoritative candidate returned by a semantic index."""

    concept_id: str = Field(min_length=1)
    mapping_level: str = Field(min_length=1)
    distance: float = Field(ge=0)
    index_version: str = Field(min_length=1)


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
        index_version: str,
    ) -> None:
        if not index_path.exists():
            raise FileNotFoundError(index_path)
        lancedb = import_module("lancedb")
        database = lancedb.connect(str(index_path))
        self._table = database.open_table(table_name)
        self._index_version = index_version

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
        if limit < 1:
            raise ValueError("limit must be positive")
        vector = tuple(float(value) for value in embedding)
        if not vector:
            raise ValueError("embedding must not be empty")
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
                index_version=self._index_version,
            )
            for row, distance in zip(rows, distances, strict=True)
        )


def optional_semantic_retriever(
    index_path: Path | None,
    *,
    table_name: str = "medicine_embeddings",
    index_version: str = "unavailable",
) -> SemanticRetriever:
    """Return a usable fallback when the optional index cannot be opened."""

    if index_path is None:
        return UnavailableSemanticRetriever()
    try:
        return LanceDBSemanticRetriever(
            index_path,
            table_name=table_name,
            index_version=index_version,
        )
    except FileNotFoundError, ImportError, OSError, RuntimeError, ValueError:
        return UnavailableSemanticRetriever()


def _quoted(value: str) -> str:
    return value.replace("'", "''")


def _distance(value: object) -> float:
    if not isinstance(value, int | float):
        raise TypeError("LanceDB result has no numeric distance")
    return float(value)
