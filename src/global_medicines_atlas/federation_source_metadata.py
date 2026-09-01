"""Offline source-specific metadata contracts for public federation archives.

This module validates caller-supplied metadata only. It performs no network,
credential, publication, collection, or visibility operation.
"""

from __future__ import annotations

from datetime import date
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal, Self
from urllib.parse import unquote

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)


def _reject_padded(value: Any) -> Any:
    if isinstance(value, str) and value != value.strip():
        raise ValueError("exact metadata identity must not be padded")
    return value


NonBlank = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)
]
ExactNonBlank = Annotated[
    str,
    BeforeValidator(_reject_padded),
    StringConstraints(strip_whitespace=False, min_length=1, max_length=2048),
]
Sha256 = Annotated[
    str, BeforeValidator(_reject_padded), Field(pattern=r"^[0-9a-f]{64}$")
]
Revision = Annotated[
    str, BeforeValidator(_reject_padded), Field(pattern=r"^[0-9a-f]{40}$")
]

_PROFILES = {
    "au-mbs": (
        "edithatogo/australian-mbs-source-archive",
        "Australian Medicare Benefits Schedule source archive",
        "Australian Government Department of Health, Disability and Ageing",
        "www.health.gov.au",
        frozenset({"www.mbsonline.gov.au"}),
    ),
    "au-pbs": (
        "edithatogo/australian-pbs-source-archive",
        "Australian Pharmaceutical Benefits Scheme source archive",
        "Australian Government Department of Health, Disability and Ageing",
        "www.health.gov.au",
        frozenset({"www.pbs.gov.au"}),
    ),
}


class SourceMetadataError(ValueError):
    """Source metadata is incomplete, generic, or internally inconsistent."""


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


def _public_url_without_userinfo(value: AnyHttpUrl) -> AnyHttpUrl:
    if value.username is not None or value.password is not None:
        raise ValueError("public metadata URL must not contain userinfo")
    return value


PublicUrl = Annotated[
    AnyHttpUrl,
    BeforeValidator(_reject_padded),
    AfterValidator(_public_url_without_userinfo),
]


class SourceIdentity(_Model):
    source_id: Literal["au-mbs", "au-pbs"]
    authority: NonBlank
    authority_url: PublicUrl
    source_url: PublicUrl
    source_version: ExactNonBlank
    effective_from: date
    retrieved_at: AwareDatetime

    @field_validator("source_id", mode="before")
    @classmethod
    def source_id_is_exact(cls, value: Any) -> Any:
        return _reject_padded(value)


class DataCard(_Model):
    title: NonBlank
    summary: NonBlank
    intended_uses: tuple[NonBlank, ...] = Field(min_length=1, max_length=32)
    limitations: tuple[NonBlank, ...] = Field(min_length=1, max_length=32)


class PayloadBinding(_Model):
    path: ExactNonBlank
    sha256: Sha256

    @model_validator(mode="after")
    def path_is_safe(self) -> Self:
        decoded = unquote(self.path)
        path = PurePosixPath(decoded)
        noncanonical = decoded != self.path or self.path != path.as_posix()
        unsafe = (
            not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in decoded
        )
        if noncanonical or unsafe:
            raise ValueError("payload path must be safe and relative")
        return self


class CroissantDistribution(PayloadBinding):
    encoding_format: NonBlank


class Croissant(_Model):
    name: NonBlank
    conforms_to: Literal["http://mlcommons.org/croissant/1.0"]
    distributions: tuple[CroissantDistribution, ...] = Field(
        min_length=1, max_length=256
    )


class Citation(_Model):
    dataset: ExactNonBlank
    revision: Revision
    source_url: PublicUrl
    accessed_at: date


class Provenance(_Model):
    receipt: ExactNonBlank
    payloads: tuple[PayloadBinding, ...] = Field(min_length=1, max_length=256)


class Coverage(_Model):
    scope: NonBlank
    payload_paths: tuple[ExactNonBlank, ...] = Field(max_length=256)
    exclusions: tuple[NonBlank, ...] = Field(max_length=256)


class Rights(_Model):
    permission_state: Literal["approved"]
    permission_reference: PublicUrl
    attribution: NonBlank
    reviewed_at: date


class Maintenance(_Model):
    correction_url: PublicUrl
    withdrawal_policy: NonBlank


class VersionHistoryEntry(_Model):
    revision: Revision
    source_version: ExactNonBlank
    effective_from: date
    status: Literal["current", "superseded", "withdrawn"]


class SourceMetadataDocument(_Model):
    schema_version: Literal[1]
    dataset: ExactNonBlank
    revision: Revision
    source: SourceIdentity
    data_card: DataCard
    croissant: Croissant
    citations: tuple[Citation, ...] = Field(min_length=1, max_length=32)
    provenance: Provenance
    coverage: Coverage
    rights: Rights
    maintenance: Maintenance
    version_history: tuple[VersionHistoryEntry, ...] = Field(
        min_length=1, max_length=256
    )

    @property
    def source_ids(self) -> tuple[str, ...]:
        return (self.source.source_id,)

    @model_validator(mode="after")
    def metadata_is_source_specific_and_closed(self) -> Self:
        (
            expected_dataset,
            expected_title,
            expected_authority,
            authority_host,
            source_hosts,
        ) = _PROFILES[self.source.source_id]
        if self.dataset != expected_dataset:
            raise ValueError("source profile uses the wrong approved dataset")
        if self.data_card.title != expected_title:
            raise ValueError("data card requires the source-specific title")
        if self.croissant.name != expected_title:
            raise ValueError(
                "Croissant name requires the source-specific title"
            )
        if self.source.authority_url.host != authority_host:
            raise ValueError("source profile uses the wrong authority host")
        if self.source.authority != expected_authority:
            raise ValueError("source profile uses the wrong authority identity")
        if self.source.source_url.host not in source_hosts:
            raise ValueError("source profile uses the wrong source host")
        if any(
            citation.source_url.host not in source_hosts
            for citation in self.citations
        ):
            raise ValueError(
                "citation uses a host outside the approved source profile"
            )

        provenance = tuple(
            (item.path, item.sha256) for item in self.provenance.payloads
        )
        distributions = tuple(
            (item.path, item.sha256) for item in self.croissant.distributions
        )
        provenance_paths = tuple(path for path, _ in provenance)
        if len(provenance_paths) != len(set(provenance_paths)):
            raise ValueError("provenance payload paths must be unique")
        if distributions != provenance:
            raise ValueError(
                "Croissant distribution mismatch with provenance payloads"
            )
        if self.coverage.payload_paths != provenance_paths:
            raise ValueError(
                "coverage payload denominator must equal provenance payloads"
            )
        if len(self.coverage.exclusions) != len(set(self.coverage.exclusions)):
            raise ValueError("coverage exclusions must be unique")

        if not any(
            citation.dataset == self.dataset
            and citation.revision == self.revision
            for citation in self.citations
        ):
            raise ValueError("citation must identify this dataset revision")
        return self

    @model_validator(mode="after")
    def rights_are_profile_bound(self) -> Self:
        expected_authority = _PROFILES[self.source.source_id][2]
        authority_host = _PROFILES[self.source.source_id][3]
        if (
            self.rights.permission_reference.host != authority_host
            or self.rights.attribution != expected_authority
        ):
            raise ValueError(
                "rights evidence does not match the approved source profile"
            )
        return self

    @model_validator(mode="after")
    def lifecycle_is_revision_bound(self) -> Self:
        current = tuple(
            item for item in self.version_history if item.status == "current"
        )
        if len(current) != 1 or current[0].revision != self.revision:
            raise ValueError(
                "version history must contain the current revision exactly once"
            )
        if current[0].source_version != self.source.source_version:
            raise ValueError("version history source version mismatch")
        if current[0].effective_from != self.source.effective_from:
            raise ValueError("version history effective date mismatch")
        revisions = tuple(item.revision for item in self.version_history)
        if len(revisions) != len(set(revisions)):
            raise ValueError("version history revisions must be unique")

        correction = str(self.maintenance.correction_url).rstrip("/")
        if correction in {
            str(self.source.authority_url).rstrip("/"),
            str(self.source.source_url).rstrip("/"),
        }:
            raise ValueError("correction route must be distinct and actionable")
        return self


def validate_source_metadata(
    document: dict[str, Any],
) -> SourceMetadataDocument:
    """Validate one public-source metadata document without external I/O."""

    try:
        return SourceMetadataDocument.model_validate(document)
    except ValidationError as error:
        messages = "; ".join(item["msg"] for item in error.errors())
        if "permission_state" in str(error) and "approved" in str(error):
            messages = (
                "source-byte publication permission must be approved; "
                + messages
            )
        raise SourceMetadataError(messages) from error
