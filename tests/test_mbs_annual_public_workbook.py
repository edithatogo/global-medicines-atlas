"""Qualify public workbook structure without emitting patient observations."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest
import scripts.qualify_mbs_annual_public_workbook as annual
from scripts.qualify_mbs_annual_public_workbook import profile_workbook

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
HEADERS = (
    "Financial Year",
    "State",
    "Column1",
    "Broad Type of Service",
    "Patients",
    "Patients as percent of Population",
    "Services",
    "Services per Patient",
    "Services per capita",
    "Benefits",
    "Benefits per Patient",
    "Benefits per capita",
    "Estimated Resident Population",
)
TITLE = "Table 3: Financial Year Patient* Statistics by Broad Type of Service and State"
DEFINITION = (
    "* A patient is defined as a person who claimed at least one MBS service."
)


def _text_cell(coordinate: str, value: str) -> str:
    return (
        f'<c r="{coordinate}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
    )


def _data_row(index: int, group: str, patient_cell: str) -> str:
    cells = (
        _text_cell(f"A{index}", "2025-26")
        + _text_cell(f"B{index}", "SYNTHETIC_STATE")
        + _text_cell(f"D{index}", group)
        + patient_cell
    )
    return f'<row r="{index}">{cells}</row>'


def _workbook(
    rows: str,
    *,
    headers: tuple[str, ...] = HEADERS,
    note: str = DEFINITION,
    extra_header: str = "",
) -> bytes:
    header = "".join(
        _text_cell(f"{chr(65 + index)}9", name)
        for index, name in enumerate(headers)
    )
    result = BytesIO()
    with ZipFile(result, "w") as archive:
        archive.writestr("[Content_Types].xml", f'<Types xmlns="{TYPES}"/>')
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{MAIN}" xmlns:r="{OFFICE}"><sheets>'
            '<sheet name="Patients" sheetId="1" r:id="r1"/>'
            "</sheets></workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{PACKAGE}">'
            f'<Relationship Id="r1" Type="{OFFICE}/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{MAIN}"><dimension ref="A1:M50"/><sheetData>'
            f'<row r="1">{_text_cell("A1", TITLE)}</row>'
            f'<row r="5">{_text_cell("A5", note)}</row>'
            f'<row r="9">{header}{extra_header}</row>'
            f"{rows}</sheetData></worksheet>",
        )
    return result.getvalue()


def _profile(payload: bytes) -> dict[str, object]:
    return profile_workbook(
        payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        expected_bytes=len(payload),
    )


def test_public_workbook_profile_retains_structure_without_observation_values() -> (
    None
):
    payload = _workbook(
        _data_row(10, "SYNTHETIC_GROUP", '<c r="E10"><v>987654321</v></c>')
    )

    result = _profile(payload)

    assert result["data_rows"] == 1
    assert result["financial_year_labels"] == ["2025-26"]
    assert result["patient_value_shapes"] == {"numeric_nonnegative_integer": 1}
    assert result["native_header_labels"] == list(HEADERS)
    assert result["patient_definition"] == DEFINITION
    assert result["duplicate_year_state_group_keys"] == 0
    encoded = json.dumps(result)
    assert "987654321" not in encoded
    assert "SYNTHETIC_STATE" not in encoded
    assert "SYNTHETIC_GROUP" not in encoded


def test_workbook_identity_is_checked_before_archive_parsing() -> None:
    payload = _workbook(_data_row(10, "GROUP", '<c r="E10"><v>2</v></c>'))
    with pytest.raises(ValueError, match="identity"):
        profile_workbook(
            payload, expected_sha256="0" * 64, expected_bytes=len(payload)
        )
    with pytest.raises(ValueError, match="identity"):
        profile_workbook(
            payload,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
            expected_bytes=len(payload) + 1,
        )


def test_missing_or_renamed_patient_header_is_not_a_patient_measure() -> None:
    payload = _workbook("", headers=(*HEADERS[:4], "Services", *HEADERS[5:]))
    with pytest.raises(ValueError, match="header"):
        _profile(payload)


def test_unexpected_formula_header_is_rejected() -> None:
    payload = _workbook("", extra_header='<c r="N9"><f>1+1</f></c>')
    with pytest.raises(ValueError, match="header"):
        _profile(payload)


def test_patient_shapes_do_not_treat_missing_text_or_formulas_as_zero() -> None:
    payload = _workbook(
        _data_row(10, "ONE", "")
        + _data_row(11, "TWO", _text_cell("E11", "Not available"))
        + _data_row(12, "THREE", '<c r="E12"><f>1+1</f><v>2</v></c>')
        + _data_row(13, "FOUR", '<c r="E13" t="e"><v>#N/A</v></c>')
        + _data_row(14, "FIVE", '<c r="E14"><v>-0.5</v></c>')
    )
    result = _profile(payload)
    assert result["patient_value_shapes"] == {
        "formula_uninterpreted": 1,
        "missing": 1,
        "numeric_other_uninterpreted": 1,
        "source_error": 1,
        "text_uninterpreted": 1,
    }


def test_duplicate_key_and_missing_definition_do_not_create_qualified_counts() -> (
    None
):
    payload = _workbook(
        _data_row(10, "SAME", '<c r="E10"><v>4</v></c>')
        + _data_row(11, "SAME", '<c r="E11"><v>5</v></c>')
    )
    assert _profile(payload)["duplicate_year_state_group_keys"] == 1
    with pytest.raises(ValueError, match="definition"):
        _profile(_workbook("", note="Different, unqualified definition"))


def test_unrecognised_period_is_not_a_zero_or_silent_data_row() -> None:
    payload = _workbook(
        _data_row(10, "GROUP", '<c r="E10"><v>987654321</v></c>').replace(
            "2025-26", "unrecognised period"
        )
    )
    result = _profile(payload)
    assert result["data_rows"] == 0
    assert result["unclassified_rows_after_header"] == 1
    assert result["patient_value_shapes"] == {}
    assert "987654321" not in json.dumps(result)


def test_duplicate_cell_coordinate_is_rejected() -> None:
    payload = _workbook(
        _data_row(
            10,
            "GROUP",
            '<c r="E10"><v>2</v></c><c r="E10"><v>3</v></c>',
        )
    )
    with pytest.raises(ValueError, match="cell identity"):
        _profile(payload)


def test_archived_receipt_and_workbook_are_both_bound_and_remain_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _workbook(_data_row(10, "GROUP", '<c r="E10"><v>7</v></c>'))
    digest = hashlib.sha256(payload).hexdigest()
    source = {
        "schema_id": "global-medicines-atlas.australian-harvest-receipt",
        "schema_version": 1,
        "source_id": "au-health-medicare-statistics",
        "category": "medicare_statistics_collection_attachment",
        "source_url": annual.SOURCE_URL,
        "archive_path": annual.RAW_PATH,
        "sha256": digest,
        "byte_count": len(payload),
    }
    receipt = json.dumps(source).encode()
    monkeypatch.setattr(annual, "SHA256", digest)
    monkeypatch.setattr(annual, "BYTE_COUNT", len(payload))
    monkeypatch.setattr(
        annual, "RECEIPT_SHA256", hashlib.sha256(receipt).hexdigest()
    )

    report = annual.qualify_archived_workbook(payload, receipt)

    assert report["source"]["sha256"] == digest
    assert report["qualification"]["m106_accepted"] is False
    assert report["qualification"]["patient_denominator_admitted"] is False
    assert (
        report["qualification"]["cross_group_deduplication_qualified"] is False
    )
    assert (
        report["qualification"]["patient_observation_values_emitted"] is False
    )
    with pytest.raises(ValueError, match="receipt identity"):
        annual.qualify_archived_workbook(payload, receipt + b" ")

    source["source_id"] = "unrelated-source"
    wrong_source = json.dumps(source).encode()
    monkeypatch.setattr(
        annual, "RECEIPT_SHA256", hashlib.sha256(wrong_source).hexdigest()
    )
    with pytest.raises(ValueError, match="receipt content"):
        annual.qualify_archived_workbook(payload, wrong_source)


def test_retained_public_profile_preserves_identity_and_open_gates() -> None:
    root = Path(__file__).resolve().parents[1]
    report = json.loads(
        (
            root / "quality/qualifications/"
            "mbs-annual-public-workbook-qualification-20261115.json"
        ).read_text(encoding="utf-8")
    )
    assert report["source"]["sha256"] == annual.SHA256
    assert report["source"]["receipt_sha256"] == annual.RECEIPT_SHA256
    assert report["source"]["revision"] == annual.REVISION
    assert report["profile"]["data_rows"] == 2202
    assert report["profile"]["financial_year_labels"][0] == "2009-10"
    assert report["profile"]["financial_year_labels"][-1] == "2025-26"
    assert report["profile"]["native_header_labels"] == list(HEADERS)
    assert report["profile"]["patient_definition"] == DEFINITION
    assert report["profile"]["unclassified_rows_after_header"] == 0
    for key in (
        "m106_accepted",
        "cross_group_deduplication_qualified",
        "patient_denominator_admitted",
        "federation_v4_admission_performed",
        "patient_observation_values_emitted",
        "geography_or_service_group_labels_emitted",
        "individual_participant_or_cohort_data_accessed",
        "new_dataset_published",
    ):
        assert report["qualification"][key] is False
