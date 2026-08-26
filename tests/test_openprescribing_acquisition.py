"""Tests for the OpenPrescribing fail-closed acquisition contract."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from scripts import probe_openprescribing_availability as probe_script

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


def test_approved_public_contract_locks_documented_api_surface() -> None:
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
    assert authorization.decision_status == "approved_public"
    assert authorization.public_release_authorized is True
    assert authorization.external_publication_authorized is True
    authorization.require_payload_authority()
    authorization.require_publication_authority()
    with pytest.raises(ValueError, match="explicit date partition"):
        authorization.require_reproducible_partition(date_partition=None)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"acquisition_authorized": False}, "approved public OpenPrescribing"),
        (
            {"public_release_authorized": False},
            "approved public OpenPrescribing",
        ),
        (
            {"external_publication_authorized": False},
            "approved public OpenPrescribing",
        ),
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
        public_release_authorized=False,
        external_publication_authorized=False,
    )
    approved.require_payload_authority()
    with pytest.raises(ValueError, match="explicit date partition"):
        approved.require_reproducible_partition(date_partition=None)
    approved.require_reproducible_partition(date_partition=date(2026, 1, 1))
    with pytest.raises(ValidationError, match="requires dated authority"):
        _authorization(
            decision_status="approved_internal",
            decision_date=None,
            acquisition_authorized=True,
            internal_retention_authorized=True,
            public_release_authorized=False,
            external_publication_authorized=False,
        )


def test_pending_and_internal_decisions_keep_publication_fail_closed() -> None:
    pending = _authorization(
        decision_status="pending",
        decision_date=None,
        acquisition_authorized=False,
        internal_retention_authorized=False,
        public_release_authorized=False,
        external_publication_authorized=False,
    )
    with pytest.raises(PermissionError, match="decision is pending"):
        pending.require_payload_authority()
    with pytest.raises(PermissionError, match="publication is not authorized"):
        pending.require_publication_authority()

    internal = _authorization(
        decision_status="approved_internal",
        acquisition_authorized=True,
        internal_retention_authorized=True,
        public_release_authorized=False,
        external_publication_authorized=False,
    )
    internal.require_payload_authority()
    with pytest.raises(PermissionError, match="publication is not authorized"):
        internal.require_publication_authority()


def test_availability_probe_is_bounded_and_does_not_retain_payloads() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            403,
            headers={
                "content-type": "text/html; charset=UTF-8",
                "server": "cloudflare",
                "cf-mitigated": "challenge",
            },
            content=b"challenge bytes that must not enter the receipt",
        )

    receipt = probe_script.probe(
        date(2026, 6, 1), transport=httpx.MockTransport(handler)
    )
    assert len(requests) == 6
    assert receipt["endpoint_count"] == 6
    assert receipt["payload_bytes_retained"] is False
    assert receipt["payloads_acquired"] is False
    assert receipt["external_publication_performed"] is False
    assert receipt["challenge_bodies_retained"] is False
    observations = receipt["observations"]
    assert isinstance(observations, list)
    assert all(
        item["availability"] == "cloudflare_challenge_from_current_environment"
        for item in observations
    )
    assert all("content" not in item for item in observations)
    assert requests[0].url.params["date"] == "2026-06-01"
    assert "date" not in requests[-1].url.params
