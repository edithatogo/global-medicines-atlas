"""Immutable, deterministic receipts for governed source acquisition."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal, Self, cast

import orjson
from pydantic import AnyUrl, AwareDatetime, Field, model_validator

from .models import FrozenModel
from .reuse_gate import ReuseGateDecision

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class AcquisitionMethod(StrEnum):
    """How source bytes or records were acquired."""

    API = "api"
    DOWNLOAD = "download"
    LICENSED_FEED = "licensed_feed"
    MANUAL_EXPORT = "manual_export"
    WEB_QUERY = "web_query"
    LOCAL_FIXTURE = "local_fixture"


class AcquisitionStatus(StrEnum):
    """Observable outcome of a retrieval attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class EvidenceClass(StrEnum):
    """Qualification class, kept distinct from acquisition success."""

    FIXTURE = "fixture"
    SYNTHETIC = "synthetic"
    DRY_RUN = "dry_run"
    LIVE = "live"
    UNAVAILABLE = "unavailable"


class RightsState(StrEnum):
    """Known permission state for retaining and transforming source data."""

    UNKNOWN = "unknown"
    PERMITTED = "permitted"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"


class SourceIdentity(FrozenModel):
    """Stable catalog and publisher identity for a source."""

    catalog_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    authority: str = Field(min_length=1)
    dataset_title: str = Field(min_length=1)
    catalog_version: str = Field(min_length=1)


class RetrievalEvidence(FrozenModel):
    """The access surface, clock, method, and outcome of one attempt."""

    uri: AnyUrl
    retrieved_at: AwareDatetime
    acquisition_method: AcquisitionMethod
    status: AcquisitionStatus


class PayloadEvidence(FrozenModel):
    """Identity and exact size of an acquired byte payload."""

    sha256: str = Field(pattern=SHA256_PATTERN)
    byte_count: int = Field(ge=0)

    @classmethod
    def from_bytes(cls, payload: bytes) -> Self:
        return cls(sha256=sha256(payload).hexdigest(), byte_count=len(payload))

    def matches(self, payload: bytes) -> bool:
        return self == self.from_bytes(payload)


class TransformationEvidence(FrozenModel):
    """Pinned transformation and deterministic output identities."""

    transformation_id: str = Field(min_length=1)
    transformation_sha256: str = Field(pattern=SHA256_PATTERN)
    output_sha256: str = Field(pattern=SHA256_PATTERN)
    output_byte_count: int = Field(ge=0)


def acquisition_id_for(
    *,
    source_id: str,
    payload_sha256: str,
    source_version: str | None = None,
) -> str:
    """Stable identity for one payload acquisition; independent of parse."""

    material = f"{source_id}\n{payload_sha256}\n{source_version or ''}"
    return sha256(material.encode()).hexdigest()


class TemporalIdentity(FrozenModel):
    """Independent clocks for one acquisition; never collapse them.

    source_published_at / source_effective_at are source-native. Missing
    stays missing and must not be filled from retrieved_at. valid_from /
    valid_to are recorded only when the source supplied them.
    """

    retrieved_at: AwareDatetime
    source_published_at: AwareDatetime | None = None
    source_effective_at: AwareDatetime | None = None
    valid_from: AwareDatetime | None = None
    valid_to: AwareDatetime | None = None
    acquisition_id: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_independent_clocks(self) -> TemporalIdentity:
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to <= self.valid_from
        ):
            raise ValueError("valid_to must follow valid_from")
        return self


def temporal_identity_from_source(
    *,
    retrieved_at: AwareDatetime,
    source_id: str,
    payload_sha256: str,
    source_published_at: AwareDatetime | None = None,
    source_effective_at: AwareDatetime | None = None,
    valid_from: AwareDatetime | None = None,
    valid_to: AwareDatetime | None = None,
    source_version: str | None = None,
    substitute_retrieved_as_published: bool = False,
) -> TemporalIdentity:
    """Build temporal identity without inventing source-native times."""

    if substitute_retrieved_as_published:
        raise ValueError(
            "source published time must not be filled from retrieved_at"
        )
    return TemporalIdentity(
        retrieved_at=retrieved_at,
        source_published_at=source_published_at,
        source_effective_at=source_effective_at,
        valid_from=valid_from,
        valid_to=valid_to,
        acquisition_id=acquisition_id_for(
            source_id=source_id,
            payload_sha256=payload_sha256,
            source_version=source_version,
        ),
    )


def require_temporal(temporal: TemporalIdentity | None) -> TemporalIdentity:
    """Narrow a bound temporal identity; receipts must always carry one."""

    if temporal is None:
        raise ValueError("temporal identity is required")
    return temporal


def _model_field(value: object, name: str) -> object:
    if isinstance(value, dict):
        return cast("dict[str, object]", value).get(name)
    return getattr(value, name, None)


def _bind_temporal_payload(data: dict[str, object]) -> dict[str, object]:
    if data.get("temporal") is not None:
        return data
    retrieval = data.get("retrieval")
    payload = data.get("payload")
    source = data.get("source")
    retrieved_at = _model_field(retrieval, "retrieved_at")
    source_id = _model_field(source, "source_id")
    digest = _model_field(payload, "sha256")
    if not isinstance(retrieved_at, datetime) or not isinstance(source_id, str):
        return data
    payload_sha256 = digest if isinstance(digest, str) else "0" * 64
    effective = data.get("effective_from")
    source_effective_at = effective if isinstance(effective, datetime) else None
    data["temporal"] = temporal_identity_from_source(
        retrieved_at=retrieved_at,
        source_id=source_id,
        payload_sha256=payload_sha256,
        source_effective_at=source_effective_at,
    )
    return data


class DeterministicReceipt(FrozenModel):
    """Canonical serialization shared by success and failure receipts."""

    def canonical_json(self) -> bytes:
        payload = self.model_dump(mode="json", exclude_none=False)
        return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    def digest(self) -> str:
        return sha256(self.canonical_json()).hexdigest()


class SourceReceipt(DeterministicReceipt):
    """Evidence that a source payload was acquired and transformed."""

    receipt_type: Literal["source"] = "source"
    receipt_id: str = Field(min_length=1)
    source: SourceIdentity
    retrieval: RetrievalEvidence
    payload: PayloadEvidence
    effective_from: AwareDatetime | None = None
    effective_to: AwareDatetime | None = None
    temporal: TemporalIdentity | None = None
    reuse: ReuseGateDecision | None = None
    rights_state: RightsState
    rights_reference: AnyUrl | None = None
    evidence_class: EvidenceClass
    transformation: TransformationEvidence

    @model_validator(mode="before")
    @classmethod
    def bind_temporal_identity(cls, data: object) -> object:
        if isinstance(data, dict):
            return _bind_temporal_payload(cast("dict[str, object]", data))
        return data

    @model_validator(mode="after")
    def validate_success_contract(self) -> SourceReceipt:
        if self.retrieval.status is not AcquisitionStatus.SUCCEEDED:
            raise ValueError("SourceReceipt requires a succeeded retrieval")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ValueError("effective_to must follow effective_from")
        if (
            self.rights_state is RightsState.PERMITTED
            and self.rights_reference is None
        ):
            raise ValueError("permitted rights require a rights reference")
        if self.temporal is None:
            raise ValueError("temporal identity is required")
        if self.temporal.retrieved_at != self.retrieval.retrieved_at:
            raise ValueError("temporal.retrieved_at must match retrieval")
        return self

    @property
    def satisfies_live_gate(self) -> bool:
        return (
            self.evidence_class is EvidenceClass.LIVE
            and self.retrieval.status is AcquisitionStatus.SUCCEEDED
            and self.rights_state is RightsState.PERMITTED
        )


class FailureReceipt(DeterministicReceipt):
    """Durable evidence for an unsuccessful or unavailable source attempt."""

    receipt_type: Literal["failure"] = "failure"
    receipt_id: str = Field(min_length=1)
    source: SourceIdentity
    retrieval: RetrievalEvidence
    temporal: TemporalIdentity | None = None
    reuse: ReuseGateDecision | None = None
    evidence_class: EvidenceClass
    rights_state: RightsState
    rights_reference: AnyUrl | None = None
    failure_code: str = Field(min_length=1)
    failure_message: str = Field(min_length=1)
    retryable: bool = False

    @model_validator(mode="before")
    @classmethod
    def bind_temporal_identity(cls, data: object) -> object:
        if isinstance(data, dict):
            return _bind_temporal_payload(cast("dict[str, object]", data))
        return data

    @model_validator(mode="after")
    def validate_failure_contract(self) -> FailureReceipt:
        if self.retrieval.status is AcquisitionStatus.SUCCEEDED:
            raise ValueError(
                "FailureReceipt cannot record a succeeded retrieval"
            )
        if self.evidence_class is EvidenceClass.LIVE:
            raise ValueError("FailureReceipt cannot claim live evidence")
        if self.temporal is None:
            raise ValueError("temporal identity is required")
        return self

    @property
    def satisfies_live_gate(self) -> Literal[False]:
        return False
