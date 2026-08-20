"""Additive SHA-256 Merkle attestations over authoritative object receipts."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenModel

_HASH_PATTERN = r"^[0-9a-f]{64}$"


class AttestationLeaf(FrozenModel):
    content_id: str = Field(min_length=1)
    sha256: str = Field(pattern=_HASH_PATTERN)


class MerkleManifest(FrozenModel):
    schema_id: Literal["global-medicines-atlas.merkle-manifest"]
    schema_version: Literal[1]
    algorithm: Literal["sha256-domain-separated-binary-tree-v1"]
    leaf_count: int = Field(ge=1)
    root_sha256: str = Field(pattern=_HASH_PATTERN)
    ordered_content_ids: tuple[str, ...] = Field(min_length=1)
    per_object_receipts_authoritative: Literal[True] = True
    non_membership_proofs_supported: Literal[False] = False

    @model_validator(mode="after")
    def count_matches_ids(self) -> MerkleManifest:
        if self.leaf_count != len(self.ordered_content_ids):
            raise ValueError(
                "leaf count must match ordered content identifiers"
            )
        if tuple(sorted(self.ordered_content_ids)) != self.ordered_content_ids:
            raise ValueError("content identifiers must use canonical order")
        if len(set(self.ordered_content_ids)) != self.leaf_count:
            raise ValueError("content identifiers must be unique")
        return self


class ProofStep(FrozenModel):
    side: Literal["left", "right"]
    sibling_sha256: str = Field(pattern=_HASH_PATTERN)


class InclusionProof(FrozenModel):
    content_id: str = Field(min_length=1)
    leaf_sha256: str = Field(pattern=_HASH_PATTERN)
    steps: tuple[ProofStep, ...]
    root_sha256: str = Field(pattern=_HASH_PATTERN)


class MerkleExperimentReceipt(FrozenModel):
    schema_id: Literal["global-medicines-atlas.merkle-experiment-receipt"]
    schema_version: Literal[1]
    manifest: MerkleManifest
    proofs: tuple[InclusionProof, ...] = Field(min_length=1)
    all_inclusion_proofs_verified: Literal[True]
    source_receipts_remain_authoritative: Literal[True] = True


def _leaf_bytes(leaf: AttestationLeaf) -> bytes:
    return json.dumps(
        leaf.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _leaf_hash(leaf: AttestationLeaf) -> bytes:
    return hashlib.sha256(b"\x00" + _leaf_bytes(leaf)).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _canonical_leaves(
    leaves: tuple[AttestationLeaf, ...],
) -> tuple[AttestationLeaf, ...]:
    if not leaves:
        raise ValueError("Merkle manifest requires at least one leaf")
    ordered = tuple(sorted(leaves, key=lambda item: item.content_id))
    identifiers = tuple(item.content_id for item in ordered)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate content identifier")
    return ordered


def _next_level(level: tuple[bytes, ...]) -> tuple[bytes, ...]:
    nodes: list[bytes] = []
    for index in range(0, len(level), 2):
        left = level[index]
        right = level[index + 1] if index + 1 < len(level) else left
        nodes.append(_node_hash(left, right))
    return tuple(nodes)


def _root(level: tuple[bytes, ...]) -> bytes:
    if not level:
        raise RuntimeError("Merkle level unexpectedly empty")
    return level[0]


def build_merkle_manifest(
    leaves: tuple[AttestationLeaf, ...],
) -> MerkleManifest:
    """Build an order-independent manifest without replacing leaf receipts."""

    ordered = _canonical_leaves(leaves)
    level = tuple(_leaf_hash(leaf) for leaf in ordered)
    while len(level) > 1:
        level = _next_level(level)
    return MerkleManifest(
        schema_id="global-medicines-atlas.merkle-manifest",
        schema_version=1,
        algorithm="sha256-domain-separated-binary-tree-v1",
        leaf_count=len(ordered),
        root_sha256=_root(level).hex(),
        ordered_content_ids=tuple(leaf.content_id for leaf in ordered),
    )


def build_inclusion_proof(
    leaves: tuple[AttestationLeaf, ...], content_id: str
) -> InclusionProof:
    """Build a membership proof; absence proofs are explicitly unsupported."""

    ordered = _canonical_leaves(leaves)
    identifiers = tuple(leaf.content_id for leaf in ordered)
    if content_id not in identifiers:
        raise KeyError(
            "content identifier is absent; non-membership unsupported"
        )
    index = identifiers.index(content_id)
    leaf = ordered[index]
    level = tuple(_leaf_hash(item) for item in ordered)
    steps: list[ProofStep] = []
    while len(level) > 1:
        is_right = index % 2 == 1
        sibling_index = index - 1 if is_right else index + 1
        if sibling_index >= len(level):
            sibling_index = index
        steps.append(
            ProofStep(
                side="left" if is_right else "right",
                sibling_sha256=level[sibling_index].hex(),
            )
        )
        level = _next_level(level)
        index //= 2
    return InclusionProof(
        content_id=content_id,
        leaf_sha256=leaf.sha256,
        steps=tuple(steps),
        root_sha256=_root(level).hex(),
    )


def verify_inclusion_proof(proof: InclusionProof) -> bool:
    """Verify a proof against its bound root and per-object digest."""

    current = _leaf_hash(
        AttestationLeaf(
            content_id=proof.content_id,
            sha256=proof.leaf_sha256,
        )
    )
    for step in proof.steps:
        sibling = bytes.fromhex(step.sibling_sha256)
        current = (
            _node_hash(sibling, current)
            if step.side == "left"
            else _node_hash(current, sibling)
        )
    return current.hex() == proof.root_sha256


def build_experiment_receipt(
    leaves: tuple[AttestationLeaf, ...],
) -> MerkleExperimentReceipt:
    """Build and verify the additive manifest plus all inclusion proofs."""

    manifest = build_merkle_manifest(leaves)
    proofs = tuple(
        build_inclusion_proof(leaves, content_id)
        for content_id in manifest.ordered_content_ids
    )
    if not all(verify_inclusion_proof(proof) for proof in proofs):
        raise RuntimeError("generated inclusion proof failed verification")
    return MerkleExperimentReceipt(
        schema_id="global-medicines-atlas.merkle-experiment-receipt",
        schema_version=1,
        manifest=manifest,
        proofs=proofs,
        all_inclusion_proofs_verified=True,
    )
