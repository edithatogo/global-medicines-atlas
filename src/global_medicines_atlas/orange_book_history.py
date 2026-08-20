"""Fail-closed planning for FDA Orange Book historical acquisition."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel

_OFFICIAL_HOSTS = frozenset({"www.fda.gov", "wayback.archive-it.org"})
_EXPECTED_SURFACE_COUNT = 5


class OrangeBookReleaseSurface(FrozenModel):
    """One official surface relevant to the versioned Orange Book family."""

    release_kind: Literal[
        "current_structured_zip",
        "current_annual_edition",
        "current_cumulative_supplement",
        "monthly_additions_deletions_index",
        "legacy_fda_archive_index",
    ]
    url: AnyHttpUrl
    media_hint: Literal["zip", "pdf", "html"]
    source_version: str = Field(min_length=1)
    max_bytes: int = Field(ge=1, le=512 * 1024 * 1024)

    @model_validator(mode="after")
    def official_fda_surface(self) -> OrangeBookReleaseSurface:
        if self.url.host not in _OFFICIAL_HOSTS:
            raise ValueError("release surface must use an official FDA host")
        if (
            self.url.host == "wayback.archive-it.org"
            and self.release_kind != "legacy_fda_archive_index"
        ):
            raise ValueError("Archive-It is allowed only for the FDA archive")
        return self


class OrangeBookHistoricalPlan(FrozenModel):
    """Maintainer-gated plan for historical Orange Book source bytes."""

    schema_id: Literal["global-medicines-atlas.orange-book-historical-plan"]
    schema_version: Literal[1]
    source_id: Literal["us-fda-orange-book"]
    prompt_id: Literal[16]
    observed_at: date
    official_documentation: tuple[AnyHttpUrl, ...]
    observed_release_link_count: int = Field(ge=0)
    observed_release_range: str = Field(min_length=1)
    historical_inventory_complete: bool
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    maintainer_decision: str | None
    rights_profile: Literal["government_public_domain_policy_review"]
    surfaces: tuple[OrangeBookReleaseSurface, ...]
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def fail_closed_scope(self) -> OrangeBookHistoricalPlan:
        if self.historical_inventory_complete:
            raise ValueError("bounded discovery cannot claim complete history")
        if any(
            url.host != "www.fda.gov" for url in self.official_documentation
        ):
            raise ValueError("documentation must use the official FDA host")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("historical plan cannot authorize publication")
        if self.acquisition_authorized and (
            not self.internal_retention_authorized
            or not self.maintainer_decision
        ):
            raise ValueError(
                "acquisition authority requires an explicit maintainer decision "
                "and internal retention authorization"
            )
        if (
            not self.acquisition_authorized
            and self.internal_retention_authorized
        ):
            raise ValueError(
                "retention cannot precede acquisition authorization"
            )
        kinds = [surface.release_kind for surface in self.surfaces]
        if len(kinds) != len(set(kinds)):
            raise ValueError("release surface kinds must be unique")
        if len(kinds) != _EXPECTED_SURFACE_COUNT:
            raise ValueError("plan must preserve all five observed surfaces")
        return self


class HistoricalRequest(FrozenModel):
    """A bounded request emitted only by the applicable planning gate."""

    method: Literal["HEAD", "GET"]
    url: AnyHttpUrl
    max_response_body_bytes: int = Field(ge=0)
    release_kind: str = Field(min_length=1)


def build_metadata_probe_requests(
    plan: OrangeBookHistoricalPlan,
) -> tuple[HistoricalRequest, ...]:
    """Build body-free metadata probes for the observed release surfaces."""
    return tuple(
        HistoricalRequest(
            method="HEAD",
            url=surface.url,
            max_response_body_bytes=0,
            release_kind=surface.release_kind,
        )
        for surface in plan.surfaces
    )


def build_payload_requests(
    plan: OrangeBookHistoricalPlan,
) -> tuple[HistoricalRequest, ...]:
    """Build bounded payload requests after explicit maintainer authorization."""
    if not plan.acquisition_authorized:
        raise PermissionError(
            "historical Orange Book payloads require maintainer authorization"
        )
    if not plan.historical_inventory_complete:
        raise PermissionError(
            "historical Orange Book payloads require a complete release inventory"
        )
    return tuple(
        HistoricalRequest(
            method="GET",
            url=surface.url,
            max_response_body_bytes=surface.max_bytes,
            release_kind=surface.release_kind,
        )
        for surface in plan.surfaces
    )
