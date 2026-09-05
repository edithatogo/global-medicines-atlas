"""Additive, credential-free verification-cost receipts for frontier manifests.

The receipt describes deterministic work required to verify a Merkle manifest. It
does not replace per-object SHA-256 evidence, claim a signature, or measure
wall-clock performance. This keeps the frontier experiment useful on an empty
machine and avoids introducing a trust anchor that has not been authorised.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from .frontier_merkle import (
    MerkleManifest,
    canonical_merkle_manifest_bytes,
    merkle_root,
)
from .models import FrozenModel

ATTESTATION_SCHEMA = "global-medicines-atlas.frontier-verification-receipt"
ATTESTATION_VERSION = 1


class VerificationCostReceipt(FrozenModel):
    """Deterministic verification-cost evidence bound to one manifest."""

    schema_id: Literal["global-medicines-atlas.frontier-verification-receipt"]
    schema_version: Literal[1]
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_root_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    leaf_count: int = Field(strict=True, gt=0)
    object_sha256_checks: int = Field(strict=True, gt=0)
    merkle_leaf_hashes: int = Field(strict=True, gt=0)
    merkle_pair_hashes: int = Field(strict=True, ge=0)
    verification_mode: Literal["per_object_sha256_plus_merkle"]
    signature_state: Literal["not_attested"]

    @model_validator(mode="after")
    def cost_shape(self) -> VerificationCostReceipt:
        if self.object_sha256_checks != self.leaf_count:
            raise ValueError(
                "object SHA-256 checks must cover every manifest leaf"
            )
        if self.merkle_leaf_hashes != self.leaf_count:
            raise ValueError(
                "Merkle leaf hashes must cover every manifest leaf"
            )
        return self


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_verification_cost_receipt(
    manifest: MerkleManifest,
) -> VerificationCostReceipt:
    """Build deterministic work-count evidence without reading object payloads."""
    leaf_count = len(manifest.leaves)
    # The tree duplicates an odd final node at each level, so count the actual
    # pair hashes performed by the verifier rather than assuming n-1.
    level = leaf_count
    pair_hashes = 0
    while level > 1:
        pair_hashes += (level + 1) // 2
        level = (level + 1) // 2
    return VerificationCostReceipt(
        schema_id=ATTESTATION_SCHEMA,
        schema_version=ATTESTATION_VERSION,
        manifest_sha256=_sha256(canonical_merkle_manifest_bytes(manifest)),
        manifest_root_sha256=manifest.root_sha256,
        leaf_count=leaf_count,
        object_sha256_checks=leaf_count,
        merkle_leaf_hashes=leaf_count,
        merkle_pair_hashes=pair_hashes,
        verification_mode="per_object_sha256_plus_merkle",
        signature_state="not_attested",
    )


def verify_verification_cost_receipt(
    manifest: MerkleManifest, receipt: VerificationCostReceipt
) -> bool:
    """Verify receipt binding and manifest integrity, retaining object checks."""
    expected = build_verification_cost_receipt(manifest)
    return (
        receipt == expected
        and merkle_root(manifest.leaves) == receipt.manifest_root_sha256
    )


def canonical_verification_cost_bytes(
    receipt: VerificationCostReceipt,
) -> bytes:
    """Serialize the receipt deterministically for an evidence ledger."""
    return (
        json.dumps(
            receipt.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
