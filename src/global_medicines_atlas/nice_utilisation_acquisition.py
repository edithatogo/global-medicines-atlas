"""Fail-closed contracts for the historic NHS NICE-utilisation corpus."""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

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


class NICEUtilisationArtifact(FrozenModel):
    """One exact first-party file in the approved private corpus."""

    release_label: Literal["2008", "2009", "2010-and-2011", "2012"]
    role: Literal[
        "report",
        "tables",
        "data_quality_statement",
        "feedback_form",
        "pre_release_access",
        "annex",
    ]
    url: AnyHttpUrl
    filename: str = Field(min_length=1)
    source_record_eligible: bool = False
    third_party_content_risk: Literal[
        "declared_in_release",
        "ancillary_governance_document",
    ]
    publication_authorized: Literal[False] = False

    @model_validator(mode="after")
    def exact_official_file(self) -> NICEUtilisationArtifact:
        if self.url.host != "files.digital.nhs.uk":
            raise ValueError(
                "NICE-utilisation files must stay on the official host"
            )
        suffix = self.filename.rsplit(".", 1)[-1].casefold()
        if suffix not in {"pdf", "xlsx", "doc"}:
            raise ValueError(
                "NICE-utilisation file type is outside reviewed scope"
            )
        if self.source_record_eligible != (self.role == "tables"):
            raise ValueError(
                "only the reviewed workbook is source-record eligible"
            )
        return self


def _artifact(
    release_label: Literal["2008", "2009", "2010-and-2011", "2012"],
    role: Literal[
        "report",
        "tables",
        "data_quality_statement",
        "feedback_form",
        "pre_release_access",
        "annex",
    ],
    url: str,
) -> NICEUtilisationArtifact:
    filename = url.rsplit("/", 1)[-1]
    primary = role in {"report", "tables", "annex"}
    return NICEUtilisationArtifact(
        release_label=release_label,
        role=role,
        url=AnyHttpUrl(url),
        filename=filename,
        source_record_eligible=role == "tables",
        third_party_content_risk=(
            "declared_in_release"
            if primary
            else "ancillary_governance_document"
        ),
    )


NICE_UTILISATION_ARTIFACTS: Final = (
    _artifact(
        "2008",
        "report",
        "https://files.digital.nhs.uk/publicationimport/pub01xxx/pub01400/use-nice-app-med-nhs-exp-stat-eng-exp.pdf",
    ),
    _artifact(
        "2008",
        "pre_release_access",
        "https://files.digital.nhs.uk/publicationimport/pub01xxx/pub01400/use-nice-app-med-nhs-exp-stat-eng-pra.pdf",
    ),
    _artifact(
        "2008",
        "annex",
        "https://files.digital.nhs.uk/publicationimport/pub01xxx/pub01400/use-nice-app-med-nhs-exp-stat-eng-anx.pdf",
    ),
    _artifact(
        "2009",
        "report",
        "https://files.digital.nhs.uk/publicationimport/pub01xxx/pub01470/use-nice-app-med-nhs-exp-stat-eng-09-rep.pdf",
    ),
    _artifact(
        "2009",
        "data_quality_statement",
        "https://files.digital.nhs.uk/publicationimport/pub01xxx/pub01470/use-nice-app-med-nhs-exp-stat-eng-09-qual.pdf",
    ),
    _artifact(
        "2009",
        "pre_release_access",
        "https://files.digital.nhs.uk/publicationimport/pub01xxx/pub01470/use-nice-app-med-nhs-exp-stat-eng-09-pra.pdf",
    ),
    _artifact(
        "2010-and-2011",
        "report",
        "https://files.digital.nhs.uk/publicationimport/pub07xxx/pub07985/use-nice-app-med-nhs-exp-stat-eng-10-11-rep.pdf",
    ),
    _artifact(
        "2010-and-2011",
        "data_quality_statement",
        "https://files.digital.nhs.uk/publicationimport/pub07xxx/pub07985/use-nice-app-med-nhs-exp-stat-eng-10-11-qual.pdf",
    ),
    _artifact(
        "2010-and-2011",
        "feedback_form",
        "https://files.digital.nhs.uk/publicationimport/pub07xxx/pub07985/use-nice-app-med-nhs-exp-stat-eng-10-11-feed.doc",
    ),
    _artifact(
        "2010-and-2011",
        "pre_release_access",
        "https://files.digital.nhs.uk/publicationimport/pub07xxx/pub07985/use-nice-app-med-nhs-exp-stat-eng-10-11-pra.pdf",
    ),
    _artifact(
        "2012",
        "report",
        "https://files.digital.nhs.uk/publicationimport/pub13xxx/pub13413/use-nice-app-med-nhs-exp-stat-eng-12-rep.pdf",
    ),
    _artifact(
        "2012",
        "tables",
        "https://files.digital.nhs.uk/publicationimport/pub13xxx/pub13413/use-nice-app-med-nhs-exp-stat-eng-12-tab.xlsx",
    ),
    _artifact(
        "2012",
        "data_quality_statement",
        "https://files.digital.nhs.uk/publicationimport/pub13xxx/pub13413/use-nice-app-med-nhs-exp-stat-eng-12-qual.pdf",
    ),
    _artifact(
        "2012",
        "feedback_form",
        "https://files.digital.nhs.uk/publicationimport/pub13xxx/pub13413/use-nice-app-med-nhs-exp-stat-eng-12-fbk.doc",
    ),
    _artifact(
        "2012",
        "pre_release_access",
        "https://files.digital.nhs.uk/publicationimport/pub13xxx/pub13413/use-nice-app-med-nhs-exp-stat-eng-12-pra.pdf",
    ),
)


def inspect_nice_utilisation_payload(filename: str, payload: bytes) -> str:
    """Verify file extension and conservative source-format magic."""
    suffix = filename.rsplit(".", 1)[-1].casefold()
    valid = {
        "pdf": payload.startswith(b"%PDF-"),
        "xlsx": payload.startswith(b"PK\x03\x04")
        and b"xl/workbook.xml" in payload,
        "doc": payload.startswith(b"\xd0\xcf\x11\xe0"),
    }
    if suffix not in valid or not valid[suffix]:
        raise ValueError(
            "NICE-utilisation payload does not match declared format"
        )
    return suffix
