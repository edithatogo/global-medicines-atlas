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
