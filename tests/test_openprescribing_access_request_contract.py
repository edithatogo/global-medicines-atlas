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


def test_access_request_and_plan_match_sent_request_evidence() -> None:
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

    assert "**Status:** sent 2026-09-28" in request
    sent = [
        r
        for r in records
        if r.get("kind") == "openprescribing_supported_access_request_sent"
    ]
    assert len(sent) == 1
    assert sent[0]["status"] == "sent_awaiting_provider_response"
    assert sent[0]["source_payloads_attached"] is False
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/provider-outreach-receipts-20260929.json"
        ).read_text(encoding="utf-8")
    )
    message = next(
        m for m in receipt["messages"] if m["source_id"] == "gb-openprescribing"
    )
    assert message["acknowledgement"]["kind"] == (
        "automatic_receipt_acknowledgement"
    )
    assert message["acknowledgement"]["substantive_guidance"] is False
    assert (
        receipt["verification"]["substantive_provider_responses_observed"]
        is False
    )
    assert "provider-outreach-receipts-20260929.json" in request
    assert "feedback@openprescribing.net" in request
    assert "will not attempt to solve the" in request
    assert "Send the request to `feedback@openprescribing.net`" in plan
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
