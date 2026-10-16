"""Keep M-106 patient measures distinct from item service counts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

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
