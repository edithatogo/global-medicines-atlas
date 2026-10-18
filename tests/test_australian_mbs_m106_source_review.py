"""Keep M-106 patient measures distinct from item service counts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).parents[1]
REVIEW = (
    ROOT / "quality/qualifications/"
    "australian-mbs-item-demographic-source-review-20260929.json"
)
CURRENT_ITEM_DATA = (
    ROOT / "quality/qualifications/"
    "australian-mbs-current-item-data-metadata-20260930.json"
)
PATIENT_SOURCE_METADATA = (
    ROOT / "quality/qualifications/"
    "australian-mbs-m106-patient-source-metadata-20261016.json"
)
METADATA_RECHECK = (
    ROOT / "quality/qualifications/"
    "australian-mbs-m106-source-metadata-recheck-20261017.json"
)
ANNUAL_WORKBOOK_HEAD = (
    ROOT / "quality/qualifications/"
    "australian-mbs-m106-annual-workbook-head-readback-20261019.json"
)
ANNUAL_WORKBOOK_HEAD_SCHEMA = (
    ROOT / "schemas/australian-mbs-m106-annual-workbook-head-readback-v1.json"
)
AUSTRALIAN_TRACK_EVIDENCE = (
    ROOT / "conductor/tracks/australian_health_source_consolidation_20260829/"
    "evidence.jsonl"
)


def test_item_demographic_candidate_does_not_qualify_patient_denominator() -> (
    None
):
    review = cast("dict[str, Any]", json.loads(REVIEW.read_text()))
    qualification = cast("dict[str, Any]", review["qualification"])
    fields = review["metadata_observations"]["published_fields"]

    assert "Services" in fields
    assert "Benefit" in fields
    assert not any("patient" in field.lower() for field in fields)
    assert qualification["item_level_service_statistics_candidate"] is True
    assert qualification["distinct_patient_count_field_observed"] is False
    assert qualification["patient_denominator_qualified"] is False
    assert qualification["source_bytes_acquired"] is False
    assert qualification["interactive_report_reuse_terms_verified"] is False

    inquiry = (
        ROOT
        / "conductor/tracks/australian_health_source_consolidation_20260829/"
        "m106-item-patient-count-inquiry.md"
    ).read_text(encoding="utf-8")
    assert "**Status:** sent 2026-09-28" in inquiry
    assert "not requesting a custom or restricted extraction" in inquiry
    assert "patient-level" in inquiry
    outreach = cast(
        "dict[str, Any]",
        json.loads(
            (
                ROOT
                / "quality/qualifications/provider-outreach-receipts-20260929.json"
            ).read_text(encoding="utf-8")
        ),
    )
    message = next(
        item
        for item in outreach["messages"]
        if item["source_id"] == "au-services-australia-mbs-item-demographics"
    )
    assert message["gmail_message_id"] == "1a0e93bc557578ea"
    assert message["recipient"] == "statistics@servicesaustralia.gov.au"
    assert message["attachment_count"] == 0


def test_current_item_data_metadata_is_not_patient_or_rights_qualification() -> (
    None
):
    receipt = cast("dict[str, Any]", json.loads(CURRENT_ITEM_DATA.read_text()))
    fields = receipt["metadata_observations"]["fields"]
    qualification = cast("dict[str, Any]", receipt["qualification"])

    assert receipt["resource"]["resource_id"] == (
        "dbdde899-76ab-4d8d-a05a-46b51088b49e"
    )
    assert receipt["metadata_observations"]["metadata_query_url"].endswith(
        "resource_id=dbdde899-76ab-4d8d-a05a-46b51088b49e&limit=0"
    )
    assert receipt["metadata_observations"]["record_count"] == 26391
    assert (
        receipt["metadata_observations"]["records_returned_by_metadata_query"]
        == 0
    )
    assert {field["id"] for field in fields} == {
        "_id",
        "Year",
        "Month of Processing",
        "Group",
        "Sub-Group",
        "Item Number",
        "State",
        "Services",
        "Benefit",
    }
    assert not any("patient" in field["id"].lower() for field in fields)
    assert receipt["source_bytes_accessed"] is False
    assert receipt["source_rows_accessed"] is False
    assert receipt["project_rights_decision_made"] is False
    assert qualification["patient_denominator_qualified"] is False
    assert qualification["acquisition_authorized"] is False
    assert qualification["public_license_notice"] == (
        "Creative Commons Attribution 3.0 Australia"
    )
    digest = receipt["digest"]
    canonical = {
        key: value for key, value in receipt.items() if key != "digest"
    }
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    assert digest["value"] == hashlib.sha256(encoded).hexdigest()


def test_department_patient_metadata_remains_candidate_only() -> None:
    receipt = cast(
        "dict[str, Any]", json.loads(PATIENT_SOURCE_METADATA.read_text())
    )
    assessment = cast("dict[str, Any]", receipt["assessment"])
    resources = cast(
        "list[dict[str, Any]]",
        receipt["source_metadata_review"]["candidate_resources"],
    )

    assert len(resources) == 2
    assert all(item["payload_acquired"] is False for item in resources)
    assert assessment["status"] == "candidate_metadata_only"
    assert (
        assessment["establishes_full_mbs_distinct_patient_denominator"] is False
    )
    assert assessment["establishes_item_level_distinct_patient_counts"] is False
    assert assessment["source_owner_clarification_received"] is False
    assert assessment["source_specific_maintainer_rights_decision"] is False
    assert assessment["acquisition_authorized"] is False
    assert assessment["m106_acceptance"] is False
    reference = receipt["source_metadata_review"][
        "authoritative_measurement_context"
    ]["reference_document_access"]
    assert reference["content_reviewed_via_web_reader"] is True
    assert reference["pages_reviewed"] == [91, 92]
    assert reference["pdf_saved_locally"] is False

    inquiry = cast("dict[str, Any]", receipt["source_owner_inquiry"])
    assert inquiry["recipient"] == "enquiries@health.gov.au"
    assert inquiry["gmail_message_id"] == "1a144fb6ffd7c3cd"
    assert inquiry["state"] == "sent_awaiting_source_owner_response"
    assert inquiry["attachments"] == 0
    assert inquiry["patient_data_requested"] is False
    assert inquiry["rights_decision_made"] is False
    body = (
        ROOT
        / "conductor/tracks/australian_health_source_consolidation_20260829/"
        "m106-department-patient-denominator-inquiry.md"
    ).read_text(encoding="utf-8")
    assert "full MBS population or a defined service/item cohort" in body
    assert "coverage and suppression rules" in body
    assert "access, attribution, retention and redistribution terms" in body
    assert "custom extraction, patient-level records, restricted" in body


def test_annual_patient_candidate_uses_existing_scoped_authorization() -> None:
    receipt = cast("dict[str, Any]", json.loads(METADATA_RECHECK.read_text()))
    boundaries = cast("dict[str, Any]", receipt["boundaries"])
    authorization = cast(
        "dict[str, Any]", boundaries["existing_annual_series_authorization"]
    )
    provider = cast(
        "dict[str, Any]", receipt["provider_correspondence_readback"]
    )

    assert authorization["qualification"].endswith(
        "australian-mbs-utilisation-publication-authorization.json"
    )
    assert authorization["source_id"] == "au-health-medicare-statistics"
    assert authorization["category"] == (
        "medicare_annual_statistics_state_territory"
    )
    assert (
        authorization["covers_acquisition_and_publication_within_scope"] is True
    )
    assert boundaries["acquisition_authorized_within_existing_scope"] is True
    assert boundaries["new_rights_decision_required_for_annual_series"] is False
    assert boundaries["acquisition_preconditions_satisfied"] is False
    assert boundaries["acquisition_performed"] is False
    assert boundaries["m106_accepted"] is False
    assert provider["substantive_source_owner_clarification_found"] is False
    assert provider["new_rights_decision_required_for_annual_series"] is False
    assert provider["existing_annual_series_authorization_applies"] is True


def test_annual_patient_readback_preserves_pending_source_and_rights_gates() -> (
    None
):
    records = [
        cast("dict[str, Any]", json.loads(line))
        for line in AUSTRALIAN_TRACK_EVIDENCE.read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    receipt = next(
        record
        for record in records
        if record.get("kind")
        == "m106_annual_patient_measure_and_owner_followup"
    )
    metadata = cast("dict[str, Any]", receipt["official_metadata"])
    contact = cast("dict[str, Any]", receipt["contact"])
    boundaries = cast("dict[str, Any]", receipt["boundaries"])

    assert "patients" in metadata["page_claim"]
    assert any("do not specify" in item for item in metadata["observations"])
    assert contact["sent_message_id"] == "1a14abd12b459daf"
    assert contact["substantive_response_received"] is False
    assert contact["auto_replies"][0]["meaning"].startswith("receipt_only")
    assert boundaries["source_bytes_or_rows_read"] is False
    assert boundaries["acquisition_performed"] is False
    assert boundaries["source_rights_changed"] is False
    assert boundaries["distinct_patient_denominator_qualified"] is False
    assert boundaries["m106_accepted"] is False


def test_annual_workbook_transport_readback_keeps_identity_and_rights_gates() -> (
    None
):
    receipt = cast(
        "dict[str, Any]", json.loads(ANNUAL_WORKBOOK_HEAD.read_text())
    )
    schema = cast(
        "dict[str, Any]",
        json.loads(ANNUAL_WORKBOOK_HEAD_SCHEMA.read_text()),
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        receipt
    )

    page = cast("dict[str, Any]", receipt["official_page"])
    head = cast("dict[str, Any]", receipt["attachment_head"])
    owner = cast("dict[str, Any]", receipt["owner_clarification"])
    boundaries = cast("dict[str, Any]", receipt["boundaries"])
    assert page["described_period"] == "2009-10 through 2025-26"
    assert page["attachment_filename_period"] == "2009-10 through 2024-25"
    assert page["response_bytes"] == 34921
    assert len(page["response_sha256"]) == 64
    assert head["method"] == "HEAD"
    assert head["http_status"] == 200
    assert head["content_length"] == 1058479
    assert head["response_body_bytes"] == 0
    assert owner["sent_message_id"] == "1a14abd12b459daf"
    assert owner["substantive_response_received"] is False
    assert boundaries["workbook_body_requested"] is False
    assert boundaries["workbook_payload_bytes_read"] == 0
    assert boundaries["source_rights_changed"] is False
    assert boundaries["distinct_patient_denominator_qualified"] is False
    assert boundaries["m106_accepted"] is False

    invalid = dict(receipt)
    invalid_head = dict(head)
    invalid_head["response_body_bytes"] = 1
    invalid["attachment_head"] = invalid_head
    with pytest.raises(ValidationError):
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(
            invalid
        )
