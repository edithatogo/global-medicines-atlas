"""Credential-free additive verification-cost receipt tests."""

import pytest

from global_medicines_atlas.frontier_attestation import (
    build_verification_cost_receipt,
    canonical_verification_cost_bytes,
    verify_verification_cost_receipt,
)
from global_medicines_atlas.frontier_merkle import (
    MerkleLeaf,
    build_merkle_manifest,
)


def _manifest(count: int = 3):
    return build_merkle_manifest([
        MerkleLeaf(path=f"objects/{index}", sha256=f"{index + 1:064x}")
        for index in range(count)
    ])


def test_receipt_binds_manifest_and_counts_base_object_checks() -> None:
    manifest = _manifest()
    receipt = build_verification_cost_receipt(manifest)

    assert receipt.leaf_count == 3
    assert receipt.object_sha256_checks == 3
    assert receipt.merkle_leaf_hashes == 3
    assert receipt.merkle_pair_hashes == 3
    assert receipt.signature_state == "not_attested"
    assert verify_verification_cost_receipt(manifest, receipt)
    assert canonical_verification_cost_bytes(receipt).endswith(b"\n")


def test_receipt_rejects_manifest_or_cost_mutation() -> None:
    manifest = _manifest()
    receipt = build_verification_cost_receipt(manifest)

    altered_manifest = _manifest(2)
    assert not verify_verification_cost_receipt(altered_manifest, receipt)
    altered_receipt = receipt.model_copy(update={"merkle_pair_hashes": 2})
    assert not verify_verification_cost_receipt(manifest, altered_receipt)


def test_receipt_requires_one_sha_check_per_leaf() -> None:
    receipt = build_verification_cost_receipt(_manifest()).model_dump(
        mode="json"
    )
    receipt["object_sha256_checks"] = 2
    with pytest.raises(ValueError, match="cover every manifest leaf"):
        type(build_verification_cost_receipt(_manifest())).model_validate(
            receipt
        )
