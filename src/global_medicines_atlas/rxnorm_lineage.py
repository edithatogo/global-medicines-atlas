"""Governed lineage for RxNorm candidate resolution."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Self

from pydantic import AnyUrl, AwareDatetime, Field, model_validator

from .models import FrozenModel
from .receipts import SHA256_PATTERN, RightsState


class RxNormEndpointClass(StrEnum):
    """The trust and availability boundary used for a terminology query."""

    LOCAL_FIXTURE = "local_fixture"
    LOCAL_RXNAV = "local_rxnav"
    PUBLIC_RXNAV = "public_rxnav"


class RxNormQueryMethod(StrEnum):
    """A versioned description of how a candidate was obtained."""

    NORMALIZED_EXACT = "normalized_exact"
    FIND_RXCUI_BY_STRING = "find_rxcui_by_string_search_2"


class RxNormLineage(FrozenModel):
    """Immutable source identity for an RxNorm candidate.

    This records terminology lookup provenance only. It does not establish a
    reviewed medicine mapping or therapeutic equivalence.
    """

    release_identity: str = Field(min_length=1)
    receipt_id: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    query_method: RxNormQueryMethod
    endpoint_class: RxNormEndpointClass
    source_uri: str = Field(min_length=1)
    retrieved_at: AwareDatetime
    rights_state: RightsState
    rights_reference: AnyUrl | None = None

    @model_validator(mode="after")
    def require_reference_for_permitted_rights(self) -> Self:
        if (
            self.rights_state is RightsState.PERMITTED
            and self.rights_reference is None
        ):
            raise ValueError("permitted rights require a rights reference")
        return self

    @classmethod
    def from_payload(
        cls,
        *,
        payload: bytes,
        release_identity: str,
        query_method: RxNormQueryMethod,
        endpoint_class: RxNormEndpointClass,
        source_uri: str,
        retrieved_at: datetime,
        rights_state: RightsState,
        rights_reference: AnyUrl | None = None,
        receipt_id: str | None = None,
    ) -> Self:
        """Bind lineage to the exact fixture or response bytes."""

        payload_digest = sha256(payload).hexdigest()
        return cls(
            release_identity=release_identity,
            receipt_id=receipt_id
            or f"rxnorm:{endpoint_class}:{payload_digest}",
            payload_sha256=payload_digest,
            query_method=query_method,
            endpoint_class=endpoint_class,
            source_uri=source_uri,
            retrieved_at=retrieved_at,
            rights_state=rights_state,
            rights_reference=rights_reference,
        )

    def matches_payload(self, payload: bytes) -> bool:
        """Return whether these lineage details describe ``payload``."""

        return self.payload_sha256 == sha256(payload).hexdigest()
