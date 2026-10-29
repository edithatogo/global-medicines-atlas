"""Provision consumer resources from independently governed admission profiles.

The profile supplies authority; candidate contracts and receipt bytes are
untrusted inputs. This adapter performs no network, publication or release.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated

from pydantic import Field

from .federation_admission import TrustedAdmissionProfile, admit_closed_contract
from .federation_distribution import ProducedObject, reconcile_distribution
from .federation_receipt_closure import (
    ReceiptPayload,
    ReceiptRole,
    verify_receipt_closure,
)
from .models import FrozenModel
from .platinum_configuration import ResourceConfiguration
from .platinum_resolver import SEMANTIC_MANIFEST_BYTES
from .platinum_types import (
    RESOURCE_ID_PATTERN,
    EntityGranularity,
    PlatinumSemanticDimension,
    validate_granularity_dimension,
)
from .strict_json import unique_json_object

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ProductAdmissionProfile(FrozenModel):
    """Separately governed subject, every receipt role, and product semantics."""

    resource_id: str = Field(pattern=RESOURCE_ID_PATTERN, max_length=128)
    semantic_dimension: PlatinumSemanticDimension
    entity_granularity: EntityGranularity
    semantic_sha256: Digest
    subject: TrustedAdmissionProfile
    receipt_roles: tuple[ReceiptRole, ...] = Field(min_length=1, max_length=256)


def admit_product_configuration(
    contract: bytes,
    receipts: tuple[ReceiptPayload, ...],
    semantic_manifest: bytes,
    *,
    schema: bytes,
    profile: ProductAdmissionProfile,
    contract_path: str,
    semantic_path: str,
) -> ResourceConfiguration:
    """Close exact receipts and provision one resource under external trust.

    Approval of the profile and the claims in its receipts must be established
    by the caller. Digest closure alone does not establish either authority.
    """
    profile = ProductAdmissionProfile.model_validate(
        profile.model_dump(mode="python")
    )
    validate_granularity_dimension(
        profile.semantic_dimension, profile.entity_granularity
    )
    closure = verify_receipt_closure(contract, receipts, schema=schema)
    expected_roles = sorted(profile.receipt_roles, key=lambda item: item.role)
    if len({item.role for item in expected_roles}) != len(expected_roles):
        raise ValueError("trusted product receipt roles are duplicated")
    if sorted(closure.roles, key=lambda item: item.role) != expected_roles:
        raise ValueError(
            "product receipts differ from independently trusted roles"
        )
    admission = admit_closed_contract(
        contract, closure, schema=schema, trusted=profile.subject
    )
    if (
        len(semantic_manifest) > SEMANTIC_MANIFEST_BYTES
        or hashlib.sha256(semantic_manifest).hexdigest()
        != profile.semantic_sha256
    ):
        raise ValueError("product semantics differ from independent trust")
    manifest = json.loads(
        semantic_manifest, object_pairs_hook=unique_json_object
    )
    if manifest != {
        "version": "1.0",
        "resource_id": profile.resource_id,
        "semantic_dimension": profile.semantic_dimension,
        "entity_granularity": profile.entity_granularity,
        "contract_sha256": admission.contract_sha256,
    }:
        raise ValueError(
            "product semantic claims differ from independent trust"
        )
    trusted = profile.subject
    obj = ProducedObject(
        producer_repository=trusted.producer_repository,
        source_id=trusted.source_id,
        acquisition_id=trusted.acquisition_id,
        layer=trusted.layer,
        bronze_stratum=trusted.bronze_stratum,
        path=trusted.path,
        sha256=trusted.sha256,
        byte_count=trusted.byte_count,
        evidence_kind=trusted.evidence_kind,
    )
    binding = reconcile_distribution(
        [obj],
        [contract],
        schema=schema,
        destinations={trusted.layer: trusted.dataset},
    )[0]
    return ResourceConfiguration(
        resource_id=profile.resource_id,
        semantic_dimension=profile.semantic_dimension,
        entity_granularity=profile.entity_granularity,
        binding=binding,
        semantic_sha256=profile.semantic_sha256,
        admission=admission,
        contract_path=contract_path,
        semantic_path=semantic_path,
    )
