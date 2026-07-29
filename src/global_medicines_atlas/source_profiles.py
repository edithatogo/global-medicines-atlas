"""Generic acquisition profiles for documented source interfaces.

Profiles describe transport policy only. They do not claim that a
source-specific parser, fixture, or live receipt exists.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from .models import FrozenModel


class AuthenticationMode(StrEnum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH = "oauth"
    ACCOUNT = "account"
    SUBSCRIPTION = "subscription"
    MANUAL_APPROVAL = "manual_approval"
    CERTIFICATE = "certificate"
    UNKNOWN = "unknown"


class AcquisitionTransport(StrEnum):
    HTTP_DOWNLOAD = "http_download"
    REST = "rest"
    FHIR = "fhir"
    RSS = "rss"
    LICENSED_DOWNLOAD = "licensed_download"


class AcquisitionProfile(FrozenModel):
    profile_id: str = Field(min_length=1)
    transport: AcquisitionTransport
    authentication: AuthenticationMode
    minimum_interval_seconds: float = Field(ge=0)
    expected_cadence: str = Field(min_length=1)
    supports_conditional_requests: bool
    notes: str = Field(min_length=1)


PROFILES: tuple[AcquisitionProfile, ...] = (
    AcquisitionProfile(
        profile_id="public-bulk",
        transport=AcquisitionTransport.HTTP_DOWNLOAD,
        authentication=AuthenticationMode.NONE,
        minimum_interval_seconds=1,
        expected_cadence="source-declared",
        supports_conditional_requests=True,
        notes="Snapshot download with digest, content-type, and size controls.",
    ),
    AcquisitionProfile(
        profile_id="public-rest",
        transport=AcquisitionTransport.REST,
        authentication=AuthenticationMode.NONE,
        minimum_interval_seconds=1,
        expected_cadence="source-declared",
        supports_conditional_requests=True,
        notes="Documented public REST interface; paginate and retain raw pages.",
    ),
    AcquisitionProfile(
        profile_id="rate-limited-rest",
        transport=AcquisitionTransport.REST,
        authentication=AuthenticationMode.NONE,
        minimum_interval_seconds=20,
        expected_cadence="source-declared",
        supports_conditional_requests=False,
        notes="Conservative shared-rate-limit profile, including PBS public API.",
    ),
    AcquisitionProfile(
        profile_id="keyed-rest",
        transport=AcquisitionTransport.REST,
        authentication=AuthenticationMode.API_KEY,
        minimum_interval_seconds=1,
        expected_cadence="source-declared",
        supports_conditional_requests=False,
        notes="Credential supplied at runtime; never persisted in catalog data.",
    ),
    AcquisitionProfile(
        profile_id="oauth-rest",
        transport=AcquisitionTransport.REST,
        authentication=AuthenticationMode.OAUTH,
        minimum_interval_seconds=1,
        expected_cadence="source-declared",
        supports_conditional_requests=False,
        notes="OAuth token is an external gate and is never stored in receipts.",
    ),
    AcquisitionProfile(
        profile_id="keyed-fhir",
        transport=AcquisitionTransport.FHIR,
        authentication=AuthenticationMode.API_KEY,
        minimum_interval_seconds=1,
        expected_cadence="source-declared",
        supports_conditional_requests=True,
        notes="FHIR capability and terminology operations require qualification.",
    ),
    AcquisitionProfile(
        profile_id="public-fhir",
        transport=AcquisitionTransport.FHIR,
        authentication=AuthenticationMode.NONE,
        minimum_interval_seconds=1,
        expected_cadence="source-declared",
        supports_conditional_requests=True,
        notes="Public documented FHIR service; persist capability metadata.",
    ),
    AcquisitionProfile(
        profile_id="account-download",
        transport=AcquisitionTransport.LICENSED_DOWNLOAD,
        authentication=AuthenticationMode.ACCOUNT,
        minimum_interval_seconds=1,
        expected_cadence="source-declared",
        supports_conditional_requests=False,
        notes="Account, subscription, and licence acceptance remain external.",
    ),
)


def acquisition_profile(profile_id: str) -> AcquisitionProfile:
    """Resolve one governed generic profile."""

    matches = tuple(
        profile for profile in PROFILES if profile.profile_id == profile_id
    )
    if len(matches) != 1:
        raise LookupError(
            f"acquisition profile must resolve once: {profile_id}"
        )
    return matches[0]
