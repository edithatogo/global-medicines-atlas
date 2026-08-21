"""Tests for Prompt 35 global pharmacovigilance source contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from global_medicines_atlas.global_pv_acquisition import (
    GlobalPvAuthorization,
    load_global_pv_authorization,
    parse_canada_vigilance_structure,
    parse_mhra_yellow_card_surface,
    parse_pmda_safety_surface,
    parse_tga_daen_surface,
)

AUTHORIZATION = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/global-pv-acquisition-authorization.json"
)


def _raw() -> dict[str, object]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def _sources(raw: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", raw["sources"])


def test_authorization_is_independent_and_fail_closed() -> None:
    authority = load_global_pv_authorization(AUTHORIZATION)
    assert len(authority.sources) == 5
    for source in authority.sources:
        with pytest.raises(
            PermissionError, match="payload decision is pending"
        ):
            source.require_payload_authority()


def test_authorization_rejects_identity_and_scope_drift() -> None:
    raw = _raw()
    raw["sources"] = list(reversed(_sources(raw)))
    with pytest.raises(ValidationError, match="identity or order drifted"):
        GlobalPvAuthorization.model_validate(raw)
    raw = _raw()
    _sources(raw)[3]["acquisition_authorized"] = True
    _sources(raw)[3]["decision_date"] = "2026-08-21"
    _sources(raw)[3]["internal_retention_authorized"] = True
    with pytest.raises(ValidationError, match="pending Prompt 35"):
        GlobalPvAuthorization.model_validate(raw)


def test_authorization_rejects_incomplete_approvals() -> None:
    raw = _raw()
    _sources(raw)[3].update({
        "decision_status": "approved_internal",
        "decision_date": "2026-08-21",
    })
    with pytest.raises(ValidationError, match="bounded authority"):
        GlobalPvAuthorization.model_validate(raw)
    raw = _raw()
    _sources(raw)[3].update({
        "decision_status": "approved_public",
        "decision_date": "2026-08-21",
        "acquisition_authorized": True,
        "internal_retention_authorized": True,
    })
    with pytest.raises(ValidationError, match="complete authority"):
        GlobalPvAuthorization.model_validate(raw)


@pytest.mark.parametrize("status", ["approved_internal", "approved_public"])
def test_complete_approval_can_authorize_payload(status: str) -> None:
    raw = _raw()
    source = _sources(raw)[3]
    source.update({
        "decision_status": status,
        "decision_date": "2026-08-21",
        "acquisition_authorized": True,
        "internal_retention_authorized": True,
        "public_release_authorized": status == "approved_public",
        "external_publication_authorized": status == "approved_public",
    })
    authority = GlobalPvAuthorization.model_validate(raw)
    authority.sources[3].require_payload_authority()


def test_canada_metadata_preserves_documented_discrepancy() -> None:
    names = (
        "Reports.txt",
        "Drug_Product.txt",
        "Drug_Product_Ingredients.txt",
        "Reactions.txt",
        "Outcome_LX.txt",
        "Gender_LX.txt",
        "Report_Type_LX.txt",
        "Seriousness_LX.txt",
        "Source_LX.txt",
        "Report_Links_LX.txt",
        "Report_Drug.txt",
        "Report_Drug_Indication.txt",
        "Literature_Reference.txt",
    )
    payload = (
        "comprised of 11 files" + "".join(f"><a>{name}</a>" for name in names)
    ).encode()
    surface = parse_canada_vigilance_structure(payload)
    assert len(surface.artefacts) == 13
    assert "says 11 files" in surface.limitation
    with pytest.raises(ValueError, match="table inventory"):
        parse_canada_vigilance_structure(
            payload.replace(b"Reports.txt", b"Missing.txt")
        )
    with pytest.raises(ValueError, match="count discrepancy"):
        parse_canada_vigilance_structure(
            payload.replace(b"11 files", b"13 files")
        )


def test_interactive_and_document_surfaces_are_bounded() -> None:
    tga = parse_tga_daen_surface(b"1 January 1971 14 days 150,000 30,000")
    assert tga.artefacts == ("xlsx-current-layout", "csv-summarised")
    mhra = parse_mhra_yellow_card_surface(
        b"interactive Drug Analysis Profiles active substance"
    )
    assert mhra.surface_kind == "interactive_export"
    pmda = parse_pmda_safety_surface(
        b"Post-marketing Safety only in Japanese since April 2004"
    )
    assert pmda.surface_kind == "documents"


@pytest.mark.parametrize(
    ("parser", "payload", "message"),
    [
        (parse_tga_daen_surface, b"1 January 1971", "TGA DAEN"),
        (parse_mhra_yellow_card_surface, b"interactive", "MHRA Yellow Card"),
        (parse_pmda_safety_surface, b"Post-marketing Safety", "PMDA safety"),
    ],
)
def test_public_surfaces_reject_drift(
    parser: object, payload: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        cast("object", parser)(payload)  # type: ignore[operator]
