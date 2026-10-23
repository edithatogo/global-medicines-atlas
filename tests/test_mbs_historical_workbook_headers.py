"""Historical workbook header candidates stay identity-bound and unpromoted."""

from hashlib import sha256
from typing import Any, cast

import pytest
from test_mbs_historical_workbook_native import bound, workbook

from global_medicines_atlas.mbs_historical_workbook_headers import (
    profile_workbook_headers,
)


def test_header_candidates_bind_sheet_and_exact_text_without_mapping(tmp_path):
    path, member, native = bound(tmp_path, workbook())
    report = cast("Any", profile_workbook_headers(path, member, native))
    assert report["member_sha256"] == member.sha256
    assert report["member_path_sha256"] == member.path_sha256
    assert len(report["sheets"]) == 2
    primary = report["sheets"][0]
    assert primary["name"] == "Synthetic primary"
    assert primary["candidate_rows"] == [
        {
            "row_index": 3,
            "labels": [
                {"column": chr(65 + index), "text": label}
                for index, label in enumerate((
                    "Year",
                    "Month",
                    "Item_Number",
                    "State",
                    "Age_Range",
                    "Gender",
                    "Services",
                    "Benefits ($)",
                ))
            ],
            "disposition": "exact_contract_match",
            "contract_id": "mbs-demographic-workbook-v1",
            "column_bindings": [
                {
                    "column": chr(65 + index),
                    "native_header": label,
                    "field": field,
                    "status": "interpreted",
                }
                for index, (label, field) in enumerate(
                    zip(
                        (
                            "Year",
                            "Month",
                            "Item_Number",
                            "State",
                            "Age_Range",
                            "Gender",
                            "Services",
                            "Benefits ($)",
                        ),
                        (
                            "calendar_year_label",
                            "processing_month_label",
                            "schedule_item_identifier",
                            "state_label",
                            "age_range_label",
                            "gender_label",
                            "service_count_label",
                            "benefit_amount_label_currency_unresolved",
                        ),
                        strict=True,
                    )
                )
            ],
        }
    ]
    assert report["supported_header_mappings_present"] is True
    assert report["whole_workbook_semantics_complete"] is False
    assert report["candidate_only"] is True
    assert (
        report["header_profile_sha256"]
        == sha256(report["canonical_profile"].encode()).hexdigest()
    )


def test_wrong_member_bytes_and_path_are_rejected_before_profile(tmp_path):
    path, member, native = bound(tmp_path, workbook())
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="identity"):
        profile_workbook_headers(path, member, native)


def test_exact_group_header_uses_only_group_contract(tmp_path):
    headers = (
        "Year",
        "Month",
        "Group",
        "Sub_Group",
        "Item_Number",
        "State",
        "Services",
        "Benefits ($)",
    )
    path, member, native = bound(tmp_path, workbook(header=headers))
    report = profile_workbook_headers(path, member, native)
    primary = report["sheets"][0]
    assert (
        primary["candidate_rows"][0]["contract_id"] == "mbs-group-workbook-v1"
    )
    assert primary["candidate_rows"][0]["disposition"] == "exact_contract_match"
    assert [
        binding["field"]
        for binding in primary["candidate_rows"][0]["column_bindings"]
    ] == [
        "calendar_year_label",
        "processing_month_label",
        "schedule_group_identifier",
        "schedule_subgroup_identifier",
        "schedule_item_identifier",
        "state_label",
        "service_count_label",
        "benefit_amount_label_currency_unresolved",
    ]
