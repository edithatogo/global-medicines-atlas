"""Deterministic, additive Merkle manifests for public object batches.

The Merkle root accelerates batch verification but never replaces the
source-native per-object SHA-256 receipts. Leaves bind source dataset,
revision, path, and object digest so source identity is covered by the root.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Literal

from pydantic import Field, field_validator

from .models import FrozenModel

MERKLE_SCHEMA = "global-medicines-atlas.merkle-manifest"
MERKLE_VERSION = 3


class MerkleLeaf(FrozenModel):
    """An object receipt retained alongside its batch proof."""

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_id: str = Field(min_length=1)
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")


class MerkleManifest(FrozenModel):
    """Content-addressed manifest for a deterministic object batch."""

    schema_id: str = MERKLE_SCHEMA
    schema_version: Literal[3] = MERKLE_VERSION
    leaves: tuple[MerkleLeaf, ...] = Field(min_length=1)
    root_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("leaves")
    @classmethod
    def unique_paths(
        cls, value: tuple[MerkleLeaf, ...]
    ) -> tuple[MerkleLeaf, ...]:
        paths = [leaf.path for leaf in value]
        if len(paths) != len(set(paths)):
            raise ValueError("Merkle leaf paths must be unique")
        return value


def _hash_pair(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"node\0" + left + right).digest()


def _leaf_hash(leaf: MerkleLeaf) -> bytes:
    identity = json.dumps(
        {
            "dataset_id": leaf.dataset_id,
            "path": leaf.path,
            "revision": leaf.revision,
            "sha256": leaf.sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"leaf\0" + identity).digest()


def merkle_root(leaves: Sequence[MerkleLeaf]) -> str:
    """Return the root for sorted leaves, duplicating the final odd node."""
    normalized = tuple(sorted(leaves, key=lambda leaf: leaf.path))
    if not normalized:
        raise ValueError("A Merkle manifest requires at least one leaf")
    if len({leaf.path for leaf in normalized}) != len(normalized):
        raise ValueError("Merkle leaf paths must be unique")
    level = [_leaf_hash(leaf) for leaf in normalized]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            _hash_pair(level[i], level[i + 1]) for i in range(0, len(level), 2)
        ]
    return level[0].hex()


def build_merkle_manifest(leaves: Sequence[MerkleLeaf]) -> MerkleManifest:
    """Build an order-independent manifest while retaining every receipt."""
    normalized = tuple(sorted(leaves, key=lambda leaf: leaf.path))
    return MerkleManifest(
        leaves=normalized, root_sha256=merkle_root(normalized)
    )


def verify_merkle_manifest(manifest: MerkleManifest) -> bool:
    """Verify both the leaf inventory and the stored root."""
    return merkle_root(manifest.leaves) == manifest.root_sha256


def canonical_merkle_manifest_bytes(manifest: MerkleManifest) -> bytes:
    """Serialize a manifest deterministically for a publication receipt."""
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
