"""Receipt-bound extraction preserves metadata and source-cell properties."""

from io import BytesIO
from zipfile import ZipFile

import pytest
from test_mbs_demographic_silver import source

from global_medicines_atlas.mbs_demographic_extraction import (
    AncillaryCell,
    WorkbookMember,
    WorkbookSheet,
    iter_demographic_records,
)
from global_medicines_atlas.mbs_demographic_silver import (
    WORKBOOK_HEADERS,
    DemographicRow,
)

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def workbook(data_row=None, header=None, target="worksheets/sheet1.xml"):
    cells = "".join(
        f'<c r="{chr(65 + i)}3" t="inlineStr"><is><t>{name}</t></is></c>'
        for i, name in enumerate(header or WORKBOOK_HEADERS)
    )
    data = data_row or (
        '<c r="A4"><v>2016</v></c><c r="B4"><v>3</v></c>'
        '<c r="C4" t="inlineStr"><is><t>00123</t></is></c>'
        '<c r="D4" t="inlineStr"><is><t>SYNTHETIC</t></is></c>'
        '<c r="E4" t="str"><f t="shared" si="0">"Unknown"</f><v>Unknown</v></c>'
        '<c r="F4" t="inlineStr"><is><t>F</t></is></c>'
        '<c r="G4"><v>-2</v></c><c r="H4"><v>12.5</v></c>'
    )
    output = BytesIO()
    with ZipFile(output, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets>'
            '<sheet name="Synthetic primary" sheetId="1" r:id="r1"/>'
            '<sheet name="Metadata" sheetId="2" r:id="r2"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{PKG}">'
            f'<Relationship Id="r1" Type="{REL}/worksheet" Target="{target}"/>'
            f'<Relationship Id="r2" Type="{REL}/worksheet" Target="worksheets/sheet2.xml"/></Relationships>',
        )
        z.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{NS}"><dimension ref="A1:H4"/><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>Synthetic title</t></is></c></row>'
            f'<row r="3">{cells}</row><row r="4">{data}</row></sheetData></worksheet>',
        )
        z.writestr(
            "xl/worksheets/sheet2.xml",
            f'<worksheet xmlns="{NS}"><dimension ref="A1:A3"/><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>Synthetic metadata</t></is></c></row>'
            '<row r="3"/></sheetData></worksheet>',
        )
    return output.getvalue()


def test_workbook_primary_metadata_formulas_and_inventory_are_retained():
    payload = workbook()
    records = list(
        iter_demographic_records(payload, source("workbook", payload))
    )
    rows = [x for x in records if isinstance(x, DemographicRow)]
    auxiliary = [x for x in records if isinstance(x, AncillaryCell)]
    sheets = [x for x in records if isinstance(x, WorkbookSheet)]
    members = [x for x in records if isinstance(x, WorkbookMember)]
    assert len(rows) == 1
    assert len(auxiliary) == 10
    assert len(members) == 4
    assert [x.native_cell_count for x in sheets] == [17, 1]
    assert [x.native_row_count for x in sheets] == [3, 2]
    assert rows[0].cells[2].value == "00123"
    assert rows[0].cells[4].value == "Unknown"
    assert rows[0].cells[4].native_properties["formula_present"] is True
    assert rows[0].cells[4].native_properties["formula_attributes"] == {
        "t": "shared",
        "si": "0",
    }
    assert rows[0].cells[4].native_properties["formula"] == '"Unknown"'
    assert any(x.cell.value == "Synthetic metadata" for x in auxiliary)
    assert sum(x.native_cell_count for x in sheets) == sum(
        cell.state != "absent" for row in rows for cell in row.cells
    ) + len(auxiliary)


def test_csv_headers_records_empty_fields_and_quotes_remain_native():
    payload = b'Year,Month of Processing,Item Number,State,Age Range,Gender,Services,Benefit\r\n2016,3,00123,SYNTHETIC,"""Unknown""",F,-2,12.5\r\n2016,3,00124,SYNTHETIC,,F,0,\r\n'
    records = list(iter_demographic_records(payload, source("csv", payload)))
    rows = [x for x in records if isinstance(x, DemographicRow)]
    assert len([x for x in records if isinstance(x, AncillaryCell)]) == 8
    assert [x.row_index for x in rows] == [2, 3]
    assert rows[0].cells[4].value == '"Unknown"'
    assert rows[1].cells[4].state == "value"
    assert rows[1].cells[4].value == ""  # ruff: ignore[compare-to-empty-string] -- distinguish blank from null
    assert not any(isinstance(x, WorkbookMember) for x in records)


def test_digest_is_verified_before_any_parser_output():
    payload = workbook()
    with pytest.raises(ValueError, match="identity"):
        next(
            iter_demographic_records(
                payload + b"changed", source("workbook", payload)
            )
        )


def test_unsupported_header_is_rejected_and_root_relative_targets_are_safe():
    payload = workbook(header=("Wrong", *WORKBOOK_HEADERS[1:]))
    with pytest.raises(ValueError, match="header"):
        list(iter_demographic_records(payload, source("workbook", payload)))
    valid = workbook(target="/xl/worksheets/sheet1.xml")
    assert any(
        isinstance(x, DemographicRow)
        for x in iter_demographic_records(valid, source("workbook", valid))
    )
    unsafe = workbook(target="../../outside.xml")
    with pytest.raises(ValueError, match="relationship"):
        list(iter_demographic_records(unsafe, source("workbook", unsafe)))


@pytest.mark.parametrize(
    "data",
    [
        '<c r="A5"><v>1</v></c>',
        '<c r="A4"><v>1</v></c><c r="A4"><v>2</v></c>',
        '<c r="XFE4"><v>1</v></c>',
        '<c r="A0"><v>1</v></c>',
        '<c r="H4" t="e"/>',
    ],
)
def test_inconsistent_cell_coordinates_and_empty_errors_fail_closed(data):
    payload = workbook(data_row=data)
    with pytest.raises(ValueError, match=r"worksheet|workbook|CSV"):
        list(iter_demographic_records(payload, source("workbook", payload)))


def test_sparse_rows_and_extra_columns_are_retained():
    payload = workbook(
        data_row='<c r="A4"><v>2016</v></c><c r="I4" t="e"><v>#N/A</v></c>'
    )
    records = list(
        iter_demographic_records(payload, source("workbook", payload))
    )
    row = next(x for x in records if isinstance(x, DemographicRow))
    assert [cell.state for cell in row.cells] == ["value", *(["absent"] * 7)]
    extra = next(
        x
        for x in records
        if isinstance(x, AncillaryCell) and x.coordinate == "I4"
    )
    assert extra.cell.state == "source_error"
    assert extra.cell.value == "#N/A"


@pytest.mark.parametrize(
    "payload",
    [
        b"wrong,header\n",
        b"Year,Month of Processing,Item Number,State,Age Range,Gender,Services,Benefit\n1,2\n",
        b"Year,Month of Processing,Item Number,State,Age Range,Gender,Services,Benefit\n\xff\n",
    ],
)
def test_csv_shape_and_encoding_fail_closed(payload):
    with pytest.raises(ValueError, match=r"worksheet|workbook|CSV"):
        list(iter_demographic_records(payload, source("csv", payload)))


def rewrite_package(payload, transform, additions=None):
    output = BytesIO()
    with (
        ZipFile(BytesIO(payload)) as original,
        ZipFile(output, "w") as rewritten,
    ):
        for entry in original.infolist():
            rewritten.writestr(
                entry.filename, transform(entry.filename, original.read(entry))
            )
        for path, content in (additions or {}).items():
            rewritten.writestr(path, content)
    return output.getvalue()


def test_shared_strings_keep_rich_text_order_and_structure():
    payload = workbook(data_row='<c r="A4" t="s"><v>0</v></c>')
    payload = rewrite_package(
        payload,
        lambda _, content: content,
        {
            "xl/sharedStrings.xml": f'<sst xmlns="{NS}"><si><r><t>first</t></r><rPh><t>phonetic</t></rPh><r><t>last</t></r></si></sst>'
        },
    )
    records = list(
        iter_demographic_records(payload, source("workbook", payload))
    )
    cell = next(x for x in records if isinstance(x, DemographicRow)).cells[0]
    assert cell.value == "firstlast"
    assert "phonetic" in str(cell.native_properties["shared_string_structure"])


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('Id="r2"', 'Id="r1"'),
        (
            'Target="worksheets/sheet1.xml"',
            'TargetMode="External" Target="worksheets/sheet1.xml"',
        ),
        ('Target="worksheets/sheet1.xml"', 'Target="/outside/sheet.xml"'),
        ('name="Metadata"', 'name="Synthetic primary"'),
        ('<row r="4">', '<row r="0">'),
        ('<row r="4">', '<row r="invalid">'),
        ('<row r="3">', '<row r="2">'),
    ],
)
def test_ambiguous_package_and_row_identities_are_rejected(before, after):
    payload = rewrite_package(
        workbook(),
        lambda _, content: content.replace(before.encode(), after.encode()),
    )
    with pytest.raises(ValueError, match=r"workbook|worksheet|header"):
        list(iter_demographic_records(payload, source("workbook", payload)))
