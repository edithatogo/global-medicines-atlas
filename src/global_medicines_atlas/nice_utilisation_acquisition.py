"""Fail-closed contracts for the historic NHS NICE-utilisation corpus."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel


class NICEUtilisationRelease(FrozenModel):
    """One source-native release in the discontinued experimental series."""

    label: Literal["2008", "2009", "2010-and-2011", "2012"]
    publication_date: date
    period_start: date
    period_end: date
    publication_url: AnyHttpUrl
    methodology_change: str = Field(min_length=1)
    corrected_after_publication: bool

    @model_validator(mode="after")
    def official_and_ordered(self) -> NICEUtilisationRelease:
        if self.publication_url.host != "digital.nhs.uk":
            raise ValueError(
                "NICE-utilisation releases must stay on digital.nhs.uk"
            )
        if self.period_end < self.period_start:
            raise ValueError("release period must be ordered")
        return self


class NICEUtilisationAuthorization(FrozenModel):
    """Maintainer decision binding the exact historic four-release corpus."""

    schema_id: Literal[
        "global-medicines-atlas.nice-utilisation-acquisition-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date | None
    decision_status: Literal["pending", "approved_internal"]
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    series_url: AnyHttpUrl
    terms_url: AnyHttpUrl
    series_status: Literal["discontinued"]
    expected_release_count: Literal[4]
    releases: tuple[NICEUtilisationRelease, ...]

    @model_validator(mode="after")
    def exact_scope(self) -> NICEUtilisationAuthorization:
        if (
            self.series_url.host != "digital.nhs.uk"
            or self.terms_url.host != "www.england.nhs.uk"
        ):
            raise ValueError(
                "NICE-utilisation authority must stay on official NHS hosts"
            )
        if len(self.releases) != self.expected_release_count:
            raise ValueError(
                "authorization must bind all four historic releases"
            )
        if tuple(item.label for item in self.releases) != (
            "2008",
            "2009",
            "2010-and-2011",
            "2012",
        ):
            raise ValueError("historic release sequence drifted")
        if not self.releases[-1].corrected_after_publication:
            raise ValueError("2012 correction must remain explicit")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError(
                "NICE-utilisation publication must remain separately gated"
            )
        if self.decision_status == "pending":
            if (
                self.decision_date is not None
                or self.acquisition_authorized
                or self.internal_retention_authorized
            ):
                raise ValueError(
                    "pending NICE-utilisation decision cannot authorize payloads"
                )
        elif (
            self.decision_date is None
            or not self.acquisition_authorized
            or not self.internal_retention_authorized
        ):
            raise ValueError(
                "approved NICE-utilisation acquisition requires dated authority"
            )
        return self

    def require_payload_authority(self) -> None:
        """Raise unless internal acquisition and retention are approved."""
        if self.decision_status != "approved_internal":
            raise PermissionError(
                "NICE-utilisation payload acquisition decision is pending"
            )
