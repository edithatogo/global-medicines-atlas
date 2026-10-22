"""Historical workbook extraction preserves physical cells without header claims."""

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

import pytest
from test_mbs_archive_members import fixture
from test_mbs_demographic_extraction import workbook

from global_medicines_atlas import mbs_historical_workbook_native as module
from global_medicines_atlas.mbs_historical_csv_package import FrozenMbsMember
from global_medicines_atlas.mbs_historical_workbook_native import (
    iter_workbook_records,
)


def bound(tmp_path, payload):
    _, source = fixture(tmp_path)
    path = tmp_path / "private.xlsx"
    path.write_bytes(payload)
    native = "SYNTHETIC.xlsx"
    member = FrozenMbsMember(
        source,
        0,
        sha256(payload).hexdigest(),
        len(payload),
        sha256(native.encode()).hexdigest(),
        ".xlsx",
        "5" * 64,
    )
    return path, member, native


def test_every_sheet_cell_and_empty_row_is_retained_without_header_profile(
    tmp_path,
):
    args = bound(tmp_path, workbook(header=("Unreviewed",)))
    records = list(iter_workbook_records(*args))
    cells = [r for r in records if r["kind"] == "cell"]
    rows = [r for r in records if r["kind"] == "row"]
    sheets = [r for r in records if r["kind"] == "sheet"]
    assert len(cells) == 11
    assert len(rows) == 5
    assert len(sheets) == 2
    unknown = next(r for r in cells if r["cell"]["value"] == "Unknown")
    assert unknown["cell"]["native_properties"]["formula"] == '"Unknown"'
    assert unknown["cell"]["native_properties"]["formula_attributes"] == {
        "t": "shared",
        "si": "0",
    }
    assert sum(r["native_cell_count"] for r in sheets) == len(cells)
    assert sum(r["cell_count"] for r in rows) == len(cells)
    assert any(r["cell_count"] == 0 for r in rows)
    assert all(r["semantics_qualified"] is False for r in sheets)


@pytest.mark.parametrize("change", ["bytes", "path", "suffix", "size"])
def test_binding_failure_precedes_all_records(tmp_path, change):
    path, member, native = bound(tmp_path, workbook())
    if change == "bytes":
        path.write_bytes(path.read_bytes() + b"changed")
    elif change == "path":
        native = "other.xlsx"
    elif change == "suffix":
        member = replace(member, suffix=".csv")
    else:
        member = replace(member, byte_count=True)
    with pytest.raises(ValueError, match="historical workbook"):
        next(iter_workbook_records(path, member, native))


def altered_workbook(payload, change):
    output = BytesIO()
    with ZipFile(BytesIO(payload)) as original, ZipFile(output, "w") as target:
        for info in original.infolist():
            value = original.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                value = change(value)
            target.writestr(info.filename, value)
    return output.getvalue()


@pytest.mark.parametrize(
    "change", ["duplicate", "wrong_row", "order", "doctype"]
)
def test_native_xml_identity_and_parser_failures_remain_failures(
    tmp_path, change
):
    def alter(value):
        if change == "duplicate":
            return value.replace(
                b'<c r="A4">', b'<c r="A4"><v>duplicate</v></c><c r="A4">'
            )
        if change == "wrong_row":
            return value.replace(b'<c r="A4">', b'<c r="A5">')
        if change == "order":
            return value.replace(b'<row r="4">', b'<row r="2">')
        return b'<!DOCTYPE worksheet [<!ENTITY x "forbidden">]>' + value

    args = bound(tmp_path, altered_workbook(workbook(), alter))
    with pytest.raises(ValueError, match=r"identity|DTD|declaration|DOCTYPE"):
        list(iter_workbook_records(*args))


def test_native_cell_errors_and_unrounded_precision_are_preserved(tmp_path):
    payload = workbook(
        data_row='<c r="A4"><v>1.123456789123456789</v></c><c r="B4" t="e"><f>1/0</f><v>#DIV/0!</v></c><c r="C4"/>'
    )
    cells = [
        r
        for r in iter_workbook_records(*bound(tmp_path, payload))
        if r["kind"] == "cell" and r["row_index"] == 4
    ]
    assert cells[0]["cell"]["value"] == "1.123456789123456789"
    assert cells[1]["cell"]["state"] == "source_error"
    assert cells[1]["cell"]["native_properties"]["formula"] == "1/0"
    assert cells[1]["cell"]["value"] == "#DIV/0!"
    assert cells[2]["cell"]["state"] == "null"


def test_native_record_bound_is_enforced(tmp_path, monkeypatch):
    args = bound(tmp_path, workbook())
    monkeypatch.setattr(module, "MAX_RECORD_BYTES", 1)
    with pytest.raises(ValueError, match="record byte bound"):
        list(iter_workbook_records(*args))


@pytest.mark.parametrize("change", ["root", "row_parent"])
def test_unexpected_worksheet_shape_is_rejected(tmp_path, change):
    def alter(value):
        if change == "root":
            return value.replace(b"<worksheet ", b"<invented ").replace(
                b"</worksheet>", b"</invented>"
            )
        return value.replace(b"<sheetData>", b"<invented>").replace(
            b"</sheetData>", b"</invented>"
        )

    args = bound(tmp_path, altered_workbook(workbook(), alter))
    with pytest.raises(ValueError, match=r"root|parent"):
        list(iter_workbook_records(*args))


def test_same_size_wrong_digest_is_rejected_before_output(tmp_path):
    path, member, native = bound(tmp_path, workbook())
    member = replace(member, sha256="0" * 64)
    with pytest.raises(ValueError, match="identity"):
        next(iter_workbook_records(path, member, native))
