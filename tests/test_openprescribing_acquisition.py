"""Tests for the OpenPrescribing fail-closed acquisition contract."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.openprescribing_acquisition import (
    OpenPrescribingAuthorization,
)

AUTHORIZATION = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/openprescribing-acquisition-authorization.json"
)


def _raw() -> dict[str, object]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def _authorization(**updates: object) -> OpenPrescribingAuthorization:
    raw = _raw()
    raw.update(updates)
    return OpenPrescribingAuthorization.model_validate(raw)


def test_pending_contract_locks_documented_api_surface() -> None:
    authorization = _authorization()
    assert [item.name for item in authorization.endpoints] == [
        "spending",
        "spending_by_org",
        "bnf_code",
        "org_code",
        "org_details",
        "org_location",
    ]
    assert authorization.archive_strategy == "receipt_bound_partitioned_queries"
    with pytest.raises(PermissionError, match="decision is pending"):
        authorization.require_payload_authority()
    with pytest.raises(PermissionError, match="decision is pending"):
        authorization.require_reproducible_partition(date_partition=None)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"acquisition_authorized": True}, "pending OpenPrescribing decision"),
        ({"public_release_authorized": True}, "separately gated"),
        ({"documentation_url": "https://example.test/api"}, "official service"),
        ({"upstream_monthly_source_url": "https://example.test/epd"}, "NHSBSA"),
    ],
)
def test_authorization_rejects_scope_widening(
    updates: dict[str, object], message: str
) -> None:
    raw = _raw()
    raw.update(updates)
    with pytest.raises(ValidationError, match=message):
        OpenPrescribingAuthorization.model_validate(raw)


def test_endpoint_inventory_cannot_drift() -> None:
    raw = _raw()
    raw["endpoints"] = list(raw["endpoints"])[:-1]  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="all six API identities"):
        OpenPrescribingAuthorization.model_validate(raw)
    raw = _raw()
    endpoints = list(raw["endpoints"])  # type: ignore[arg-type]
    endpoints[0], endpoints[1] = endpoints[1], endpoints[0]
    raw["endpoints"] = endpoints
    with pytest.raises(ValidationError, match="identity sequence drifted"):
        OpenPrescribingAuthorization.model_validate(raw)


@pytest.mark.parametrize(
    ("update", "message"),
    [
        (
            {"url": "https://example.test/api/1.0/spending/"},
            "openprescribing.net",
        ),
        ({"url": "https://openprescribing.net/api/2.0/spending/"}, "API v1.0"),
        ({"formats": ["csv"]}, "retain JSON"),
        ({"rolling_window": False}, "rolling-window semantics"),
    ],
)
def test_endpoint_rejects_host_version_format_and_window_drift(
    update: dict[str, object], message: str
) -> None:
    raw = _raw()
    endpoints = list(raw["endpoints"])  # type: ignore[arg-type]
    endpoints[0] = {**endpoints[0], **update}
    raw["endpoints"] = endpoints
    with pytest.raises(ValidationError, match=message):
        OpenPrescribingAuthorization.model_validate(raw)


def test_approved_internal_capture_requires_date_and_partition() -> None:
    approved = _authorization(
        decision_status="approved_internal",
        decision_date="2026-08-21",
        acquisition_authorized=True,
        internal_retention_authorized=True,
    )
    approved.require_payload_authority()
    with pytest.raises(ValueError, match="explicit date partition"):
        approved.require_reproducible_partition(date_partition=None)
    approved.require_reproducible_partition(date_partition=date(2026, 1, 1))
    with pytest.raises(ValidationError, match="requires dated authority"):
        _authorization(
            decision_status="approved_internal",
            acquisition_authorized=True,
            internal_retention_authorized=True,
        )
