"""Tests for the fail-closed Nordic utilisation public surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from global_medicines_atlas.nordic_utilisation_acquisition import (
    NordicAuthorization,
    load_nordic_authorization,
    parse_denmark_metadata_inventory,
    parse_sweden_query_inventory,
)

AUTHORIZATION = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/nordic-utilisation-acquisition-authorization.json"
)


def _raw() -> dict[str, object]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def _authorization() -> NordicAuthorization:
    return load_nordic_authorization(AUTHORIZATION)


def _sources(raw: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", raw["sources"])


def _denmark(*, last_year: int = 2025, population: bool = True) -> bytes:
    names = [
        f"{year}_{kind}_data.txt"
        for year in range(1996, last_year + 1)
        for kind in ("atc_code", "product_name")
    ]
    if population:
        names.append("population_data.txt")
    return "".join(
        f"<a href='/download/{index}'>{name}</a>"
        for index, name in enumerate(names)
    ).encode()


def _options(identifier: str, values: tuple[str, ...]) -> str:
    return (
        f"<select id='{identifier}'>"
        + "".join(
            f"<option value='{value}'>{value}</option>" for value in values
        )
        + "</select>"
    )


def _sweden(
    *,
    annual_end: int = 2025,
    geography_count: int = 22,
    measures: tuple[int, ...] = (1, 2, 3, 4, 9),
    limits: bool = True,
) -> bytes:
    html = "".join((
        _options("ARMANAD_IND", ("AR", "MAN_EJ_ALD", "MAN_EJ_REG")),
        _options("OMR", tuple(str(value) for value in range(geography_count))),
        _options("AGI", tuple(str(value) for value in range(18))),
        _options("KON", ("3", "1", "2")),
        _options(
            "AR", tuple(str(value) for value in range(2006, annual_end + 1))
        ),
        _options("AR_MANAD", tuple(str(value) for value in range(2006, 2027))),
        "".join(
            f"<input id='matti_{measure}_1'><label for='matti_{measure}_1'>measure</label>"
            for measure in measures
        ),
        "max antal 70 000 fler än 100 ATC-koder" if limits else "",
    ))
    return html.encode()


def test_authorization_is_independent_and_fail_closed() -> None:
    authorization = _authorization()
    assert tuple(source.source_id for source in authorization.sources) == (
        "dk-medstat-utilisation",
        "no-norpd-utilisation",
        "se-socialstyrelsen-utilisation",
    )
    for source in authorization.sources:
        with pytest.raises(
            PermissionError, match="payload decision is pending"
        ):
            source.require_payload_authority()


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"acquisition_authorized": True}, "pending Nordic decision"),
        ({"public_release_authorized": True}, "publication must remain"),
    ],
)
def test_pending_source_rejects_scope_widening(
    update: dict[str, object], message: str
) -> None:
    raw = _raw()
    sources = _sources(raw)
    sources[0].update(update)
    with pytest.raises(ValidationError, match=message):
        NordicAuthorization.model_validate(raw)


def test_approved_internal_source_requires_complete_dated_authority() -> None:
    raw = _raw()
    sources = _sources(raw)
    sources[0].update(
        decision_status="approved_internal",
        decision_date="2026-08-21",
        acquisition_authorized=True,
        internal_retention_authorized=True,
    )
    approved = NordicAuthorization.model_validate(raw)
    approved.sources[0].require_payload_authority()
    sources[0]["decision_date"] = None
    with pytest.raises(ValidationError, match="requires dated authority"):
        NordicAuthorization.model_validate(raw)


def test_authorization_rejects_missing_or_reordered_source() -> None:
    raw = _raw()
    sources = _sources(raw)
    raw["sources"] = list(reversed(sources))
    with pytest.raises(ValidationError, match="identity or order drifted"):
        NordicAuthorization.model_validate(raw)


def test_denmark_inventory_is_metadata_only_and_exact() -> None:
    inventory = parse_denmark_metadata_inventory(_denmark())
    assert inventory.first_year == 1996
    assert inventory.latest_year == 2025
    assert inventory.annual_metadata_file_count == 60
    assert inventory.population_file_present


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (_denmark(last_year=2024), "annual metadata inventory"),
        (_denmark(population=False), "population metadata identity"),
    ],
)
def test_denmark_inventory_rejects_drift(payload: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_denmark_metadata_inventory(payload)


def test_sweden_inventory_binds_current_aggregate_dimensions() -> None:
    inventory = parse_sweden_query_inventory(_sweden())
    assert inventory.resolution_modes == ("AR", "MAN_EJ_ALD", "MAN_EJ_REG")
    assert inventory.annual_years == tuple(range(2006, 2026))
    assert inventory.monthly_years == tuple(range(2006, 2027))
    assert inventory.geography_count == 22
    assert inventory.age_group_count == 18
    assert inventory.sex_count == 3
    assert inventory.measure_ids == (1, 2, 3, 4, 9)
    assert inventory.maximum_cells == 70_000
    assert inventory.maximum_atc_codes == 100


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (_sweden(geography_count=21), "query dimensions"),
        (_sweden(annual_end=2024), "year inventory"),
        (_sweden(measures=(1, 2, 3, 4)), "measure inventory"),
        (_sweden(limits=False), "query limits"),
    ],
)
def test_sweden_inventory_rejects_drift(payload: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_sweden_query_inventory(payload)
