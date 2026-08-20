"""Deterministic batch-attestation tests."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from global_medicines_atlas.batch_attestation import (
    AttestationLeaf,
    build_experiment_receipt,
    build_inclusion_proof,
    build_merkle_manifest,
    verify_inclusion_proof,
)


def _leaf(name: str, payload: bytes) -> AttestationLeaf:
    return AttestationLeaf(
        content_id=name,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


LEAVES = (
    _leaf("content-a", b"alpha"),
    _leaf("content-b", b"beta"),
    _leaf("content-c", b"gamma"),
)


@pytest.mark.unit
def test_merkle_root_is_order_independent_and_domain_separated() -> None:
    forward = build_merkle_manifest(LEAVES)
    reverse = build_merkle_manifest(tuple(reversed(LEAVES)))

    assert forward == reverse
    assert forward.leaf_count == 3
    assert forward.ordered_content_ids == (
        "content-a",
        "content-b",
        "content-c",
    )
    assert forward.per_object_receipts_authoritative is True
    assert forward.non_membership_proofs_supported is False


@pytest.mark.unit
def test_inclusion_proof_verifies_for_every_leaf() -> None:
    manifest = build_merkle_manifest(LEAVES)

    for leaf in LEAVES:
        proof = build_inclusion_proof(LEAVES, leaf.content_id)
        assert proof.root_sha256 == manifest.root_sha256
        assert verify_inclusion_proof(proof) is True

    receipt = build_experiment_receipt(LEAVES)
    assert receipt.manifest == manifest
    assert receipt.all_inclusion_proofs_verified is True
    assert receipt.source_receipts_remain_authoritative is True


@pytest.mark.unit
def test_tampered_leaf_or_sibling_fails_verification() -> None:
    proof = build_inclusion_proof(LEAVES, "content-b")
    tampered_leaf = proof.model_copy(
        update={"leaf_sha256": hashlib.sha256(b"changed").hexdigest()}
    )
    assert verify_inclusion_proof(tampered_leaf) is False

    first = proof.steps[0].model_copy(
        update={"sibling_sha256": hashlib.sha256(b"changed").hexdigest()}
    )
    tampered_path = proof.model_copy(
        update={"steps": (first, *proof.steps[1:])}
    )
    assert verify_inclusion_proof(tampered_path) is False


@pytest.mark.unit
def test_incremental_update_changes_root_without_mutating_old_manifest() -> (
    None
):
    original = build_merkle_manifest(LEAVES)
    expanded = build_merkle_manifest((*LEAVES, _leaf("content-d", b"delta")))

    assert original.root_sha256 != expanded.root_sha256
    assert original.leaf_count == 3
    assert expanded.leaf_count == 4


@pytest.mark.unit
def test_empty_duplicate_and_absent_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_merkle_manifest(())
    with pytest.raises(ValueError, match="duplicate"):
        build_merkle_manifest((LEAVES[0], LEAVES[0]))
    with pytest.raises(KeyError, match="non-membership unsupported"):
        build_inclusion_proof(LEAVES, "missing")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"leaf_count": 2}, "leaf count"),
        (
            {"ordered_content_ids": ("content-b", "content-a", "content-c")},
            "canonical order",
        ),
        (
            {"ordered_content_ids": ("content-a", "content-a", "content-c")},
            "unique",
        ),
    ],
)
def test_manifest_rejects_inconsistent_leaf_inventory(
    updates: dict[str, object], message: str
) -> None:
    payload = build_merkle_manifest(LEAVES).model_dump(mode="json")
    payload.update(updates)

    with pytest.raises(ValidationError, match=message):
        type(build_merkle_manifest(LEAVES)).model_validate(payload)
