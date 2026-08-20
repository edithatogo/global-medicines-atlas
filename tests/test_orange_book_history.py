"""Fail-closed contracts for FDA Orange Book historical acquisition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from global_medicines_atlas.orange_book_history import (
    OrangeBookHistoricalPlan,
    build_metadata_probe_requests,
    build_payload_requests,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "quality/qualifications/orange-book-historical-plan.json"


def _plan_payload() -> dict[str, object]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def test_committed_plan_records_bounded_official_surface_without_authority():
    plan = OrangeBookHistoricalPlan.model_validate_json(PLAN.read_bytes())

    assert plan.source_id == "us-fda-orange-book"
    assert plan.prompt_id == 16
    assert plan.observed_release_link_count == 137
    assert plan.observed_release_range == "2015-01 through 2026-07"
    assert plan.historical_inventory_complete is False
    assert plan.acquisition_authorized is False
    assert plan.internal_retention_authorized is False
    assert plan.public_release_authorized is False
    assert plan.external_publication_authorized is False
    assert {item.release_kind for item in plan.surfaces} == {
        "current_structured_zip",
        "current_annual_edition",
        "current_cumulative_supplement",
        "monthly_additions_deletions_index",
        "legacy_fda_archive_index",
    }


def test_plan_rejects_non_official_hosts():
    payload = _plan_payload()
    surfaces = cast("list[object]", payload["surfaces"])
    first = cast("dict[str, object]", surfaces[0])
    first["url"] = "https://example.com/orange-book.zip"

    with pytest.raises(ValidationError):
        OrangeBookHistoricalPlan.model_validate(payload)


def test_plan_rejects_archive_host_for_non_archive_surface():
    payload = _plan_payload()
    surfaces = cast("list[object]", payload["surfaces"])
    first = cast("dict[str, object]", surfaces[0])
    first["url"] = "https://wayback.archive-it.org/7993/not-the-fda-index"

    with pytest.raises(ValidationError, match="only for the FDA archive"):
        OrangeBookHistoricalPlan.model_validate(payload)


def test_plan_rejects_false_historical_completeness():
    payload = _plan_payload()
    payload["historical_inventory_complete"] = True

    with pytest.raises(ValidationError, match="cannot claim complete history"):
        OrangeBookHistoricalPlan.model_validate(payload)


def test_plan_rejects_non_fda_documentation():
    payload = _plan_payload()
    payload["official_documentation"] = ["https://example.com/orange-book"]

    with pytest.raises(ValidationError, match="official FDA host"):
        OrangeBookHistoricalPlan.model_validate(payload)


@pytest.mark.parametrize(
    "field", ["public_release_authorized", "external_publication_authorized"]
)
def test_plan_rejects_publication_authority(field: str):
    payload = _plan_payload()
    payload[field] = True

    with pytest.raises(ValidationError, match="cannot authorize publication"):
        OrangeBookHistoricalPlan.model_validate(payload)


def test_plan_rejects_retention_without_acquisition_authority():
    payload = _plan_payload()
    payload["internal_retention_authorized"] = True

    with pytest.raises(ValidationError, match="retention cannot precede"):
        OrangeBookHistoricalPlan.model_validate(payload)


def test_plan_rejects_duplicate_or_missing_release_surfaces():
    payload = _plan_payload()
    surfaces = cast("list[object]", payload["surfaces"])
    surfaces[-1] = surfaces[0]
    with pytest.raises(ValidationError, match="must be unique"):
        OrangeBookHistoricalPlan.model_validate(payload)

    payload = _plan_payload()
    surfaces = cast("list[object]", payload["surfaces"])
    payload["surfaces"] = surfaces[:-1]
    with pytest.raises(ValidationError, match="all five observed surfaces"):
        OrangeBookHistoricalPlan.model_validate(payload)


def test_plan_rejects_authority_without_internal_retention_and_decision():
    payload = _plan_payload()
    payload["acquisition_authorized"] = True

    with pytest.raises(ValidationError, match="maintainer decision"):
        OrangeBookHistoricalPlan.model_validate(payload)


def test_metadata_planning_uses_head_only_and_zero_response_body():
    plan = OrangeBookHistoricalPlan.model_validate_json(PLAN.read_bytes())

    probes = build_metadata_probe_requests(plan)

    assert len(probes) == len(plan.surfaces)
    assert {request.method for request in probes} == {"HEAD"}
    assert {request.max_response_body_bytes for request in probes} == {0}
    assert all(
        request.url.host in {"www.fda.gov", "wayback.archive-it.org"}
        for request in probes
    )


def test_payload_requests_fail_closed_before_maintainer_authorization():
    plan = OrangeBookHistoricalPlan.model_validate_json(PLAN.read_bytes())

    with pytest.raises(PermissionError, match="maintainer authorization"):
        build_payload_requests(plan)


def test_authorization_alone_cannot_bypass_incomplete_release_inventory():
    payload = _plan_payload()
    payload["acquisition_authorized"] = True
    payload["internal_retention_authorized"] = True
    payload["maintainer_decision"] = "Test-only explicit authorization."
    plan = OrangeBookHistoricalPlan.model_validate(payload)

    with pytest.raises(PermissionError, match="complete release inventory"):
        build_payload_requests(plan)
