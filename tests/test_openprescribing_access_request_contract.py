"""Contracts for the prepared OpenPrescribing access request."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
TRACK = ROOT / "conductor" / "tracks" / "bronze_medallion_completion_20260819"


def _evidence_records() -> list[dict[str, Any]]:
    return [
        cast("dict[str, Any]", json.loads(line))
        for line in (TRACK / "evidence.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]


def test_access_request_and_plan_match_prepared_not_sent_evidence() -> None:
    request = (TRACK / "openprescribing-access-request.md").read_text(
        encoding="utf-8"
    )
    plan = (TRACK / "plan.md").read_text(encoding="utf-8")
    records = _evidence_records()
    prepared = [
        record
        for record in records
        if record.get("kind")
        == "openprescribing_supported_access_request_prepared"
    ]

    assert len(prepared) == 1
    record = prepared[0]
    assert record["status"] == "draft_prepared_not_sent"
    assert record["request_draft"] == (
        "conductor/tracks/bronze_medallion_completion_20260819/"
        "openprescribing-access-request.md"
    )
    assert record["scope"]["message_sent"] is False
    assert record["scope"]["credentials_requested_or_created"] is False
    assert record["scope"]["challenge_workaround_attempted"] is False

    assert "**Status:** prepared, not sent." in request
    assert "will not attempt to solve the" in request
    assert (
        "prepare an unsent request for a supported machine-access path" in plan
    )
    assert "Obtain provider guidance for automated access" in plan


def test_access_request_validation_names_its_direct_contract() -> None:
    records = _evidence_records()
    validation = [
        record
        for record in records
        if record.get("kind")
        == "openprescribing_access_request_contract_validation"
    ]

    assert len(validation) == 1
    assert validation[0]["status"] == "local_pass_protected_ci_pending"
    assert validation[0]["validation"]["artifact_contract_test"] == "passed"


def test_access_request_merge_evidence_preserves_external_boundary() -> None:
    records = _evidence_records()
    merged = [
        record
        for record in records
        if record.get("kind")
        == "openprescribing_access_request_validation_merged"
    ]

    assert len(merged) == 1
    record = merged[0]
    assert record["status"] == "merged_protected_ci_passed"
    assert record["checks"]["hosted_total"] == 37
    assert record["checks"]["hosted_success"] == 37
    assert record["boundary"].startswith(
        "Hosted validation confirms the unsent request"
    )
