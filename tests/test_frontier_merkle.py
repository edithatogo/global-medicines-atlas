import hashlib

import pytest

from global_medicines_atlas.frontier_merkle import (
    MerkleLeaf,
    build_merkle_manifest,
    canonical_merkle_manifest_bytes,
    merkle_root,
    verify_merkle_manifest,
)


def _leaf(path: str, value: str = "a") -> MerkleLeaf:
    return MerkleLeaf(path=path, sha256=hashlib.sha256(value.encode()).hexdigest())


@pytest.mark.unit
def test_root_and_manifest_are_order_stable() -> None:
    first = build_merkle_manifest([_leaf("b", "2"), _leaf("a", "1")])
    second = build_merkle_manifest([_leaf("a", "1"), _leaf("b", "2")])
    assert first.root_sha256 == second.root_sha256
    assert canonical_merkle_manifest_bytes(first) == canonical_merkle_manifest_bytes(second)
    assert verify_merkle_manifest(first)


@pytest.mark.edge
def test_mutation_and_missing_leaf_change_root() -> None:
    leaves = [_leaf("a", "1"), _leaf("b", "2"), _leaf("c", "3")]
    root = merkle_root(leaves)
    assert merkle_root(leaves[:2]) != root
    assert merkle_root([_leaf("a", "changed"), *leaves[1:]]) != root


@pytest.mark.edge
def test_duplicate_paths_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        build_merkle_manifest([_leaf("a", "1"), _leaf("a", "2")])
