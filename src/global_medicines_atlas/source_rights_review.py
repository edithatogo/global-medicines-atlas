"""Source-family rights reviews and public publication eligibility."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    AnyUrl,
    AwareDatetime,
    Field,
    computed_field,
    model_validator,
)

from .models import FrozenModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ReusePermission(StrEnum):
    """Explicit reuse permission; unknown never implies permission."""

    UNKNOWN = "unknown"
    PERMITTED = "permitted"
    CONDITIONAL = "conditional"
    PROHIBITED = "prohibited"


class PublicationSensitivity(StrEnum):
    """Publication sensitivity independent of copyright and licensing."""

    PUBLIC = "public"
    CONTROLLED = "controlled"
    PROHIBITED = "publication_prohibited"
    UNKNOWN = "unknown"


class EvidenceScope(StrEnum):
    """Breadth of an official rights statement."""

    DATASET = "dataset"
    ENDPOINT = "endpoint"
    AUTHORITY = "authority"
    NATIONAL_OPEN_DATA = "national_open_data"


class ReviewDisposition(StrEnum):
    """One source's publication disposition."""

    APPROVED_PUBLIC_SOURCE = "approved_public_source"
    APPROVED_PUBLIC_DERIVED_ONLY = "approved_public_derived_only"
    CATALOGUE_ONLY = "catalogue_only"
    RIGHTS_BLOCKED = "rights_blocked"
    CREDENTIALED_EXCLUDED = "credentialed_excluded"


class RightsEvidence(FrozenModel):
    """Content-digested observation of an official rights statement."""

    official_url: AnyUrl
    observed_at: AwareDatetime
    content_sha256: str = Field(pattern=SHA256_PATTERN)
    scope: EvidenceScope
    reuse_statement: str = Field(min_length=1)


class SourceRightsReview(FrozenModel):
    """Rights and sensitivity decision for one catalogued source."""

    schema_id: Literal["global-medicines-atlas.source-rights-review"] = (
        "global-medicines-atlas.source-rights-review"
    )
    schema_version: Literal[1] = 1
    source_id: str = Field(min_length=1)
    policy_family_id: str = Field(min_length=1)
    evidence: tuple[RightsEvidence, ...]
    redistribute: ReusePermission
    transform: ReusePermission
    publish_source_bytes: ReusePermission
    sensitivity: PublicationSensitivity
    disposition: ReviewDisposition
    attribution: str | None = None
    field_exclusions: tuple[str, ...] = ()
    maintainer_licence_approved: bool = False
    maintainer_publication_approved: bool = False
    reviewed_at: AwareDatetime
    review_trigger: str = Field(min_length=1)
    blocker: str | None = None

    @computed_field
    @property
    def public_source_eligible(self) -> bool:
        """Return whether source bytes may enter a public package."""

        return self.disposition is ReviewDisposition.APPROVED_PUBLIC_SOURCE

    @computed_field
    @property
    def public_derived_eligible(self) -> bool:
        """Return whether an approved public projection may be published."""

        return self.disposition in {
            ReviewDisposition.APPROVED_PUBLIC_SOURCE,
            ReviewDisposition.APPROVED_PUBLIC_DERIVED_ONLY,
        }

    @model_validator(mode="after")
    def public_source_disposition_is_supported(self) -> Self:
        if self.disposition is ReviewDisposition.APPROVED_PUBLIC_SOURCE:
            if not self.evidence:
                raise ValueError("public source requires official evidence")
            if self.redistribute is not ReusePermission.PERMITTED:
                raise ValueError(
                    "public source requires redistribute permission"
                )
            if self.transform is not ReusePermission.PERMITTED:
                raise ValueError("public source requires transform permission")
            if self.publish_source_bytes is not ReusePermission.PERMITTED:
                raise ValueError("public source bytes must be permitted")
            if self.sensitivity is not PublicationSensitivity.PUBLIC:
                raise ValueError("public source requires public sensitivity")
            if not (
                self.maintainer_licence_approved
                and self.maintainer_publication_approved
            ):
                raise ValueError("public source requires maintainer approval")
            if self.attribution is None:
                raise ValueError("public source requires attribution guidance")
        return self

    @model_validator(mode="after")
    def public_derived_disposition_is_supported(self) -> Self:
        if self.disposition is ReviewDisposition.APPROVED_PUBLIC_DERIVED_ONLY:
            if not self.evidence:
                raise ValueError(
                    "public derived data requires official evidence"
                )
            if self.redistribute is not ReusePermission.PERMITTED:
                raise ValueError(
                    "public derived data requires redistribute permission"
                )
            if self.transform is not ReusePermission.PERMITTED:
                raise ValueError(
                    "public derived data requires transform permission"
                )
            if self.sensitivity is not PublicationSensitivity.PUBLIC:
                raise ValueError(
                    "public derived data requires public sensitivity"
                )
            if not (
                self.maintainer_licence_approved
                and self.maintainer_publication_approved
            ):
                raise ValueError(
                    "public derived data requires maintainer approval"
                )
            if self.attribution is None:
                raise ValueError(
                    "public derived data requires attribution guidance"
                )
        return self

    @model_validator(mode="after")
    def non_public_disposition_has_blocker(self) -> Self:
        if (
            self.disposition
            in {
                ReviewDisposition.CATALOGUE_ONLY,
                ReviewDisposition.RIGHTS_BLOCKED,
                ReviewDisposition.CREDENTIALED_EXCLUDED,
            }
            and self.blocker is None
        ):
            raise ValueError("non-public disposition requires a blocker")
        return self


def validate_catalogue_reviews(
    source_ids: tuple[str, ...],
    reviews: tuple[SourceRightsReview, ...],
) -> None:
    """Require exactly one source rights review per catalogue source."""

    counts = Counter(item.source_id for item in reviews)
    duplicates = sorted(
        source_id for source_id, count in counts.items() if count > 1
    )
    if duplicates:
        raise ValueError(f"duplicate source rights reviews: {duplicates}")
    expected = set(source_ids)
    actual = set(counts)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        raise ValueError(
            f"source rights coverage mismatch; missing={missing}, "
            f"unexpected={unexpected}"
        )
