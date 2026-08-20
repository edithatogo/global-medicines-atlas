"""Immutable, deterministic receipts for governed source acquisition."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal, Self, cast

import orjson
from pydantic import AnyUrl, AwareDatetime, Field, model_validator

from .models import FrozenModel
from .reuse_gate import ReuseGateDecision
from .rights_policy import AcquisitionRightsPolicy, coarse_rights_state

if TYPE_CHECKING:
    import httpx

SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SENSITIVE_HTTP_HEADERS = frozenset({
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "x-auth-token",
    "x-access-token",
    "www-authenticate",
})
_ALLOWED_HTTP_HEADERS = {
    "etag": "etag",
    "last-modified": "last_modified",
    "content-type": "content_type",
    "content-encoding": "content_encoding",
    "content-length": "content_length",
}


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


class DataSensitivity(StrEnum):
    """Intrinsic disclosure risk, independent from licensing permission."""

    UNKNOWN = "unknown"
    NON_SENSITIVE = "non_sensitive"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class PersonalDataState(StrEnum):
    """Observed or plausible personal-data content in source bytes."""

    UNKNOWN = "unknown"
    NONE = "none"
    POSSIBLE = "possible"
    PRESENT = "present"


class PublicationDisposition(StrEnum):
    """Publication decision, evaluated separately from source rights."""

    REVIEW_REQUIRED = "review_required"
    PERMITTED = "permitted"
    PROHIBITED = "prohibited"


class SensitivityClassification(FrozenModel):
    """Independent sensitivity and publication classification for bytes."""

    schema_id: Literal[
        "global-medicines-atlas.bronze-sensitivity-classification"
    ] = "global-medicines-atlas.bronze-sensitivity-classification"
    schema_version: Literal[1] = 1
    data_sensitivity: DataSensitivity = DataSensitivity.UNKNOWN
    personal_data: PersonalDataState = PersonalDataState.UNKNOWN
    publication: PublicationDisposition = PublicationDisposition.REVIEW_REQUIRED
    reason_codes: tuple[str, ...] = ("unassessed",)

    @model_validator(mode="after")
    def validate_reason_codes(self) -> SensitivityClassification:
        if not self.reason_codes or any(
            not reason.strip() for reason in self.reason_codes
        ):
            raise ValueError("sensitivity classification requires reason codes")
        if (
            self.publication is PublicationDisposition.PERMITTED
            and self.data_sensitivity is DataSensitivity.UNKNOWN
        ):
            raise ValueError(
                "publication cannot be permitted while sensitivity is unknown"
            )
        return self


class SourceIdentity(FrozenModel):
    """Stable catalog and publisher identity for a source."""

    catalog_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    authority: str = Field(min_length=1)
    dataset_title: str = Field(min_length=1)
    catalog_version: str = Field(min_length=1)


class HttpRetrievalEvidence(FrozenModel):
    """Evidence-grade HTTP/API retrieval metadata without secrets."""

    original_uri: AnyUrl
    final_uri: AnyUrl | None = None
    redirect_history: tuple[AnyUrl, ...] = ()
    http_method: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    etag: str | None = None
    last_modified: str | None = None
    content_type: str | None = None
    content_encoding: str | None = None
    content_length: int | None = Field(default=None, ge=0)
    observed_byte_length: int | None = Field(default=None, ge=0)
    source_native_version: str | None = None
    source_native_date: AwareDatetime | None = None
    acquisition_agent_version: str | None = None

    def canonical_json(self) -> bytes:
        payload = self.model_dump(mode="json", exclude_none=False)
        return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    def digest(self) -> str:
        return sha256(self.canonical_json()).hexdigest()


def redact_http_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Keep allowlisted response metadata; omit credentials and tokens."""

    cleaned: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in _SENSITIVE_HTTP_HEADERS:
            continue
        mapped = _ALLOWED_HTTP_HEADERS.get(lowered)
        if mapped is not None:
            cleaned[mapped] = value
    return cleaned


def http_retrieval_from_response(
    response: httpx.Response,
    *,
    original_uri: str,
    observed_byte_length: int,
    agent_version: str,
    source_native_version: str | None = None,
    source_native_date: AwareDatetime | None = None,
) -> HttpRetrievalEvidence:
    """Project an HTTP response into a secret-free retrieval receipt."""

    cleaned = redact_http_headers({
        str(key): str(value) for key, value in response.headers.items()
    })
    media_type = cleaned.get("content_type", "").split(";", 1)[0].strip()
    length_raw = cleaned.get("content_length")
    content_length = None
    if length_raw is not None and length_raw.isdigit():
        content_length = int(length_raw)
    history = tuple(AnyUrl(str(item.request.url)) for item in response.history)
    final = str(response.url) if response.url else None
    return HttpRetrievalEvidence(
        original_uri=AnyUrl(original_uri),
        final_uri=AnyUrl(final) if final else None,
        redirect_history=history,
        http_method=response.request.method,
        http_status=response.status_code,
        etag=cleaned.get("etag"),
        last_modified=cleaned.get("last_modified"),
        content_type=media_type or None,
        content_encoding=cleaned.get("content_encoding"),
        content_length=content_length,
        observed_byte_length=observed_byte_length,
        source_native_version=source_native_version,
        source_native_date=source_native_date,
        acquisition_agent_version=agent_version,
    )


class RetrievalEvidence(FrozenModel):
    """The access surface, clock, method, and outcome of one attempt."""

    uri: AnyUrl
    retrieved_at: AwareDatetime
    acquisition_method: AcquisitionMethod
    status: AcquisitionStatus
    http: HttpRetrievalEvidence | None = None


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


def content_id_for(*, payload_sha256: str) -> str:
    """Identity of exact payload bytes; equal to the digest."""

    return payload_sha256


def acquisition_id_for(
    *,
    source_id: str,
    payload_sha256: str,
    source_version: str | None = None,
) -> str:
    """Legacy content-stable identity; not a retrieval event."""

    material = f"{source_id}\n{payload_sha256}\n{source_version or ''}"
    return sha256(material.encode()).hexdigest()


def acquisition_event_id_for(
    *,
    source_id: str,
    payload_sha256: str,
    retrieved_at: datetime,
    source_version: str | None = None,
    original_uri: str | None = None,
) -> str:
    """Identity of one retrieval event; never collapsed into content_id."""

    material = (
        f"{source_id}\n{payload_sha256}\n{retrieved_at.isoformat()}\n"
        f"{source_version or ''}\n{original_uri or ''}\n"
        "acquisition-event-v1"
    )
    return sha256(material.encode()).hexdigest()


class TemporalIdentity(FrozenModel):
    """Independent clocks for one acquisition; never collapse them.

    source_published_at / source_effective_at are source-native. Missing
    stays missing and must not be filled from retrieved_at. valid_from /
    valid_to are recorded only when the source supplied them. content_id
    is the payload digest; acquisition_id is this retrieval event.
    """

    retrieved_at: AwareDatetime
    source_published_at: AwareDatetime | None = None
    source_effective_at: AwareDatetime | None = None
    valid_from: AwareDatetime | None = None
    valid_to: AwareDatetime | None = None
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    content_id: str | None = Field(default=None, pattern=SHA256_PATTERN)
    source_version: str | None = None

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
    original_uri: str | None = None,
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
        source_version=source_version,
        content_id=content_id_for(payload_sha256=payload_sha256),
        acquisition_id=acquisition_event_id_for(
            source_id=source_id,
            payload_sha256=payload_sha256,
            retrieved_at=retrieved_at,
            source_version=source_version,
            original_uri=original_uri,
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
    uri = _model_field(retrieval, "uri")
    if not isinstance(retrieved_at, datetime) or not isinstance(source_id, str):
        return data
    payload_sha256 = digest if isinstance(digest, str) else "0" * 64
    effective = data.get("effective_from")
    source_effective_at = effective if isinstance(effective, datetime) else None
    original_uri = str(uri) if uri is not None else None
    data["temporal"] = temporal_identity_from_source(
        retrieved_at=retrieved_at,
        source_id=source_id,
        payload_sha256=payload_sha256,
        source_effective_at=source_effective_at,
        original_uri=original_uri,
    )
    return data


class DeterministicReceipt(FrozenModel):
    """Canonical serialization shared by success and failure receipts."""

    def canonical_json(self) -> bytes:
        payload = self.model_dump(mode="json", exclude_none=False)
        return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    def digest(self) -> str:
        return sha256(self.canonical_json()).hexdigest()


class AcquisitionEvent(DeterministicReceipt):
    """Append-only record of one retrieval; distinct from payload identity."""

    schema_id: Literal["global-medicines-atlas.bronze-acquisition-event"] = (
        "global-medicines-atlas.bronze-acquisition-event"
    )
    schema_version: Literal[2, 3] = 3
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    content_id: str = Field(pattern=SHA256_PATTERN)
    source_id: str = Field(min_length=1)
    source_version: str | None = None
    retrieved_at: AwareDatetime
    source_published_at: AwareDatetime | None = None
    source_effective_at: AwareDatetime | None = None
    valid_from: AwareDatetime | None = None
    valid_to: AwareDatetime | None = None
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    source: SourceIdentity | None = None
    retrieval: RetrievalEvidence | None = None
    reuse: ReuseGateDecision | None = None
    rights_state: RightsState | None = None
    rights_reference: AnyUrl | None = None
    rights_policy: AcquisitionRightsPolicy | None = None
    sensitivity: SensitivityClassification = Field(
        default_factory=SensitivityClassification
    )
    evidence_class: EvidenceClass | None = None

    @model_validator(mode="after")
    def validate_distinct_identities(self) -> AcquisitionEvent:
        if self.acquisition_id == self.content_id:
            raise ValueError("acquisition_id must not equal content_id")
        if self.content_id != self.payload_sha256:
            raise ValueError("content_id must equal payload digest")
        return self


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
    rights_policy: AcquisitionRightsPolicy | None = None
    sensitivity: SensitivityClassification = Field(
        default_factory=SensitivityClassification
    )
    evidence_class: EvidenceClass
    transformation: TransformationEvidence

    @model_validator(mode="before")
    @classmethod
    def bind_temporal_identity(cls, data: object) -> object:
        if isinstance(data, dict):
            return _bind_temporal_payload(cast("dict[str, object]", data))
        return data

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        """Keep temporal.content_id coupled to payload digest on copy."""

        updates: dict[str, Any] = dict(update) if update is not None else {}
        payload = updates.get("payload", self.payload)
        digest = (
            payload.sha256 if isinstance(payload, PayloadEvidence) else None
        )
        temporal = updates.get("temporal", self.temporal)
        if (
            digest is not None
            and "temporal" not in updates
            and isinstance(temporal, TemporalIdentity)
            and temporal.content_id != digest
        ):
            updates["temporal"] = temporal.model_copy(
                update={"content_id": digest}
            )
        return super().model_copy(update=updates or None, deep=deep)

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
        temporal = self.temporal
        if temporal.content_id is None:
            temporal = temporal.model_copy(
                update={"content_id": self.payload.sha256}
            )
            return self.model_copy(update={"temporal": temporal})
        if temporal.content_id != self.payload.sha256:
            raise ValueError("content_id must equal payload digest")
        self._validate_bound_rights_policy()
        return self

    def _validate_bound_rights_policy(self) -> None:
        policy = self.rights_policy
        if policy is None:
            return
        if policy.source_id != self.source.source_id:
            raise ValueError("rights policy source_id must match receipt")
        temporal = self.temporal
        if (
            temporal is not None
            and policy.acquisition_id != temporal.acquisition_id
        ):
            raise ValueError("rights policy acquisition_id must match receipt")
        if coarse_rights_state(policy) != self.rights_state:
            raise ValueError(
                "rights policy does not match receipt rights_state"
            )

    def canonical_json(self) -> bytes:
        payload = self.model_dump(mode="json", exclude_none=False)
        if payload.get("rights_policy") is None:
            del payload["rights_policy"]
        return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    @property
    def satisfies_live_gate(self) -> bool:
        return (
            self.evidence_class is EvidenceClass.LIVE
            and self.retrieval.status is AcquisitionStatus.SUCCEEDED
            and self.rights_state is RightsState.PERMITTED
        )


def require_publication_permitted(receipt: SourceReceipt) -> None:
    """Fail closed across independent rights and sensitivity decisions."""

    if receipt.rights_state is not RightsState.PERMITTED:
        raise ValueError("publication is not permitted by the rights state")
    if receipt.sensitivity.publication is not PublicationDisposition.PERMITTED:
        raise ValueError(
            "publication is blocked by sensitivity/publication classification"
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
