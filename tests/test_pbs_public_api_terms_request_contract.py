"""Contract for the sent PBS public API terms request and its limits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
TRACK = ROOT / "conductor/tracks/australian_benefits_silver_gold_20260829"
PREFLIGHT = (
    ROOT
    / "quality/qualifications/australian-pbs-api-public-access-preflight-20260929.json"
)


def test_pbs_terms_request_receipt_is_reconciled_without_rights_promotion() -> (
    None
):
    request = (TRACK / "pbs-public-api-terms-request.md").read_text(
        encoding="utf-8"
    )
    preflight = cast("dict[str, Any]", json.loads(PREFLIGHT.read_text()))

    assert "**Status:** sent 2026-09-28" in request
    receipt = cast(
        "dict[str, Any]",
        json.loads(
            (
                ROOT
                / "quality/qualifications/provider-outreach-receipts-20260929.json"
            ).read_text()
        ),
    )
    pbs_message = next(
        m for m in receipt["messages"] if m["source_id"] == "au-pbs-api"
    )
    assert pbs_message["state"] == "sent_awaiting_provider_response"
    assert pbs_message["acknowledgement"]["kind"] == (
        "automatic_receipt_acknowledgement"
    )
    assert pbs_message["acknowledgement"]["substantive_guidance"] is False
    assert pbs_message["rights_decision_made"] is False
    assert pbs_message["source_payloads_attached"] is False
    assert "HPP.Support@Health.gov.au" in request
    assert "will not access" in request
    assert "embargo data" in request
    assert preflight["source_id"] == "au-pbs-api"
    assert preflight["payload_requests_made"] is False
    assert preflight["embargo_access_attempted"] is False
    assert preflight["contact"]["message_sent"] is True
    assert (
        preflight["contact"]["gmail_message_id"]
        == pbs_message["gmail_message_id"]
    )
    assert (
        preflight["contact"]["acknowledgement"]["gmail_message_id"]
        == (pbs_message["acknowledgement"]["gmail_message_id"])
    )
    assert (
        preflight["contact"]["acknowledgement"]["substantive_guidance_received"]
        is False
    )


def test_pbs_public_access_does_not_promote_rights_or_domain_acceptance() -> (
    None
):
    preflight = cast("dict[str, Any]", json.loads(PREFLIGHT.read_text()))
    observed = cast("dict[str, Any]", preflight["observed_public_api_contract"])
    rights = cast("dict[str, Any]", preflight["rights_observation"])

    assert observed["public_api_available_without_login"] is True
    assert observed["history_months"] == 12
    assert observed["shared_rate_limit_seconds"] == 20
    assert observed["data_retention_period_specified"] is False
    assert observed["external_redistribution_terms_specified"] is False
    assert (
        "own systems or databases"
        in observed["documented_local_copy_operation"]
    )
    assert rights["explicit_public_api_reuse_licence_identified"] is False
    assert rights["internal_long_term_retention_authorized"] is False
    assert rights["source_byte_redistribution_authorized"] is False
    assert rights["derived_data_publication_authorized"] is False
    assert "expressly supports downloading" in rights["interpretation"]
    assert (
        "does not resolve the project's B2 retention period"
        in rights["interpretation"]
    )
    assert "does not change acquisition authorization" in preflight["boundary"]


def test_pbs_rights_reconciliation_is_appended_after_existing_evidence_tail() -> (
    None
):
    evidence = [
        cast("dict[str, Any]", json.loads(line))
        for line in (TRACK / "evidence.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    positions = {
        row["kind"]: index
        for index, row in enumerate(evidence)
        if row.get("kind")
        in {
            "mbs_workbook_official_date_documentation_review",
            "pbs_terms_preflight_send_receipt_reconciled",
        }
    }

    assert (
        positions["mbs_workbook_official_date_documentation_review"]
        < positions["pbs_terms_preflight_send_receipt_reconciled"]
    )


def test_mbs_agency_inquiry_is_sent_without_claiming_an_approved_endpoint() -> (
    None
):
    receipt = cast(
        "dict[str, Any]",
        json.loads(
            (
                ROOT
                / "quality/qualifications/provider-outreach-receipts-20260929.json"
            ).read_text()
        ),
    )
    message = next(
        item
        for item in receipt["messages"]
        if item["source_id"] == "au-mbs-utilisation"
    )
    acceptance = (
        ROOT / "docs/qualification/australian-health-federation-acceptance.md"
    ).read_text()

    assert message["state"] == "sent_awaiting_agency_response"
    assert message["acknowledgement"]["kind"] == (
        "automatic_receipt_acknowledgement"
    )
    assert message["acknowledgement"]["substantive_guidance"] is False
    assert message["recipient"] == "enquiries@health.gov.au"
    assert message["workbook_bytes_attached"] is False
    assert message["approved_endpoint_identified"] is False
    assert "| M-107 historical snapshots | Blocked |" in acceptance
