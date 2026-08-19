"""Machine-readable acquisition rights and retention policy.

Coarse ``RightsState`` on receipts remains the retain/transform signal.
This module records licence evidence, review state, access restrictions,
and the distinct permissions to retain internal provenance versus publish
source bytes. It does not conclude licences or authorize publication.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import AnyUrl, AwareDatetime, Field, model_validator

from .models import FrozenModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"

SCHEMA_ID = "global-medicines-atlas.acquisition-rights-policy"
_CREDENTIAL_MARKERS = (
    "authorization:",
    "bearer ",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "cookie:",
    "set-cookie",
    "x-auth-token",
    "x-access-token",
)


class Permission(StrEnum):
    """Explicit permission; unknown is not an implied grant."""

    UNKNOWN = "unknown"
    PERMITTED = "permitted"
    CONDITIONAL = "conditional"
    PROHIBITED = "prohibited"


class ReviewStatus(StrEnum):
    """Review lifecycle for one acquisition rights snapshot."""

    UNREVIEWED = "unreviewed"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class AccessRestriction(StrEnum):
    """How the source is accessed; never stores credentials."""

    NONE = "none"
    UNKNOWN = "unknown"
    CREDENTIALED = "credentialed"
    LICENSED_FEED = "licensed_feed"
    APPROVAL_REQUIRED = "approval_required"


class AcquisitionRightsPolicy(FrozenModel):
    """Rights record bound to one acquisition identity."""

    schema_id: Literal["global-medicines-atlas.acquisition-rights-policy"] = (
        SCHEMA_ID
    )
    schema_version: Literal[1] = 1
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    source_id: str = Field(min_length=1)
    licence_evidence_uri: AnyUrl | None = None
    licence_expression: str | None = None
    retain_evidence: Permission
    publish_bytes: Permission
    redistribute: Permission
    transform: Permission
    attribution_requirement: str | None = None
    access_restriction: AccessRestriction
    review_status: ReviewStatus
    observed_at: AwareDatetime
    reviewed_at: AwareDatetime | None = None
    review_expires_at: AwareDatetime | None = None
    maintainer_licence_approved: bool = False
    maintainer_publication_approved: bool = False

    @model_validator(mode="after")
    def policy_is_internally_consistent(self) -> Self:
        _reject_credential_text(self.licence_expression)
        _reject_credential_text(self.attribution_requirement)
        if (
            self.publish_bytes is Permission.PERMITTED
            and self.retain_evidence is Permission.PROHIBITED
        ):
            raise ValueError(
                "publish_bytes cannot be permitted when retain_evidence is "
                "prohibited"
            )
        if (
            self.redistribute is Permission.PERMITTED
            and self.publish_bytes is Permission.PROHIBITED
        ):
            raise ValueError(
                "redistribution cannot be permitted when publish_bytes is "
                "prohibited"
            )
        if self.review_status is ReviewStatus.REVIEWED:
            if self.reviewed_at is None:
                raise ValueError("reviewed rights require reviewed_at")
            if self.licence_evidence_uri is None:
                raise ValueError("reviewed rights require licence evidence")
        if (
            self.review_expires_at is not None
            and self.review_expires_at <= self.observed_at
            and self.review_status is not ReviewStatus.EXPIRED
        ):
            raise ValueError("review_expires_at must follow observed_at")
        return self


class RightsPolicyDecision(FrozenModel):
    """Fail-closed evaluation of one acquisition policy snapshot."""

    may_retain_internal_provenance: bool
    may_publish_bytes: bool
    blocking_reasons: tuple[str, ...]


class RightsPolicyLedger(FrozenModel):
    """Append-only rights history; never rewrites earlier snapshots."""

    revisions: tuple[AcquisitionRightsPolicy, ...] = ()

    @classmethod
    def empty(cls) -> RightsPolicyLedger:
        return cls()

    def append(
        self,
        policy: AcquisitionRightsPolicy,
    ) -> RightsPolicyLedger:
        return RightsPolicyLedger(revisions=(*self.revisions, policy))

    def evaluate(
        self,
        acquisition_id: str,
        *,
        evaluated_at: datetime,
    ) -> RightsPolicyDecision:
        applicable = tuple(
            item
            for item in self.revisions
            if item.acquisition_id == acquisition_id
            and item.observed_at <= evaluated_at
        )
        if not applicable:
            return RightsPolicyDecision(
                may_retain_internal_provenance=False,
                may_publish_bytes=False,
                blocking_reasons=(
                    "rights policy is unresolved for this acquisition",
                ),
            )
        latest_at = max(item.observed_at for item in applicable)
        current = tuple(
            item for item in applicable if item.observed_at == latest_at
        )
        if _permissions_conflict(current):
            retain = any(_may_retain(item, evaluated_at) for item in current)
            return RightsPolicyDecision(
                may_retain_internal_provenance=retain,
                may_publish_bytes=False,
                blocking_reasons=(
                    "conflicting rights revisions at the same observed_at",
                ),
            )
        return evaluate_acquisition_rights(
            current[0],
            evaluated_at=evaluated_at,
        )


def coarse_rights_state(policy: AcquisitionRightsPolicy) -> str:
    """Project retain/transform permission onto receipt RightsState values."""

    if policy.retain_evidence is Permission.PROHIBITED:
        return "prohibited"
    if (
        policy.retain_evidence is Permission.UNKNOWN
        or policy.transform is Permission.UNKNOWN
    ):
        return "unknown"
    if (
        policy.retain_evidence is Permission.CONDITIONAL
        or policy.transform is Permission.PROHIBITED
        or policy.access_restriction
        in {
            AccessRestriction.CREDENTIALED,
            AccessRestriction.LICENSED_FEED,
            AccessRestriction.APPROVAL_REQUIRED,
        }
    ):
        return "restricted"
    return "permitted"


def evaluate_acquisition_rights(
    policy: AcquisitionRightsPolicy,
    *,
    evaluated_at: datetime,
) -> RightsPolicyDecision:
    """Separate lawful internal provenance from byte publication."""

    reasons: list[str] = []
    retain = _may_retain(policy, evaluated_at)
    if not retain:
        reasons.append("retain_evidence does not permit internal provenance")
    if policy.review_status is not ReviewStatus.REVIEWED:
        reasons.append(f"review_status is {policy.review_status.value}")
    if policy.review_status is ReviewStatus.EXPIRED:
        reasons.append("rights review has expired")
    if (
        policy.review_expires_at is not None
        and policy.review_expires_at <= evaluated_at
    ):
        reasons.append("rights review expiry has been reached")
    if policy.publish_bytes is not Permission.PERMITTED:
        reasons.append(f"publish_bytes is {policy.publish_bytes.value}")
    if policy.redistribute is not Permission.PERMITTED:
        reasons.append(f"redistribute is {policy.redistribute.value}")
    if policy.licence_evidence_uri is None:
        reasons.append("licence evidence is missing")
    if not policy.maintainer_licence_approved:
        reasons.append("maintainer licence approval is required")
    if not policy.maintainer_publication_approved:
        reasons.append("maintainer publication approval is required")
    if policy.access_restriction is not AccessRestriction.NONE:
        reasons.append(
            "credentialed or restricted access cannot publish source bytes"
        )
    unique = tuple(sorted(set(reasons)))
    return RightsPolicyDecision(
        may_retain_internal_provenance=retain,
        may_publish_bytes=not unique,
        blocking_reasons=unique,
    )


def _may_retain(
    policy: AcquisitionRightsPolicy,
    _evaluated_at: datetime,
) -> bool:
    return policy.retain_evidence in {
        Permission.PERMITTED,
        Permission.CONDITIONAL,
    }


def _permissions_conflict(
    policies: tuple[AcquisitionRightsPolicy, ...],
) -> bool:
    return (
        len({
            (
                item.retain_evidence,
                item.publish_bytes,
                item.redistribute,
                item.transform,
                item.review_status,
                item.maintainer_licence_approved,
                item.maintainer_publication_approved,
            )
            for item in policies
        })
        > 1
    )


def _reject_credential_text(value: str | None) -> None:
    if value is None:
        return
    lowered = value.casefold()
    if any(marker in lowered for marker in _CREDENTIAL_MARKERS):
        raise ValueError("rights policy must not contain credential material")
