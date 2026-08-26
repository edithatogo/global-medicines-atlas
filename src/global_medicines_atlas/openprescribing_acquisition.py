"""Fail-closed contracts for OpenPrescribing utilisation acquisition."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel


class OpenPrescribingEndpoint(FrozenModel):
    """One documented stable identity in the public API surface."""

    name: Literal[
        "spending",
        "spending_by_org",
        "bnf_code",
        "org_code",
        "org_details",
        "org_location",
    ]
    url: AnyHttpUrl
    formats: tuple[Literal["json", "csv"], ...]
    role: Literal["utilisation", "medicine_reference", "organisation_reference"]
    rolling_window: bool

    @model_validator(mode="after")
    def official_v1_surface(self) -> OpenPrescribingEndpoint:
        if self.url.host != "openprescribing.net":
            raise ValueError(
                "OpenPrescribing API endpoints must stay on openprescribing.net"
            )
        if not (self.url.path or "").startswith("/api/1.0/"):
            raise ValueError("OpenPrescribing endpoint must stay on API v1.0")
        if not self.formats or "json" not in self.formats:
            raise ValueError(
                "OpenPrescribing endpoint must retain JSON support"
            )
        if self.role == "utilisation" and not self.rolling_window:
            raise ValueError(
                "documented spending views must retain rolling-window semantics"
            )
        return self


class OpenPrescribingAuthorization(FrozenModel):
    """Maintainer decision for a bounded, reproducible API acquisition."""

    schema_id: Literal[
        "global-medicines-atlas.openprescribing-acquisition-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date | None
    decision_status: Literal["pending", "approved_internal", "approved_public"]
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    documentation_url: AnyHttpUrl
    rights_url: AnyHttpUrl
    licence_url: AnyHttpUrl
    attribution_statement: str = Field(min_length=1)
    upstream_monthly_source_url: AnyHttpUrl
    documentation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    documentation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_endpoint_count: Literal[6]
    endpoints: tuple[OpenPrescribingEndpoint, ...]
    archive_strategy: Literal["receipt_bound_partitioned_queries"]
    unbounded_api_crawl_authorized: Literal[False]
    upstream_monthly_epd_substitution: Literal[False]

    @model_validator(mode="after")
    def exact_scope(self) -> OpenPrescribingAuthorization:
        if (
            self.documentation_url.host != "openprescribing.net"
            or self.rights_url.host != "openprescribing.net"
        ):
            raise ValueError(
                "OpenPrescribing authority must stay on the official service"
            )
        if self.licence_url.host != "www.nationalarchives.gov.uk":
            raise ValueError("OpenPrescribing licence must stay on the OGL")
        if self.upstream_monthly_source_url.host != "www.nhsbsa.nhs.uk":
            raise ValueError("upstream monthly identity must stay on NHSBSA")
        if len(self.endpoints) != self.expected_endpoint_count:
            raise ValueError("authorization must bind all six API identities")
        if tuple(item.name for item in self.endpoints) != (
            "spending",
            "spending_by_org",
            "bnf_code",
            "org_code",
            "org_details",
            "org_location",
        ):
            raise ValueError("OpenPrescribing API identity sequence drifted")
        if self.decision_status == "pending":
            if (
                self.decision_date is not None
                or self.acquisition_authorized
                or self.internal_retention_authorized
                or self.public_release_authorized
                or self.external_publication_authorized
            ):
                raise ValueError(
                    "pending OpenPrescribing decision cannot authorize payloads"
                )
        elif self.decision_status == "approved_internal" and (
            self.decision_date is None
            or not all((
                self.acquisition_authorized,
                self.internal_retention_authorized,
            ))
            or any((
                self.public_release_authorized,
                self.external_publication_authorized,
            ))
        ):
            raise ValueError(
                "approved OpenPrescribing acquisition requires dated authority"
            )
        elif self.decision_status == "approved_public" and not all((
            self.decision_date is not None,
            self.acquisition_authorized,
            self.internal_retention_authorized,
            self.public_release_authorized,
            self.external_publication_authorized,
        )):
            raise ValueError(
                "approved public OpenPrescribing authority requires "
                "acquisition, retention, release, and publication"
            )
        return self

    def require_payload_authority(self) -> None:
        """Raise unless internal acquisition and retention are approved."""
        if self.decision_status == "pending":
            raise PermissionError(
                "OpenPrescribing payload acquisition decision is pending"
            )

    def require_publication_authority(self) -> None:
        """Raise unless public release and external publication are approved."""
        if (
            self.decision_status != "approved_public"
            or not self.public_release_authorized
            or not self.external_publication_authorized
        ):
            raise PermissionError(
                "OpenPrescribing publication is not authorized"
            )

    def require_reproducible_partition(
        self, *, date_partition: date | None
    ) -> None:
        """Reject unbounded rolling-window utilisation captures."""
        self.require_payload_authority()
        if date_partition is None:
            raise ValueError(
                "OpenPrescribing utilisation capture requires an explicit date partition"
            )
