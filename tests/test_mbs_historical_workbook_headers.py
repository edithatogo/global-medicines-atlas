"""Historical workbook header candidates stay identity-bound and unpromoted."""

from dataclasses import replace
from hashlib import sha256
from typing import Any, cast

import pytest
import scripts.profile_mbs_historical_workbook_headers as profile_script
from test_mbs_historical_workbook_native import bound, workbook

from global_medicines_atlas import (
    mbs_historical_workbook_headers as header_module,
)
from global_medicines_atlas.mbs_archive_inventory import (
    DATASET,
    REVISION,
    BoundArchive,
)
from global_medicines_atlas.mbs_historical_workbook_headers import (
    profile_workbook_headers,
)

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _bound_archive() -> BoundArchive:
    return BoundArchive(
        dataset=DATASET,
        revision=REVISION,
        source_path="raw/mbs/historical.zip",
        source_sha256="a" * 64,
        source_bytes=10,
        source_id="fixture",
        acquisition_id="fixture",
        b1_sha256="b" * 64,
        b2_sha256="c" * 64,
        prior_status="structure_verified",
        prior_member_count=0,
        prior_expanded_bytes=0,
        prior_inventory_sha256="d" * 64,
    )


def test_empty_archive_profile_does_not_claim_header_labels_emitted():
    report = profile_script._aggregate("1" * 40, 4, _bound_archive(), [])

    assert report["status"] == "passed"
    assert report["workbook_count"] == 0
    assert report["profile_count"] == 0
    assert report["header_labels_emitted"] is False


def test_header_labels_emitted_tracks_observed_candidate_labels():
    profile = {"schema": "fixture"}
    profiled = [
        {
            "header_profile_sha256": "e" * 64,
            "profile": profile,
            "member_sha256": "f" * 64,
            "member_path_sha256": "0" * 64,
            "member_bytes": 1,
            "ordinal": 0,
            "sheets": [
                {
                    "candidate_rows": [
                        {
                            "labels": [{"text": "Year"}],
                            "disposition": "unresolved_candidate",
                        }
                    ],
                }
            ],
        }
    ]

    report = profile_script._aggregate("1" * 40, 0, _bound_archive(), profiled)

    assert report["header_labels_emitted"] is True


def worksheet(rows: str, *, root: str = "worksheet") -> bytes:
    return (
        f'<{root} xmlns="{MAIN}"><dimension ref="A1:H40"/>'
        f"<sheetData>{rows}</sheetData></{root}>"
    ).encode()


def row_xml(
    row_index: str,
    labels: tuple[str, ...],
    *,
    columns: tuple[str, ...] | None = None,
) -> str:
    cols = columns or tuple(
        header_module._column_name(index) for index in range(1, len(labels) + 1)
    )
    cells = "".join(
        f'<c r="{column}{row_index}" t="inlineStr"><is><t>{label}</t></is></c>'
        for column, label in zip(cols, labels, strict=True)
    )
    return f'<row r="{row_index}">{cells}</row>'


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


def test_workbook_identity_guards_reject_unbound_metadata(tmp_path):
    path, member, native = bound(tmp_path, workbook())
    with pytest.raises(ValueError, match="identity or bound"):
        profile_workbook_headers(path, replace(member, suffix=".xls"), native)
    with pytest.raises(ValueError, match="identity or bound"):
        profile_workbook_headers(path, member, "other.xlsx")
    with pytest.raises(ValueError, match="identity or bound"):
        profile_workbook_headers(path, replace(member, byte_count=True), native)
    path.unlink()
    path.symlink_to(tmp_path / "missing-target.xlsx")
    with pytest.raises(ValueError, match="identity or bound"):
        profile_workbook_headers(path, member, native)


def test_sheet_profile_rejects_invalid_row_and_parent_and_root():
    with pytest.raises(ValueError, match="row index"):
        header_module._sheet_profile(worksheet('<row r="x"/>'), ())
    with pytest.raises(ValueError, match="row parent"):
        header_module._sheet_profile(
            worksheet('<other><row r="1"/></other>'), ()
        )
    with pytest.raises(ValueError, match="root differs"):
        header_module._sheet_profile(worksheet("", root="notWorksheet"), ())


def test_sheet_profile_stops_at_bound_and_keeps_other_header_rows_unresolved():
    labels = ("Title", "Description")
    dimension, rows = header_module._sheet_profile(
        worksheet(row_xml("21", labels) + row_xml("22", labels)), ()
    )
    assert dimension == "A1:H40"
    assert rows == []
    dimension, rows = header_module._sheet_profile(
        worksheet(row_xml("2", labels)), ()
    )
    assert dimension == "A1:H40"
    assert rows[0]["disposition"] == "unresolved_candidate"


@pytest.mark.parametrize(
    "cells",
    [
        '<c r="A1" t="str"><f>1</f><v>cached</v></c><c r="B1" t="inlineStr"><is><t>Other</t></is></c>',
        '<c r="A1"><v>12</v></c><c r="B1" t="inlineStr"><is><t>Other</t></is></c>',
        '<c r="A1" t="inlineStr"><is><t>Same</t></is></c><c r="B1" t="inlineStr"><is><t>Same</t></is></c>',
    ],
)
def test_sheet_profile_does_not_promote_formula_numeric_or_duplicate_rows(
    cells,
):
    _, rows = header_module._sheet_profile(
        worksheet(f'<row r="1">{cells}</row>'), ()
    )
    assert rows == []


def test_contract_requires_contiguous_columns_and_caps_candidate_width():
    headers = (
        "Year",
        "Month",
        "Item_Number",
        "State",
        "Age_Range",
        "Gender",
        "Services",
        "Benefits ($)",
    )
    _, rows = header_module._sheet_profile(
        worksheet(
            row_xml(
                "3", headers, columns=("A", "C", "D", "E", "F", "G", "H", "I")
            )
        ),
        (),
    )
    assert rows[0]["disposition"] == "unresolved_candidate"
    too_many = tuple(f"Label{index}" for index in range(65))
    columns = tuple(header_module._column_name(index) for index in range(1, 66))
    _, rows = header_module._sheet_profile(
        worksheet(row_xml("1", too_many, columns=columns)), ()
    )
    assert rows == []
    assert header_module._column_name(27) == "AA"
