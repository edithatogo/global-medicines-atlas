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

_CARD_CLAIMS = {
    "au-mbs": (
        "Immutable source-native MBS release evidence with receipt-bound provenance.",
        ("Historical and current MBS service-benefit analysis",),
        (
            "MBS funding evidence is not regulatory approval or formulary evidence.",
        ),
    ),
    "au-pbs": (
        "Immutable source-native PBS release evidence with receipt-bound provenance.",
        ("Historical and current PBS formulary and funding analysis",),
        (
            "PBS listing evidence is not regulatory approval or prescribing advice.",
        ),
    ),
}

_PROFILE_DETAILS = {
    "au-mbs": {
        "authority_url": "https://www.health.gov.au/",
        "citation_url": "https://www.mbsonline.gov.au/",
        "source_url_prefix": "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-",
        "coverage_scope": "August 2026 MBS release payloads",
        "receipt_prefix": "receipts/mbs-",
    },
    "au-pbs": {
        "authority_url": "https://www.health.gov.au/",
        "citation_url": "https://www.pbs.gov.au/browse/downloads",
        "source_url_prefix": "https://www.pbs.gov.au/browse/downloads",
        "coverage_scope": "April 2026 PBS release payloads",
        "receipt_prefix": "receipts/pbs-",
    },
}

_PERMISSION_REFERENCE = "https://www.health.gov.au/using-our-websites/copyright"
_WITHDRAWAL_POLICY = (
    "Withdraw or supersede a revision when its receipt, rights or source identity "
    "fails verification."
)


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
    if value.scheme != "https":
        raise ValueError("public metadata URL must use HTTPS")
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
    version: ExactNonBlank
    created_at: AwareDatetime
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
    description: NonBlank
    version: ExactNonBlank
    license: Literal["rights-declared-per-source"]
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
    receipt_sha256: Sha256
    payloads: tuple[PayloadBinding, ...] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def receipt_path_is_safe(self) -> Self:
        decoded = unquote(self.receipt)
        path = PurePosixPath(decoded)
        noncanonical = (
            decoded != self.receipt or self.receipt != path.as_posix()
        )
        unsafe = (
            not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in decoded
        )
        if noncanonical or unsafe:
            raise ValueError(
                "provenance receipt path must be safe and canonical"
            )
        return self


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
            _,
            _,
        ) = _PROFILES[self.source.source_id]
        if self.dataset != expected_dataset:
            raise ValueError("source profile uses the wrong approved dataset")
        if self.data_card.title != expected_title:
            raise ValueError("data card requires the source-specific title")
        if self.croissant.name != expected_title:
            raise ValueError(
                "Croissant name requires the source-specific title"
            )
        if self.source.authority != expected_authority:
            raise ValueError("source profile uses the wrong authority identity")

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
    def source_urls_are_profile_bound(self) -> Self:
        _, _, _, authority_host, source_hosts = _PROFILES[self.source.source_id]
        profile = _PROFILE_DETAILS[self.source.source_id]
        if self.source.authority_url.host != authority_host:
            raise ValueError("source profile uses the wrong authority host")
        if self.source.source_url.host not in source_hosts:
            raise ValueError("source profile uses the wrong source host")
        if str(self.source.authority_url) != profile["authority_url"]:
            raise ValueError("source profile uses the wrong authority URL")
        if not str(self.source.source_url).startswith(
            profile["source_url_prefix"]
        ):
            raise ValueError("source profile uses the wrong source URL surface")
        if any(
            citation.source_url.host not in source_hosts
            for citation in self.citations
        ):
            raise ValueError(
                "citation uses a host outside the approved source profile"
            )
        if any(
            str(citation.source_url) != profile["citation_url"]
            for citation in self.citations
        ):
            raise ValueError("citation uses the wrong source URL surface")
        return self

    @model_validator(mode="after")
    def data_card_claims_are_profile_bound(self) -> Self:
        claims = (
            self.data_card.summary,
            self.data_card.intended_uses,
            self.data_card.limitations,
        )
        if claims != _CARD_CLAIMS[self.source.source_id]:
            raise ValueError(
                "data card claims do not match the approved source profile"
            )
        if (
            self.data_card.version != self.source.source_version
            or self.data_card.created_at != self.source.retrieved_at
            or self.croissant.description != self.data_card.summary
            or self.croissant.version != self.source.source_version
        ):
            raise ValueError(
                "card and Croissant versions must match source identity"
            )
        return self

    @model_validator(mode="after")
    def rights_are_profile_bound(self) -> Self:
        expected_authority = _PROFILES[self.source.source_id][2]
        authority_host = _PROFILES[self.source.source_id][3]
        if (
            self.rights.permission_reference.host != authority_host
            or self.rights.attribution != expected_authority
            or str(self.rights.permission_reference) != _PERMISSION_REFERENCE
        ):
            raise ValueError(
                "rights evidence does not match the approved source profile"
            )
        if self.rights.reviewed_at > self.source.retrieved_at.date():
            raise ValueError("rights review cannot follow source retrieval")
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

        profile = _PROFILE_DETAILS[self.source.source_id]
        if self.coverage.scope != profile["coverage_scope"]:
            raise ValueError("coverage scope does not match the source profile")
        if not self.provenance.receipt.startswith(profile["receipt_prefix"]):
            raise ValueError(
                "provenance receipt does not match the source profile"
            )
        if not self.provenance.receipt.endswith(".json"):
            raise ValueError("provenance receipt must be a JSON path")
        if any(
            citation.accessed_at > self.source.retrieved_at.date()
            for citation in self.citations
        ):
            raise ValueError("citation access cannot follow source retrieval")
        if self.maintenance.withdrawal_policy != _WITHDRAWAL_POLICY:
            raise ValueError(
                "withdrawal policy does not match the approved contract"
            )

        correction = str(self.maintenance.correction_url).rstrip("/")
        approved_correction = (
            "https://github.com/edithatogo/global-medicines-atlas/issues"
        )
        if correction != approved_correction:
            raise ValueError(
                "correction route is outside the approved repository"
            )
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
