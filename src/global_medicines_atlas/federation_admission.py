"""Independent offline admission of byte-closed federation v4 contracts.

The trust profile is caller-governed and must not be derived from the contract.
Admission performs no I/O and confers neither publication nor rights authority.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field

from .federation_reader import SCHEMA_SHA256
from .federation_receipt_closure import (
    ReceiptClosure,
    ReceiptRole,
    contract_receipt_roles,
)
from .models import FrozenModel
from .strict_json import unique_json_object

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class TrustedAdmissionProfile(FrozenModel):
    """Independently configured authority and exact subject expectations."""

    producer_repository: str = Field(min_length=1)
    contract_repository: str = Field(min_length=1)
    contract_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    schema_sha256: Digest
    dataset: str = Field(min_length=1)
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(min_length=1)
    byte_count: int = Field(ge=0)
    sha256: Digest
    source_id: str = Field(min_length=1)
    acquisition_id: str = Field(min_length=1)
    layer: Literal["bronze", "silver", "gold", "platinum"]
    bronze_stratum: Literal["B0", "B1", "B2"] | None
    representation: Literal["index", "metadata", "raw", "projection"]
    schema_era: str = Field(min_length=1)
    comparison_cohort: Literal["legacy", "current", "synthetic"]
    effective_date: str | None
    retrieved_at: str = Field(min_length=1)
    evidence_kind: Literal["live", "synthetic"]
    authorization: ReceiptRole
    lineage: tuple[ReceiptRole, ...] = Field(min_length=1)


class AdmissionRecord(FrozenModel):
    """Exact admitted identity; it is not a publication or rights decision."""

    scope: Literal["offline_trusted_profile"] = "offline_trusted_profile"
    producer_repository: str
    contract_repository: str
    contract_commit: str
    schema_sha256: Digest
    evidence_kind: Literal["live", "synthetic"]
    dataset: str
    revision: str
    path: str
    byte_count: int = Field(ge=0)
    sha256: Digest
    layer: Literal["bronze", "silver", "gold", "platinum"]
    bronze_stratum: Literal["B0", "B1", "B2"] | None
    representation: Literal["index", "metadata", "raw", "projection"]
    source_id: str
    acquisition_id: str
    schema_era: str
    comparison_cohort: Literal["legacy", "current", "synthetic"]
    effective_date: str | None
    retrieved_at: str
    contract_sha256: Digest


def admit_closed_contract(
    contract: bytes,
    closure: ReceiptClosure,
    *,
    schema: bytes,
    trusted: TrustedAdmissionProfile,
) -> AdmissionRecord:
    """Admit only an exact byte-closed contract matching independent trust."""
    if closure.contract_sha256 != hashlib.sha256(contract).hexdigest():
        raise ValueError("receipt closure belongs to a different contract")
    if closure.roles != contract_receipt_roles(contract, schema=schema):
        raise ValueError("receipt closure roles belong to a different contract")
    document = json.loads(contract, object_pairs_hook=unique_json_object)
    authority = document["authority"]
    source = document["source"]
    location = document["location"]
    actual = (
        authority["producer_repository"],
        authority["contract_repository"],
        authority["contract_commit"],
        authority["schema_sha256"],
        document["evidence_kind"],
        location["dataset"],
        location["revision"],
        location["path"],
        location["bytes"],
        location["sha256"],
        source["source_id"],
        source["acquisition_id"],
        source["layer"],
        source["bronze_stratum"],
        source["representation"],
        source["schema_era"],
        source["comparison_cohort"],
        source["effective_date"],
        source["retrieved_at"],
    )
    expected = (
        trusted.producer_repository,
        trusted.contract_repository,
        trusted.contract_commit,
        trusted.schema_sha256,
        trusted.evidence_kind,
        trusted.dataset,
        trusted.revision,
        trusted.path,
        trusted.byte_count,
        trusted.sha256,
        trusted.source_id,
        trusted.acquisition_id,
        trusted.layer,
        trusted.bronze_stratum,
        trusted.representation,
        trusted.schema_era,
        trusted.comparison_cohort,
        trusted.effective_date,
        trusted.retrieved_at,
    )
    if actual != expected or trusted.schema_sha256 != SCHEMA_SHA256:
        raise ValueError("contract identity is not independently trusted")
    roles = {role.role: role for role in closure.roles}
    if roles.get("/rights/authorization") != trusted.authorization:
        raise ValueError("authorization receipt is not independently trusted")
    actual_lineage = tuple(
        sorted(
            (
                role
                for role in closure.roles
                if role.role.startswith("/lineage/")
            ),
            key=lambda role: role.role,
        )
    )
    if actual_lineage != tuple(
        sorted(trusted.lineage, key=lambda role: role.role)
    ):
        raise ValueError("lineage receipts are not independently trusted")
    return AdmissionRecord(
        producer_repository=trusted.producer_repository,
        contract_repository=trusted.contract_repository,
        contract_commit=trusted.contract_commit,
        schema_sha256=trusted.schema_sha256,
        evidence_kind=trusted.evidence_kind,
        dataset=trusted.dataset,
        revision=trusted.revision,
        path=trusted.path,
        byte_count=trusted.byte_count,
        sha256=trusted.sha256,
        layer=trusted.layer,
        bronze_stratum=trusted.bronze_stratum,
        representation=trusted.representation,
        source_id=trusted.source_id,
        acquisition_id=trusted.acquisition_id,
        schema_era=trusted.schema_era,
        comparison_cohort=trusted.comparison_cohort,
        effective_date=trusted.effective_date,
        retrieved_at=trusted.retrieved_at,
        contract_sha256=closure.contract_sha256,
    )
