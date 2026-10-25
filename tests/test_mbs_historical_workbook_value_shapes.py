"""Value shapes remain source-native diagnostics with no emitted values."""

import json
from copy import deepcopy

import pytest
from test_mbs_historical_workbook_native import bound, workbook

from global_medicines_atlas.mbs_historical_workbook_headers import (
    profile_workbook_headers,
)
from global_medicines_atlas.mbs_historical_workbook_native import (
    iter_workbook_records,
)
from global_medicines_atlas.mbs_historical_workbook_value_shapes import (
    EXPECTED_FIELDS,
    EXPECTED_HEADERS,
    merge_archive_profiles,
    profile_workbook_records,
)


def _profile():
    return {
        "sheets": [
            {
                "name": "Demographic",
                "candidate_rows": [
                    {
                        "row_index": 3,
                        "disposition": "exact_contract_match",
                        "contract_id": "mbs-demographic-workbook-v1",
                        "labels": [
                            {"column": chr(65 + i), "text": header}
                            for i, header in enumerate(EXPECTED_HEADERS)
                        ],
                        "column_bindings": [
                            {
                                "column": chr(65 + i),
                                "field": field,
                                "native_header": header,
                                "status": "interpreted",
                            }
                            for i, (field, header) in enumerate(
                                zip(
                                    EXPECTED_FIELDS,
                                    EXPECTED_HEADERS,
                                    strict=True,
                                )
                            )
                        ],
                    }
                ],
            },
            {"name": "Metadata", "candidate_rows": []},
        ]
    }


def _cell(sheet, row, col, value, *, cell_type="s", state="value", props=None):
    return {
        "kind": "cell",
        "sheet_name": sheet,
        "row_index": row,
        "column_index": col,
        "cell": {
            "state": state,
            "value": value,
            "native_properties": {"cell_type": cell_type, **(props or {})},
        },
    }


def _row(sheet, row, count):
    return {
        "kind": "row",
        "sheet_name": sheet,
        "row_index": row,
        "cell_count": count,
    }


def _records():
    records = []
    for column, header in enumerate(EXPECTED_HEADERS, start=1):
        records.append(_cell("Demographic", 3, column, header))
    records.append(_row("Demographic", 3, 8))
    values = [
        _cell(
            "Demographic",
            4,
            1,
            "2016",
            cell_type="n",
            props={"raw_value": "2016"},
        ),
        _cell(
            "Demographic",
            4,
            2,
            "1.234e2",
            cell_type="n",
            props={"raw_value": "1.234e2"},
        ),
        _cell("Demographic", 4, 3, "0012", cell_type="s"),
        _cell("Demographic", 4, 4, "NSW", cell_type="inlineStr"),
        _cell("Demographic", 4, 5, "1/2", cell_type="s"),
        _cell("Demographic", 4, 6, "F", cell_type="s"),
        _cell("Demographic", 4, 7, None, cell_type="n", state="null"),
        _cell(
            "Demographic",
            4,
            8,
            "12.50",
            cell_type="str",
            props={
                "formula_present": True,
                "formula": "1+2",
                "raw_value": "12.50",
            },
        ),
    ]
    records.extend(values)
    records.extend((
        _row("Demographic", 4, 8),
        _row("Demographic", 5, 0),
        _cell("Metadata", 1, 1, "private sentinel"),
        _row("Metadata", 1, 1),
    ))
    return records


def test_profiles_lexical_and_native_shapes_without_emitting_values():
    report = profile_workbook_records(_records(), _profile())

    assert report["header_cells"] == 8
    assert report["data_rows"] == 2
    assert report["fields"]["calendar_year_label"]["value_shapes"] == {
        "numeric_integer_lexeme": 1
    }
    assert report["fields"]["processing_month_label"]["value_shapes"] == {
        "numeric_exponent_lexeme": 1
    }
    assert report["fields"]["schedule_item_identifier"]["value_shapes"] == {
        "text_integer_lexeme": 1
    }
    assert report["fields"]["age_range_label"]["value_shapes"] == {
        "text_slash_delimited_components": 1
    }
    assert report["fields"]["service_count_label"]["value_shapes"] == {
        "missing_value": 1
    }
    benefit = report["fields"]["benefit_amount_label_currency_unresolved"]
    assert benefit["value_shapes"] == {"formula_with_cached_value": 1}
    assert benefit["formula_cells"] == benefit["formula_cells_with_cache"] == 1
    assert (
        report["fields"]["state_label"]["missing_physical_cell_positions"] == 1
    )
    assert report["source_values_emitted"] is False
    assert report["source_column_meanings_qualified"] is False
    assert report["currency_interpreted"] is False
    assert report["date_interpreted"] is False
    assert report["p7_workbook_in_scope"] is False
    assert report["p7_date_inference_applied"] is False
    assert report["p7_domain_date_semantics_qualified"] is False
    assert "private sentinel" not in repr(report)


def test_native_workbook_reader_and_value_profile_integrate_without_values(
    tmp_path,
):
    path, member, native = bound(tmp_path, workbook())
    header_report = profile_workbook_headers(path, member, native)
    profile = json.loads(header_report["canonical_profile"])
    report = profile_workbook_records(
        iter_workbook_records(path, member, native), profile
    )

    assert report["source_cell_records"] == 18
    assert report["header_cells"] == 8
    assert report["fields"]["calendar_year_label"]["value_shapes"] == {
        "numeric_integer_lexeme": 1
    }
    benefit = report["fields"]["benefit_amount_label_currency_unresolved"]
    assert benefit["value_shapes"] == {"numeric_decimal_lexeme": 1}
    assert report["source_values_emitted"] is False
    assert "2016" not in repr(report)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("header", "header cell readback"),
        ("binding", "header binding differs"),
        ("candidate", "unresolved header candidate"),
    ],
)
def test_rejects_header_or_contract_binding_drift(change, message):
    profile = deepcopy(_profile())
    if change == "header":
        records = _records()
        records[0]["cell"]["value"] = "not Year"
    elif change == "binding":
        profile["sheets"][0]["candidate_rows"][0]["column_bindings"][0][
            "field"
        ] = "wrong"
        records = _records()
    else:
        profile["sheets"][0]["candidate_rows"][0]["disposition"] = (
            "unresolved_candidate"
        )
        records = _records()
    with pytest.raises(ValueError, match=message):
        profile_workbook_records(records, profile)


def test_rejects_non_row_ordered_records():
    records = _records()
    records[9], records[17] = records[17], records[9]
    with pytest.raises(ValueError, match="order"):
        profile_workbook_records(records, _profile())


def test_merge_requires_complete_archive_indices_and_unique_candidate_ids():
    reports = [
        {
            "archive_index": index,
            "source": {
                "source_path": f"archive-{index}",
                "source_sha256": str(index),
            },
            "workbook_count": 0,
            "workbook_bindings": [],
            "fields": {
                field: {
                    "cell_count": 0,
                    "value_shapes": {},
                    "native_cell_types": {},
                    "native_states": {},
                    "formula_cells": 0,
                    "formula_cells_with_cache": 0,
                    "source_error_cells": 0,
                    "native_missing_value_cells": 0,
                    "missing_physical_cell_positions": 0,
                }
                for field in EXPECTED_FIELDS
            },
            **dict.fromkeys(
                (
                    "source_cell_records",
                    "header_cells",
                    "pre_header_cells",
                    "other_sheet_cells",
                    "out_of_contract_data_cells",
                    "data_rows",
                ),
                0,
            ),
        }
        for index in range(6)
    ]
    assert merge_archive_profiles(reports, 6)["workbook_count"] == 0
    with pytest.raises(ValueError, match="denominator"):
        merge_archive_profiles(reports[:-1], 6)
    reports[1]["workbook_bindings"] = [
        {"candidate_output_id": "duplicate", "candidate_group": 1},
        {"candidate_output_id": "duplicate", "candidate_group": 2},
    ]
    reports[1]["workbook_count"] = 2
    with pytest.raises(ValueError, match=r"field|identity"):
        merge_archive_profiles(reports, 6)
