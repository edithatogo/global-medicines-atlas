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
from .federation_receipt_closure import ReceiptClosure, ReceiptRole
from .models import FrozenModel

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class TrustedAdmissionProfile(FrozenModel):
    """Independently configured authority and exact subject expectations."""

    producer_repository: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(min_length=1)
    sha256: Digest
    source_id: str = Field(min_length=1)
    acquisition_id: str = Field(min_length=1)
    layer: Literal["bronze", "silver", "gold", "platinum"]
    bronze_stratum: Literal["B0", "B1", "B2"] | None
    evidence_kind: Literal["live", "historical", "synthetic"]
    authorization: ReceiptRole
    lineage: tuple[ReceiptRole, ...] = Field(min_length=1)


class AdmissionRecord(FrozenModel):
    """Exact admitted identity; it is not a publication or rights decision."""

    scope: Literal["offline_trusted_profile"] = "offline_trusted_profile"
    producer_repository: str
    dataset: str
    revision: str
    path: str
    sha256: Digest
    layer: str
    bronze_stratum: str | None
    contract_sha256: Digest


def admit_closed_contract(
    contract: bytes,
    closure: ReceiptClosure,
    *,
    trusted: TrustedAdmissionProfile,
) -> AdmissionRecord:
    """Admit only an exact byte-closed contract matching independent trust."""
    if closure.contract_sha256 != hashlib.sha256(contract).hexdigest():
        raise ValueError("receipt closure belongs to a different contract")
    try:
        document = json.loads(contract)
        authority = document["authority"]
        source = document["source"]
        location = document["location"]
    except TypeError, ValueError, KeyError:
        raise ValueError("invalid closed federation contract") from None
    actual = (
        authority["producer_repository"],
        location["dataset"],
        location["revision"],
        location["path"],
        location["sha256"],
        source["source_id"],
        source["acquisition_id"],
        source["layer"],
        source["bronze_stratum"],
        document["evidence_kind"],
    )
    expected = (
        trusted.producer_repository,
        trusted.dataset,
        trusted.revision,
        trusted.path,
        trusted.sha256,
        trusted.source_id,
        trusted.acquisition_id,
        trusted.layer,
        trusted.bronze_stratum,
        trusted.evidence_kind,
    )
    if actual != expected or authority["schema_sha256"] != SCHEMA_SHA256:
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
        dataset=trusted.dataset,
        revision=trusted.revision,
        path=trusted.path,
        sha256=trusted.sha256,
        layer=trusted.layer,
        bronze_stratum=trusted.bronze_stratum,
        contract_sha256=closure.contract_sha256,
    )
