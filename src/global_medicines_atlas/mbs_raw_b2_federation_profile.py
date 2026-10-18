"""Candidate-only MBS raw B2 receipt binding over federation v4.1.

This adapter joins supplied receipt bytes to the existing closure and
independent-profile admission primitives. It validates shape and identity; it
does not authenticate receipt issuers or establish rights, source authority,
producer claims, publication permission, or live M-112 admission.
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from pydantic import model_validator

from .federation_admission import (
    TrustedAdmissionProfile,
    admit_closed_contract,
)
from .federation_reader import SCHEMA_SHA256_V4_1
from .federation_receipt_closure import (
    ReceiptClosure,
    ReceiptPayload,
    verify_receipt_closure,
)
from .models import FrozenModel
from .strict_json import unique_json_object

_REQUIRED_ROLES = frozenset({
    "/publication/receipt",
    "/verification/receipt",
    "/rights/authorization",
    "/discovery/estate_entry",
    "/lineage/inputs/0",
    "/lineage/v1_conformance",
    "/lineage/v3_replay",
    "/recovery/checksum_inventory",
    "/cache/cleanup_receipt",
})
_REQUIRED_LINEAGE_ROLES = frozenset({
    "/lineage/inputs/0",
    "/lineage/v1_conformance",
    "/lineage/v3_replay",
})


class MbsRawB2CandidateProfile(FrozenModel):
    """Independently configured expectations for one MBS raw B2 candidate."""

    trusted: TrustedAdmissionProfile

    @model_validator(mode="after")
    def requires_raw_b2_v41_scope(self) -> MbsRawB2CandidateProfile:
        trusted = self.trusted
        identity = (
            trusted.schema_sha256,
            trusted.source_id,
            trusted.layer,
            trusted.bronze_stratum,
            trusted.representation,
        )
        expected = (SCHEMA_SHA256_V4_1, "au-mbs", "bronze", "B2", "raw")
        lineage_roles = {role.role for role in trusted.lineage}
        if (
            identity != expected
            or trusted.authorization.role != "/rights/authorization"
            or not lineage_roles >= _REQUIRED_LINEAGE_ROLES
        ):
            raise ValueError("MBS raw B2 candidate profile scope rejected")
        return self


class MbsRawB2Candidate(FrozenModel):
    """Synthetic or live-shape qualification result; always candidate-only."""

    schema_id: Literal["global-medicines-atlas.mbs-raw-b2-candidate"] = (
        "global-medicines-atlas.mbs-raw-b2-candidate"
    )
    schema_version: Literal[1] = 1
    status: Literal["candidate_only"] = "candidate_only"
    contract_sha256: str
    dataset: str
    revision: str
    path: str
    object_sha256: str
    receipt_closure: ReceiptClosure


def qualify_mbs_raw_b2_candidate(
    contract: bytes,
    receipts: tuple[ReceiptPayload, ...],
    *,
    schema: bytes,
    profile: MbsRawB2CandidateProfile,
) -> MbsRawB2Candidate:
    """Close supplied receipt bytes and qualify one independent MBS B2 identity.

    ``profile`` must be configured independently of ``contract``. Receipt
    closure verifies byte digests and role completeness only; the returned
    object remains candidate-only and is not a publication or remote-read
    authorization.
    """
    profile = MbsRawB2CandidateProfile.model_validate(
        profile.model_dump(mode="python")
    )
    closure = verify_receipt_closure(contract, receipts, schema=schema)
    try:
        document = cast(
            "dict[str, Any]",
            json.loads(contract, object_pairs_hook=unique_json_object),
        )
    except AttributeError, KeyError, TypeError, ValueError:
        raise ValueError("invalid MBS raw B2 candidate contract") from None
    source = cast("dict[str, Any]", document["source"])
    lineage = cast("dict[str, Any]", document["lineage"])
    source_identity = (
        source["source_id"],
        source["layer"],
        source["bronze_stratum"],
        source["representation"],
    )
    expected_identity = ("au-mbs", "bronze", "B2", "raw")
    actual_roles = {role.role for role in closure.roles}
    lineage_shape = (
        lineage["v2_field_lineage_applicability"],
        lineage["v2_field_lineage"],
    )
    if (
        source_identity != expected_identity
        or lineage_shape != ("not_applicable_raw_b2", None)
        or not actual_roles >= _REQUIRED_ROLES
        or "/lineage/v2_field_lineage" in actual_roles
    ):
        raise ValueError("invalid MBS raw B2 candidate contract")
    admission = admit_closed_contract(
        contract,
        closure,
        schema=schema,
        trusted=profile.trusted,
    )
    return MbsRawB2Candidate(
        contract_sha256=admission.contract_sha256,
        dataset=admission.dataset,
        revision=admission.revision,
        path=admission.path,
        object_sha256=admission.sha256,
        receipt_closure=closure,
    )
