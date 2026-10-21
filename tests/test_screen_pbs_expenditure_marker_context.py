from __future__ import annotations

import hashlib
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from scripts.screen_pbs_expenditure_marker_context import _screen_object


def _minimal_xlsx() -> bytes:
    files = {
        "xl/workbook.xml": (
            '<workbook '
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships">'
            '<sheets><sheet name="Table7" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships '
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'worksheet"/>'
            '</Relationships>'
        ),
        "xl/sharedStrings.xml": (
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><t>ATC classification</t></si></sst>'
        ),
        "xl/worksheets/sheet1.xml": (
            '<worksheet '
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1">'
            '<c r="A1" t="s"><v>0</v></c>'
            '<c r="B1" t="inlineStr"><is><t>SNOMED CT</t></is></c>'
            '<c r="C1" t="str"><v>ATC</v></c>'
            '<c r="D1" t="str"><v>A10BA02</v></c>'
            '</row></sheetData></worksheet>'
        ),
    }
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_marker_context_screen_counts_text_and_atc_codes_separately() -> None:
    payload = _minimal_xlsx()
    result = _screen_object(
        payload,
        {
            "path": "fixture.xlsx",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
        },
    )

    assert result["marker_cell_count"] == 3
    assert result["marker_only_cell_count"] == 2
    assert result["context_text_cell_count"] == 1
    assert result["atc_code_shape_cell_count"] == 1
    assert result["sheets_with_markers"][0]["sheet"] == "Table7"


def test_marker_context_screen_rejects_wrong_pinned_identity() -> None:
    payload = _minimal_xlsx()

    try:
        _screen_object(
            payload,
            {"path": "fixture.xlsx", "sha256": "0" * 64, "byte_count": len(payload)},
        )
    except ValueError as error:
        assert "pinned identity mismatch" in str(error)
    else:
        raise AssertionError("wrong pinned identity should fail closed")
