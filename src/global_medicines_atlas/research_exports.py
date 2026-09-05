"""Deterministic metadata manifests for reproducible research exports.

The manifest identifies a query result without embedding source or result
payloads.  It is therefore safe to commit to Git and can be rebuilt from the
same public Hugging Face revisions by a downstream researcher.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from .models import FrozenModel

EXPORT_MANIFEST_SCHEMA = "global-medicines-atlas.research-export"
EXPORT_MANIFEST_VERSION = 1


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class ExportSource(FrozenModel):
    """A pinned public data-plane object used by an export."""

    dataset_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)


class ExportCitation(FrozenModel):
    """A citation for a source or method, without source payload bytes."""

    citation_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    accessed_at: datetime | None = None


class QuerySnapshotManifest(FrozenModel):
    """Content-addressed identity for a metadata-only query snapshot."""

    schema_id: str = EXPORT_MANIFEST_SCHEMA
    schema_version: int = EXPORT_MANIFEST_VERSION
    query: Mapping[str, Any]
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_row_count: int = Field(ge=0)
    sources: tuple[ExportSource, ...] = Field(min_length=1)
    citations: tuple[ExportCitation, ...] = ()
    generated_at: datetime
    generator_commit: str = Field(min_length=1)

    @field_validator("query")
    @classmethod
    def query_is_json_object(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        _canonical_bytes(value)
        return value


def build_query_snapshot_manifest(
    *,
    query: Mapping[str, Any],
    result_rows: Sequence[Mapping[str, Any]],
    sources: Sequence[ExportSource],
    citations: Sequence[ExportCitation] = (),
    generated_at: datetime,
    generator_commit: str,
) -> QuerySnapshotManifest:
    """Build an order-stable manifest from metadata and an in-memory result.

    Rows are sorted by their canonical representation before hashing, making
    the identity stable when an equivalent query engine changes row order.
    Only the digest and count are retained; the result rows are never written.
    """
    if not sources:
        raise ValueError("A query snapshot requires at least one source")
    normalized_rows = sorted(_canonical_bytes(row) for row in result_rows)
    result_payload = b"[" + b",".join(normalized_rows) + b"]"
    return QuerySnapshotManifest(
        query=dict(query),
        query_sha256=_digest(query),
        result_sha256=hashlib.sha256(result_payload).hexdigest(),
        result_row_count=len(result_rows),
        sources=tuple(sorted(sources, key=lambda item: (item.dataset_id, item.revision, item.path))),
        citations=tuple(sorted(citations, key=lambda item: item.citation_id)),
        generated_at=generated_at,
        generator_commit=generator_commit,
    )


def canonical_manifest_bytes(manifest: QuerySnapshotManifest) -> bytes:
    """Serialize a manifest to deterministic UTF-8 JSON."""
    return _canonical_bytes(manifest.model_dump(mode="json"))


def manifest_sha256(manifest: QuerySnapshotManifest) -> str:
    """Return the content address of the canonical manifest."""
    return hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest()
