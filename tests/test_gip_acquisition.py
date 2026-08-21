"""Tests for the fail-closed GIP medicine inventory."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError

from global_medicines_atlas.gip_acquisition import (
    GIPAuthorization,
    GIPRelease,
    parse_gip_inventory,
)

AUTHORIZATION = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/gip-acquisition-authorization.json"
)
TITLES = (
    "GIP Addon Zvw meerjaren 2021-2025_12062026",
    "GIP Farmacie Zvw meerjaren 2021-2025_11052026",
    "GIP Farmacie Zvw lftgesl 2025_11052026",
    "GIP Addon Zvw meerjaren 2020-2024_18042025",
    "GIP Farmacie Zvw meerjaren 2020-2024_18042025",
    "GIP Farmacie Zvw lftgesl 2024_18042025",
    "GIP Addon Zvw meerjaren 2019-2023_22012025",
    "GIP farmacie Zvw meerjaren 2019-2023_08052024",
    "GIP Farmacie Zvw lftgesl 2023_08052024",
    "GIP Addon Zvw meerjaren 2018-2022_13122023",
    "GIP Farmacie Zvw meerjaren 2018-2022_26052022",
    "GIP Farmacie Zvw lftgesl 2022_26052023",
    "GIP addon Zvw meerjaren 2017-2021_20122023",
    "GIP Farmacie Zvw meerjaren 2017-2021_08062022",
    "GIP Farmacie Zvw lftgesl 2021_08062022",
    "GIP Farmacie Zvw meerjaren 2016-2020_27052021",
    "GIP Farmacie Zvw lftgesl 2020_27052021",
    "GIP Farmacie Zvw meerjaren 2015-2019_20102020",
    "GIP Farmacie Zvw lftgesl 2019_20102020",
    "GIP Farmacie Zvw meerjaren 2014-2018_04112019",
    "GIP Farmacie Zvw lftgesl 2018_04112019",
    "GIP Farmacie Zvw meerjaren 2013-2017_04092018",
    "GIP Farmacie Zvw lftgesl 2017_04092018",
    "GIP Farmacie Zvw meerjaren 2012-2016_25012018",
    "GIP Farmacie Zvw lftgesl 2016_25012018",
    "GIP Farmacie Zvw lftgesl 2015_23012019",
    "GIP Farmacie Zvw lftgesl 2014_23012019",
    "GIP Farmacie Zvw lftgesl 2013_23012019",
)


def _authorization(**updates: object) -> GIPAuthorization:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw.update(updates)
    return GIPAuthorization.model_validate(raw)


def _landing(titles: tuple[str, ...] = TITLES) -> bytes:
    links = [
        f'<a class="file-download extra" href="/services/file/get?key=k{index}"><h4 class="title">{title}</h4></a>'
        for index, title in enumerate(titles)
    ]
    return ("<html><body>" + "".join(links) + "</body></html>").encode()


def test_inventory_locks_all_28_medicine_files() -> None:
    authorization = _authorization()
    inventory = parse_gip_inventory(_landing(), authorization=authorization)
    assert inventory.release_count == 28
    assert sum(item.family == "farmacie" for item in inventory.releases) == 23
    assert sum(item.family == "addon" for item in inventory.releases) == 5
    assert inventory.releases[0].version_date.isoformat() == "2026-06-12"
    with pytest.raises(PermissionError, match="decision is pending"):
        authorization.require_payload_authority()


def test_inventory_ignores_unrelated_downloads_but_rejects_drift() -> None:
    harmless = (
        _landing()
        + b'<p>ordinary text</p><a class="file-download" href="/empty">'
        + b'<h4 class="title"></h4></a><a class="file-download" href="/x">'
        + b'<h4 class="title">GIP Hulpmiddelen</h4></a>'
    )
    assert (
        parse_gip_inventory(
            harmless, authorization=_authorization()
        ).release_count
        == 28
    )
    with pytest.raises(ValueError, match="inventory drifted"):
        parse_gip_inventory(
            _landing(TITLES[:-1]), authorization=_authorization()
        )
    malformed = (
        _landing()
        + b'<a class="file-download" href="/x"><h4 class="title">broken'
    )
    assert (
        parse_gip_inventory(
            malformed, authorization=_authorization()
        ).release_count
        == 28
    )


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"acquisition_authorized": True}, "pending GIP decision"),
        ({"public_release_authorized": True}, "separately gated"),
        (
            {"landing_url": "https://example.test/open"},
            "zorgcijfersdatabank.nl",
        ),
    ],
)
def test_authorization_rejects_scope_widening(
    updates: dict[str, object], message: str
) -> None:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw.update(updates)
    with pytest.raises(ValidationError, match=message):
        GIPAuthorization.model_validate(raw)


def test_approved_internal_scope_requires_date_and_retention() -> None:
    approved = _authorization(
        decision_status="approved_internal",
        decision_date="2026-08-21",
        acquisition_authorized=True,
        internal_retention_authorized=True,
    )
    approved.require_payload_authority()
    with pytest.raises(ValidationError, match="requires dated authority"):
        _authorization(
            decision_status="approved_internal",
            acquisition_authorized=True,
            internal_retention_authorized=True,
        )


def test_release_rejects_host_and_addon_shape_drift() -> None:
    common = {
        "title": "release",
        "period": "2025",
        "version_date": date(2026, 6, 12),
    }
    with pytest.raises(ValidationError, match=r"zorgcijfersdatabank\.nl"):
        GIPRelease(
            **common,
            family="farmacie",
            shape="lftgesl",
            download_url=AnyHttpUrl("https://example.test/file"),
        )
    with pytest.raises(ValidationError, match="rolling-table only"):
        GIPRelease(
            **common,
            family="addon",
            shape="lftgesl",
            download_url=AnyHttpUrl("https://www.zorgcijfersdatabank.nl/file"),
        )
    unexpected = (
        _landing()
        + b'<a class="file-download" href="/services/file/get?key=x"><h4 class="title">GIP Addon Zvw lftgesl 2025_11052026</h4></a>'
    )
    with pytest.raises(ValueError, match="unexpected Add-on release shape"):
        parse_gip_inventory(
            unexpected, authorization=_authorization(expected_release_count=28)
        )
