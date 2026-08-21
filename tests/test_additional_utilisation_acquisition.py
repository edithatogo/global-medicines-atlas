"""Tests for Prompt 34 public utilisation source surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from global_medicines_atlas.additional_utilisation_acquisition import (
    AdditionalUtilisationAuthorization,
    load_additional_utilisation_authorization,
    parse_cihi_nhex_public_surface,
    parse_hse_pcrs_public_surface,
    parse_japan_ndb_public_surface,
    parse_open_medic_inventory,
)

AUTHORIZATION = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/additional-utilisation-acquisition-authorization.json"
)


def _raw() -> dict[str, object]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def _sources(raw: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", raw["sources"])


def _open_medic(*, licence: str = "fr-lo", latest: int = 2025) -> bytes:
    resources: list[dict[str, object]] = [
        {"title": f"{year} complete", "format": "csv"}
        for year in range(2014, latest + 1)
    ]
    resources.extend(
        {"title": "support", "format": "csv"}
        for _ in range(82 - len(resources))
    )
    supplements: list[dict[str, object]] = [
        {"title": "documentation", "format": "xlsx"},
        {"title": "metadata", "format": None},
        {"title": "metadata", "format": None},
    ]
    resources.extend(supplements)
    return json.dumps({"license": licence, "resources": resources}).encode()


def _japan(*, workbook: bool = True) -> bytes:
    param = (
        "<param name='host_url' value='https%3A%2F%2Fpublic.tableau.com%2F' />"
        "<param name='name' value='6__16433435613770&#47;pattern7' />"
        if workbook
        else ""
    )
    return ("第6回 処方薬 都道府県別 薬効分類別数量" + param).encode()


def _canada(*, open_data: bool = True) -> bytes:
    links = "<a href='/nhex-series-g-2025-en.xlsx'>Expenditure on drugs</a>" + (
        "<a href='/nhex-open-data-2025-en.xlsx'>View open data</a>"
        if open_data
        else ""
    )
    return ("<p>NHEX trends data</p>" + links).encode()


def _ireland(*, report: bool = True) -> bytes:
    link = (
        "<a href='https://about.hse.ie/api/v2/download-file/file_based_publications/"
        "PCRS_Statistical_Analysis_of_Claims_and_Payments_2024.pdf'>PDF</a>"
        if report
        else ""
    )
    return (
        "PCRS Statistical Analysis of Claims and Payments 2024" + link
    ).encode()


def test_authorization_preserves_independent_source_decisions() -> None:
    authorization = load_additional_utilisation_authorization(AUTHORIZATION)
    assert tuple(source.source_id for source in authorization.sources) == (
        "fr-open-medic",
        "jp-mhlw-ndb-utilisation",
        "ca-cihi-nhex-medicines",
        "ie-pcrs-reimbursement",
    )
    authorization.sources[0].require_payload_authority()
    for source in authorization.sources[1:]:
        with pytest.raises(
            PermissionError, match="payload decision is pending"
        ):
            source.require_payload_authority()


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"acquisition_authorized": True}, "pending Prompt 34 decision"),
        (
            {
                "decision_status": "approved_internal",
                "decision_date": "2026-08-21",
                "acquisition_authorized": True,
                "internal_retention_authorized": True,
                "public_release_authorized": True,
            },
            "requires dated authority",
        ),
    ],
)
def test_authorization_rejects_scope_widening(
    update: dict[str, object], message: str
) -> None:
    raw = _raw()
    _sources(raw)[1].update(update)
    with pytest.raises(ValidationError, match=message):
        AdditionalUtilisationAuthorization.model_validate(raw)


def test_authorization_rejects_source_identity_drift() -> None:
    raw = _raw()
    raw["sources"] = list(reversed(_sources(raw)))
    with pytest.raises(ValidationError, match="identity or order drifted"):
        AdditionalUtilisationAuthorization.model_validate(raw)


def test_approved_public_source_requires_complete_authority() -> None:
    raw = _raw()
    _sources(raw)[0]["external_publication_authorized"] = False
    with pytest.raises(ValidationError, match="requires complete authority"):
        AdditionalUtilisationAuthorization.model_validate(raw)


def test_open_medic_inventory_is_exact() -> None:
    inventory = parse_open_medic_inventory(_open_medic())
    assert inventory.years == tuple(range(2014, 2026))
    assert inventory.resource_count == 85
    assert inventory.csv_resource_count == 82


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (_open_medic(licence="other"), "licence identity"),
        (_open_medic(latest=2024), "year inventory"),
    ],
)
def test_open_medic_inventory_rejects_drift(
    payload: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_open_medic_inventory(payload)


def test_open_medic_inventory_rejects_missing_and_count_drift() -> None:
    with pytest.raises(TypeError, match="resources missing"):
        parse_open_medic_inventory(b'{"license":"fr-lo","resources":{}}')
    raw = json.loads(_open_medic())
    cast("list[object]", raw["resources"]).pop()
    with pytest.raises(ValueError, match="resource inventory"):
        parse_open_medic_inventory(json.dumps(raw).encode())


def test_japan_public_surface_is_interactive_aggregate() -> None:
    inventory = parse_japan_ndb_public_surface(_japan())
    assert inventory.source_id == "jp-mhlw-ndb-utilisation"
    assert inventory.artefact_urls == (
        "https://public.tableau.com/views/6__16433435613770/pattern7",
    )


def test_japan_public_surface_rejects_drift() -> None:
    with pytest.raises(ValueError, match="NDB public aggregate surface"):
        parse_japan_ndb_public_surface(_japan(workbook=False))


def test_cihi_surface_has_drug_and_open_data_workbooks() -> None:
    inventory = parse_cihi_nhex_public_surface(_canada())
    assert inventory.publication_year == 2025
    assert len(inventory.artefact_urls) == 2


def test_cihi_surface_rejects_missing_open_data() -> None:
    with pytest.raises(ValueError, match="CIHI NHEX public surface"):
        parse_cihi_nhex_public_surface(_canada(open_data=False))


def test_hse_surface_has_scheme_bounded_report() -> None:
    inventory = parse_hse_pcrs_public_surface(_ireland())
    assert inventory.source_id == "ie-pcrs-reimbursement"
    assert inventory.publication_year == 2024


def test_hse_surface_rejects_missing_report() -> None:
    with pytest.raises(ValueError, match="HSE PCRS public report"):
        parse_hse_pcrs_public_surface(_ireland(report=False))
