"""Deterministic manifests and regeneration for derived matching indexes."""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path
from typing import Self

import orjson
from pydantic import Field, model_validator

from .models import FrozenModel
from .receipts import SHA256_PATTERN, RightsState


class MatchingIndexRow(FrozenModel):
    """One externally embedded canonical record."""

    concept_id: str = Field(min_length=1)
    mapping_level: str = Field(min_length=1)
    source_snapshot_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    text_selection_version: str = Field(min_length=1)
    embedding: tuple[float, ...] = Field(min_length=1)


class MatchingIndexLineage(FrozenModel):
    """Governance metadata required to reproduce a derived index."""

    index_version: str = Field(min_length=1)
    embedding_provider: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    embedding_version: str = Field(min_length=1)
    generation_command: str = Field(min_length=1)
    source_snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    rights_state: RightsState
    rights_reference: str | None = None
    redistributable: bool = False

    @model_validator(mode="after")
    def permitted_rights_have_reference(self) -> Self:
        if (
            self.rights_state is RightsState.PERMITTED
            and self.rights_reference is None
        ):
            raise ValueError("permitted rights require a rights reference")
        if (
            self.redistributable
            and self.rights_state is not RightsState.PERMITTED
        ):
            raise ValueError("redistribution requires permitted rights")
        return self


class MatchingIndexManifest(FrozenModel):
    """Content-addressed identity for one generated matching index."""

    manifest_version: str = "1"
    lineage: MatchingIndexLineage
    row_count: int = Field(ge=0)
    dimensions: int = Field(gt=0)
    rows_sha256: str = Field(pattern=SHA256_PATTERN)
    index_digest: str = Field(pattern=SHA256_PATTERN)


def canonical_rows(rows: Iterable[MatchingIndexRow]) -> bytes:
    ordered = sorted(
        rows,
        key=lambda row: (row.mapping_level, row.concept_id),
    )
    payload = [row.model_dump(mode="json") for row in ordered]
    return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)


def build_manifest(
    rows: Iterable[MatchingIndexRow],
    lineage: MatchingIndexLineage,
) -> MatchingIndexManifest:
    materialized = tuple(rows)
    if not materialized:
        raise ValueError("at least one index row is required")
    dimensions = len(materialized[0].embedding)
    if any(len(row.embedding) != dimensions for row in materialized):
        raise ValueError("all embeddings must have equal dimensions")
    if len({row.concept_id for row in materialized}) != len(materialized):
        raise ValueError("concept identifiers must be unique")
    rows_digest = sha256(canonical_rows(materialized)).hexdigest()
    identity = orjson.dumps(
        {
            "dimensions": dimensions,
            "lineage": lineage.model_dump(mode="json"),
            "row_count": len(materialized),
            "rows_sha256": rows_digest,
        },
        option=orjson.OPT_SORT_KEYS,
    )
    return MatchingIndexManifest(
        lineage=lineage,
        row_count=len(materialized),
        dimensions=dimensions,
        rows_sha256=rows_digest,
        index_digest=sha256(identity).hexdigest(),
    )


def generate_lancedb_index(
    rows: Iterable[MatchingIndexRow],
    lineage: MatchingIndexLineage,
    output_dir: Path,
    *,
    table_name: str = "medicine_embeddings",
) -> MatchingIndexManifest:
    """Regenerate a LanceDB index and deterministic metadata manifest."""

    materialized = tuple(rows)
    manifest = build_manifest(materialized, lineage)
    output_dir.mkdir(parents=True, exist_ok=True)
    lancedb = __import__("lancedb")
    database = lancedb.connect(str(output_dir))
    table_rows = [
        {
            "concept_id": row.concept_id,
            "mapping_level": row.mapping_level,
            "source_snapshot_id": row.source_snapshot_id,
            "schema_version": row.schema_version,
            "text_selection_version": row.text_selection_version,
            "vector": list(row.embedding),
        }
        for row in sorted(
            materialized,
            key=lambda item: (item.mapping_level, item.concept_id),
        )
    ]
    database.create_table(table_name, data=table_rows, mode="overwrite")
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(
        orjson.dumps(
            manifest.model_dump(mode="json"),
            option=orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE,
        )
    )
    return manifest
