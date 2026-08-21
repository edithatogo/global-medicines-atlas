"""Fail-closed tests for FDA GSRS/UNII acquisition preflight."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError

from global_medicines_atlas.gsrs_acquisition import (
    GSRSAuthorization,
    parse_gsrs_release_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT / "quality/qualifications/gsrs-unii-acquisition-authorization.json"
)
BASE_URL = AnyHttpUrl("https://precision.fda.gov/uniisearch/")


def _authorization(**updates: object) -> GSRSAuthorization:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw.update(updates)
    return GSRSAuthorization.model_validate(raw)


def _inventory(count: int = 68) -> bytes:
    dates = [date(2014, 1, 25)]
    dates.extend(
        date(2014, 1, 25) + timedelta(days=index)
        for index in range(1, count - 1)
    )
    dates.append(date(2026, 8, 4))
    links: list[str] = []
    for item in dates:
        compact = item.strftime("%Y%m%d")
        release_path = f"archive/{item.isoformat()}"
        links.extend((
            f'<a href="{release_path}/UNII_Data_{compact}.zip">Data</a>',
            f'<a href="{release_path}/UNIIs_{compact}.zip">Names</a>',
        ))
    return "".join(links).encode()


def _inventory_authorization(payload: bytes) -> GSRSAuthorization:
    text = payload.decode()
    dates = sorted(set(re.findall(r"archive/([0-9-]{10})/", text)))
    digest = sha256(("\n".join(dates) + "\n").encode()).hexdigest()
    return _authorization(expected_release_dates_sha256=digest)


def test_pending_authorization_cannot_fetch_payloads() -> None:
    authorization = _authorization()
    assert authorization.decision_status == "pending"
    assert authorization.acquisition_authorized is False
    with pytest.raises(PermissionError, match="decision is pending"):
        authorization.require_payload_authority()


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"acquisition_authorized": True}, "pending GSRS decision"),
        ({"internal_retention_authorized": True}, "pending GSRS decision"),
        ({"public_release_authorized": True}, "separately gated"),
        ({"expected_release_count": 67}, "all 68 releases"),
        (
            {"archive_index_url": "https://example.test/archive"},
            "precision.fda.gov",
        ),
    ],
)
def test_authorization_rejects_scope_widening(
    updates: dict[str, object], message: str
) -> None:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw.update(updates)
    with pytest.raises(ValidationError, match=message):
        GSRSAuthorization.model_validate(raw)


def test_approved_internal_authority_requires_date_and_both_flags() -> None:
    approved = _authorization(
        decision_status="approved_internal",
        decision_date="2026-08-21",
        acquisition_authorized=True,
        internal_retention_authorized=True,
    )
    approved.require_payload_authority()

    with pytest.raises(ValidationError, match="dated authority"):
        _authorization(
            decision_status="approved_internal",
            acquisition_authorized=True,
            internal_retention_authorized=True,
        )


def test_inventory_requires_all_paired_releases() -> None:
    payload = _inventory()
    authorization = _inventory_authorization(payload)
    inventory = parse_gsrs_release_inventory(
        payload, base_url=BASE_URL, authorization=authorization
    )
    assert inventory.release_count == 68
    assert inventory.first_release == date(2014, 1, 25)
    assert inventory.last_release == date(2026, 8, 4)
    assert str(inventory.releases[0].data_url).startswith(
        "https://precision.fda.gov/uniisearch/archive/"
    )

    with pytest.raises(ValueError, match="inventories differ"):
        parse_gsrs_release_inventory(
            _inventory().replace(b"UNIIs_20260804.zip", b"missing.zip"),
            base_url=BASE_URL,
            authorization=authorization,
        )
    with pytest.raises(ValueError, match="inventory drifted"):
        parse_gsrs_release_inventory(
            _inventory(67),
            base_url=BASE_URL,
            authorization=authorization,
        )

    with pytest.raises(ValueError, match="inventory drifted"):
        parse_gsrs_release_inventory(
            b"<html><body>No releases</body></html>",
            base_url=BASE_URL,
            authorization=authorization,
        )
