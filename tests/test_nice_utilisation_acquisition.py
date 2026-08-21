"""Tests for the historic NHS NICE-utilisation acquisition gate."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.nice_utilisation_acquisition import (
    NICEUtilisationAuthorization,
)

AUTHORIZATION = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
)


def _raw() -> dict[str, object]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def test_inventory_locks_the_discontinued_four_release_series() -> None:
    authorization = NICEUtilisationAuthorization.model_validate(_raw())
    assert [item.label for item in authorization.releases] == [
        "2008",
        "2009",
        "2010-and-2011",
        "2012",
    ]
    assert authorization.releases[-1].corrected_after_publication is True
    with pytest.raises(PermissionError, match="decision is pending"):
        authorization.require_payload_authority()


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"acquisition_authorized": True}, "pending NICE-utilisation"),
        ({"public_release_authorized": True}, "separately gated"),
        ({"series_url": "https://example.test/series"}, "official NHS hosts"),
    ],
)
def test_authorization_rejects_scope_widening(
    update: dict[str, object], message: str
) -> None:
    raw = _raw()
    raw.update(update)
    with pytest.raises(ValidationError, match=message):
        NICEUtilisationAuthorization.model_validate(raw)


def test_release_inventory_and_correction_cannot_drift() -> None:
    raw = _raw()
    raw["releases"] = list(raw["releases"])[:-1]  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="all four historic releases"):
        NICEUtilisationAuthorization.model_validate(raw)
    raw = _raw()
    releases = list(raw["releases"])  # type: ignore[arg-type]
    releases[-1] = {**releases[-1], "corrected_after_publication": False}
    raw["releases"] = releases
    with pytest.raises(
        ValidationError, match="correction must remain explicit"
    ):
        NICEUtilisationAuthorization.model_validate(raw)

    raw = _raw()
    releases = list(raw["releases"])  # type: ignore[arg-type]
    releases[0] = {**releases[0], "label": "2009"}
    raw["releases"] = releases
    with pytest.raises(
        ValidationError, match="historic release sequence drifted"
    ):
        NICEUtilisationAuthorization.model_validate(raw)


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"publication_url": "https://example.test/release"}, "digital.nhs.uk"),
        ({"period_start": "2008-01-02"}, "period must be ordered"),
    ],
)
def test_release_rejects_host_and_period_drift(
    update: dict[str, object], message: str
) -> None:
    raw = _raw()
    releases = list(raw["releases"])  # type: ignore[arg-type]
    releases[0] = {**releases[0], **update}
    raw["releases"] = releases
    with pytest.raises(ValidationError, match=message):
        NICEUtilisationAuthorization.model_validate(raw)


def test_approved_internal_scope_requires_date_and_retention() -> None:
    raw = _raw()
    raw.update({
        "decision_status": "approved_internal",
        "decision_date": "2026-08-21",
        "acquisition_authorized": True,
        "internal_retention_authorized": True,
    })
    NICEUtilisationAuthorization.model_validate(raw).require_payload_authority()
    raw["decision_date"] = None
    with pytest.raises(ValidationError, match="requires dated authority"):
        NICEUtilisationAuthorization.model_validate(raw)
