"""Deterministic, fail-closed contracts for governed dataset publication."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonBlank = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1024),
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class PublicationContractModel(BaseModel):
    """Immutable contract that rejects undocumented fields."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_by_alias=True,
        validate_by_name=True,
        validate_default=True,
    )


class RightsDisposition(StrEnum):
    """Machine-enforceable publication disposition."""

    PERMITTED = "permitted"
    RESTRICTED = "restricted"
    FORBIDDEN = "forbidden"
    UNKNOWN = "unknown"


class PublicationState(StrEnum):
    """Externally distinguishable release-package states."""

    PREPARED = "prepared"
    QUALIFIED = "qualified"
    UPLOADED = "uploaded"
    PUBLIC = "public"
    VERIFICATION_FAILED = "verification_failed"


class VerificationOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class VerificationCheck(StrEnum):
    """Named checks required at publication-state boundaries."""

    PACKAGE_CHECKSUM = "package-checksum"
    RIGHTS_REVIEW = "rights-review"
    PRIVACY_REVIEW = "privacy-review"
    FORBIDDEN_CONTENT_SCAN = "forbidden-content-scan"
    QUALIFICATION = "qualification"
    UPLOAD_VERIFICATION = "upload-verification"
    PUBLIC_VERIFICATION = "public-verification"


class FieldContract(PublicationContractModel):
    """One stable field in the release data dictionary."""

    name: Annotated[NonBlank, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    description: NonBlank
    data_type: NonBlank
    nullable: bool
    semantic_role: NonBlank
    source_fields: tuple[NonBlank, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def source_fields_are_unique(self) -> Self:
        if len(self.source_fields) != len(set(self.source_fields)):
            raise ValueError("source_fields must be unique")
        return self


class DataDictionary(PublicationContractModel):
    schema_version: NonBlank
    fields: tuple[FieldContract, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def field_names_are_unique(self) -> Self:
        names = tuple(field.name for field in self.fields)
        if len(names) != len(set(names)):
            raise ValueError("data dictionary field names must be unique")
        return self


class CoverageDeclaration(PublicationContractModel):
    """Declared population and exclusions; absence is never treated as zero."""

    scope: NonBlank
    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)
    exclusions: tuple[NonBlank, ...]
    jurisdictions: tuple[NonBlank, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def coverage_is_coherent(self) -> Self:
        if self.numerator > self.denominator:
            raise ValueError("coverage numerator cannot exceed denominator")
        if len(self.exclusions) != len(set(self.exclusions)):
            raise ValueError("coverage exclusions must be unique")
        if len(self.jurisdictions) != len(set(self.jurisdictions)):
            raise ValueError("coverage jurisdictions must be unique")
        return self


class ProvenanceDeclaration(PublicationContractModel):
    """Content-addressed source and transformation evidence."""

    source_id: NonBlank
    source_uri: NonBlank
    retrieved_at: AwareDatetime
    source_sha256: Sha256
    transformation_id: NonBlank
    transformation_sha256: Sha256


class RightsDeclaration(PublicationContractModel):
    """Rights evidence attached to every governed source."""

    source_id: NonBlank
    disposition: RightsDisposition
    reference_uri: NonBlank | None = None
    reviewed_at: AwareDatetime | None = None
    review_note: NonBlank | None = None

    @model_validator(mode="after")
    def permitted_rights_are_evidenced(self) -> Self:
        if self.disposition is RightsDisposition.PERMITTED and (
            self.reference_uri is None or self.reviewed_at is None
        ):
            raise ValueError(
                "permitted rights require a reference and review timestamp"
            )
        return self


class DatasetCard(PublicationContractModel):
    title: NonBlank
    summary: NonBlank
    version: NonBlank
    created_at: AwareDatetime
    intended_uses: tuple[NonBlank, ...] = Field(min_length=1)
    limitations: tuple[NonBlank, ...] = Field(min_length=1)
    coverage: tuple[CoverageDeclaration, ...] = Field(min_length=1)
    provenance: tuple[ProvenanceDeclaration, ...] = Field(min_length=1)
    rights: tuple[RightsDeclaration, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def all_sources_have_publishable_evidence(self) -> Self:
        provenance_ids = {item.source_id for item in self.provenance}
        rights_ids = {item.source_id for item in self.rights}
        if len(provenance_ids) != len(self.provenance):
            raise ValueError("provenance source_ids must be unique")
        if len(rights_ids) != len(self.rights):
            raise ValueError("rights source_ids must be unique")
        if provenance_ids != rights_ids:
            raise ValueError(
                "provenance and rights must cover the same sources"
            )
        blocked = sorted(
            item.source_id
            for item in self.rights
            if item.disposition is not RightsDisposition.PERMITTED
        )
        if blocked:
            raise ValueError(
                "package contains non-publishable source rights: "
                + ", ".join(blocked)
            )
        return self


class CroissantDistribution(PublicationContractModel):
    name: NonBlank
    content_url: NonBlank
    encoding_format: NonBlank
    sha256: Sha256


class CroissantMetadata(PublicationContractModel):
    """Minimal deterministic MLCommons Croissant representation."""

    context: tuple[NonBlank, ...] = Field(
        default=(
            "https://schema.org/",
            "https://mlcommons.org/croissant/",
        ),
        alias="@context",
    )
    conforms_to: NonBlank = Field(
        default="http://mlcommons.org/croissant/1.0",
        alias="dct:conformsTo",
    )
    name: NonBlank
    description: NonBlank
    version: NonBlank
    license: NonBlank
    distributions: tuple[CroissantDistribution, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def distribution_names_are_unique(self) -> Self:
        names = tuple(item.name for item in self.distributions)
        if len(names) != len(set(names)):
            raise ValueError("Croissant distribution names must be unique")
        return self


class PublicationPackage(PublicationContractModel):
    """Complete package metadata eligible for deterministic qualification."""

    contract_version: NonBlank
    data_dictionary: DataDictionary
    dataset_card: DatasetCard
    croissant: CroissantMetadata

    @model_validator(mode="after")
    def package_metadata_agrees(self) -> Self:
        card = self.dataset_card
        if card.title != self.croissant.name:
            raise ValueError("dataset card and Croissant names must agree")
        if card.version != self.croissant.version:
            raise ValueError("dataset card and Croissant versions must agree")
        return self

    def canonical_bytes(self) -> bytes:
        """Serialize identically across runs and input mapping order."""

        payload = self.model_dump(mode="json", by_alias=True)
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


class VerificationEvidence(PublicationContractModel):
    check_id: VerificationCheck
    outcome: VerificationOutcome
    evidence_uri: AnyHttpUrl
    evidence_sha256: Sha256
    artifact_sha256: Sha256
    checked_at: AwareDatetime
    valid_until: AwareDatetime
    privacy_approved: bool | None = None
    forbidden_content_detected: bool | None = None

    @field_validator("evidence_uri")
    @classmethod
    def evidence_uri_is_safe(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username is not None or value.password is not None:
            raise ValueError("evidence_uri must not contain credentials")
        return value

    @model_validator(mode="after")
    def review_result_is_explicit(self) -> Self:
        if self.valid_until <= self.checked_at:
            raise ValueError("verification evidence must have a valid window")
        if self.check_id is VerificationCheck.PRIVACY_REVIEW:
            if self.privacy_approved is not True:
                raise ValueError("privacy review must explicitly approve")
        elif self.privacy_approved is not None:
            raise ValueError(
                "privacy_approved is only valid for privacy review"
            )
        if self.check_id is VerificationCheck.FORBIDDEN_CONTENT_SCAN:
            if self.forbidden_content_detected is not False:
                raise ValueError(
                    "forbidden-content scan must explicitly report none"
                )
        elif self.forbidden_content_detected is not None:
            raise ValueError(
                "forbidden_content_detected is only valid for content scan"
            )
        return self


class PublicationVerificationReceipt(PublicationContractModel):
    """Durable evidence for one observable package-state transition."""

    receipt_id: NonBlank
    package_sha256: Sha256
    state: PublicationState
    verified_at: AwareDatetime
    verifier: NonBlank
    evidence: tuple[VerificationEvidence, ...] = Field(min_length=1)
    public_uri: AnyHttpUrl | None = None

    @field_validator("public_uri")
    @classmethod
    def public_uri_is_safe(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and (
            value.username is not None or value.password is not None
        ):
            raise ValueError("public_uri must not contain credentials")
        return value

    @model_validator(mode="after")
    def state_is_supported_by_evidence(self) -> Self:
        check_ids = tuple(item.check_id for item in self.evidence)
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("verification check_ids must be unique")
        non_passing = tuple(
            item
            for item in self.evidence
            if item.outcome is not VerificationOutcome.PASSED
        )
        if (
            non_passing
            and self.state is not PublicationState.VERIFICATION_FAILED
        ):
            raise ValueError(
                "failed or unknown evidence requires verification_failed"
            )
        if (
            not non_passing
            and self.state is PublicationState.VERIFICATION_FAILED
        ):
            raise ValueError(
                "verification_failed requires failed or unknown evidence"
            )
        if any(
            item.artifact_sha256 != self.package_sha256
            for item in self.evidence
        ):
            raise ValueError("all evidence must be bound to the package")
        if any(
            item.checked_at > self.verified_at
            or item.valid_until < self.verified_at
            for item in self.evidence
        ):
            raise ValueError("all evidence must be current at verification")
        if self.state is not PublicationState.VERIFICATION_FAILED:
            required = _required_checks(self.state)
            missing = required.difference(check_ids)
            if missing:
                names = ", ".join(sorted(item.value for item in missing))
                raise ValueError(
                    f"publication state is missing checks: {names}"
                )
        if self.state is PublicationState.PUBLIC and self.public_uri is None:
            raise ValueError("public state requires an observable public_uri")
        if self.state is not PublicationState.PUBLIC and self.public_uri:
            raise ValueError("only public state may declare public_uri")
        return self


def _required_checks(state: PublicationState) -> frozenset[VerificationCheck]:
    baseline = {
        VerificationCheck.PACKAGE_CHECKSUM,
        VerificationCheck.RIGHTS_REVIEW,
        VerificationCheck.PRIVACY_REVIEW,
        VerificationCheck.FORBIDDEN_CONTENT_SCAN,
    }
    if state in {
        PublicationState.QUALIFIED,
        PublicationState.UPLOADED,
        PublicationState.PUBLIC,
    }:
        baseline.add(VerificationCheck.QUALIFICATION)
    if state in {PublicationState.UPLOADED, PublicationState.PUBLIC}:
        baseline.add(VerificationCheck.UPLOAD_VERIFICATION)
    if state is PublicationState.PUBLIC:
        baseline.add(VerificationCheck.PUBLIC_VERIFICATION)
    return frozenset(baseline)


def canonical_sha256(value: PublicationContractModel) -> str:
    """Content-address any contract using canonical JSON."""

    payload: dict[str, Any] = value.model_dump(mode="json", by_alias=True)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def receipt_is_for_package(
    package: PublicationPackage,
    receipt: PublicationVerificationReceipt,
) -> bool:
    """Verify a receipt is bound to the exact deterministic package."""

    return package.sha256() == receipt.package_sha256
