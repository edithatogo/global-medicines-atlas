"""Tests for the fail-closed GIP medicine inventory."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from pydantic import AnyHttpUrl, ValidationError
from scripts import acquire_gip_public as acquisition_script

from global_medicines_atlas.gip_acquisition import (
    GIPAuthorization,
    GIPRelease,
    gip_source_record_batch,
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
    authorization.require_payload_authority()
    assert authorization.decision_status == "approved_public"
    assert authorization.public_release_authorized is True
    assert authorization.external_publication_authorized is True


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
        ({"acquisition_authorized": False}, "approved public GIP"),
        ({"public_release_authorized": False}, "approved public GIP"),
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
        public_release_authorized=False,
        external_publication_authorized=False,
    )
    approved.require_payload_authority()
    with pytest.raises(ValidationError, match="requires dated authority"):
        _authorization(
            decision_status="approved_internal",
            decision_date=None,
            acquisition_authorized=True,
            internal_retention_authorized=True,
            public_release_authorized=False,
            external_publication_authorized=False,
        )


def test_pending_and_public_authority_combinations_fail_closed() -> None:
    with pytest.raises(ValidationError, match="pending GIP decision"):
        _authorization(
            decision_status="pending",
            decision_date=None,
            acquisition_authorized=False,
            internal_retention_authorized=False,
            public_release_authorized=True,
            external_publication_authorized=True,
        )
    with pytest.raises(ValidationError, match="approved public GIP"):
        _authorization(external_publication_authorized=False)


def test_release_rejects_host_and_addon_shape_drift() -> None:
    with pytest.raises(ValidationError, match=r"zorgcijfersdatabank\.nl"):
        GIPRelease(
            title="release",
            family="farmacie",
            shape="lftgesl",
            period="2025",
            version_date=date(2026, 6, 12),
            download_url=AnyHttpUrl("https://example.test/file"),
        )
    with pytest.raises(ValidationError, match="rolling-table only"):
        GIPRelease(
            title="release",
            family="addon",
            shape="lftgesl",
            period="2025",
            version_date=date(2026, 6, 12),
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


def test_source_record_projection_preserves_hash_delimited_native_strings() -> (
    None
):
    payload = (
        b"jaar#atclaatst#gebruikers#vergoeding\r\n"
        b"2025 #A10AB01 #39 #270320\r\n"
        b"2025 #A16AB02 #63 #6356792\r\n"
    )
    batch = gip_source_record_batch("nl-gipdatabank", payload, "csv")
    assert batch is not None
    assert batch.parser_identity == "nl-gip-hash-csv-utf8-v1"
    assert batch.record_id_column == "source_row_number"
    assert batch.table.column_names == [
        "jaar",
        "atclaatst",
        "gebruikers",
        "vergoeding",
        "source_row_number",
    ]
    assert batch.table["jaar"].to_pylist() == ["2025 ", "2025 "]
    assert batch.table["atclaatst"].to_pylist() == ["A10AB01 ", "A16AB02 "]
    assert batch.table["source_row_number"].to_pylist() == [1, 2]
    assert gip_source_record_batch("other", payload, "csv") is None
    assert gip_source_record_batch("nl-gipdatabank", payload, "json") is None


@pytest.mark.parametrize(
    "payload",
    [
        b"single-column\nvalue\n",
        b"jaar#jaar\n2025#2025\n",
        b"jaar#atc\n",
    ],
)
def test_source_record_projection_rejects_unusable_csv(payload: bytes) -> None:
    with pytest.raises(ValueError, match="GIP CSV"):
        gip_source_record_batch("nl-gipdatabank", payload, "csv")


@pytest.mark.timeout(120)
def test_public_runner_lands_recovers_and_archives_exact_inventory(
    tmp_path: Path,
) -> None:
    payload = b"jaar#atclaatst#gebruikers\r\n2025 #A10AB01 #39\r\n"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/algemeen/open-data-gip":
            return httpx.Response(
                200,
                content=_landing(),
                headers={"content-type": "text/html"},
            )
        if request.url.path == "/services/file/get":
            return httpx.Response(
                200,
                content=payload,
                headers={"content-type": "text/csv;charset=UTF-8"},
            )
        return httpx.Response(404)

    result = acquisition_script.acquire(
        tmp_path / "output", transport=httpx.MockTransport(handler)
    )

    assert result["release_count"] == 28
    assert result["accepted_admission_count"] == 28
    assert result["source_record_count"] == 28
    assert result["source_record_projection_count"] == 28
    assert result["recovered_acquisition_count"] == 28
    assert result["recovered_source_record_projection_count"] == 28
    assert result["source_record_parquet_pairs_byte_identical"] == 28
    assert result["archive_restore_verified"] is True
    assert result["archive_restored_payload_count"] == 28
    assert result["public_release_authorized"] is True
    assert result["external_publication_authorized"] is True
    assert Path(str(result["archive_path"])).is_file()
    manifest = json.loads(
        (tmp_path / "output/gip-public-acquisition-manifest.json").read_text()
    )
    assert all("key=" not in json.dumps(item) for item in manifest["files"])
