"""Legacy annotations remain source assertions with complete cell lineage."""

import json
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_workbook_silver import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic receipt
)

from global_medicines_atlas.mbs_workbook_domain import (
    LEGACY_SHEET_PROFILES,
    iter_workbook_domain_batches,
    profile_workbook_domain,
)

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"


def fixture(*, drift: bool = False, sheet_drift: bool = False) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        sheets = []
        relationships = []
        for index, (name, dimension, headers) in enumerate(
            LEGACY_SHEET_PROFILES, 1
        ):
            reported_dimension = (
                "A1:AX161" if sheet_drift and index == 1 else dimension
            )
            sheets.append(
                f'<sheet name="{name}" sheetId="{index}" r:id="r{index}"/>'
            )
            relationships.append(
                f'<Relationship Id="r{index}" Type="worksheet" Target="worksheets/sheet{index}.xml"/>'
            )
            cells = "".join(
                f'<c r="{column}1" t="inlineStr"><is><t>{escape(header)}</t></is></c>'
                for column, header in headers
            )
            if drift and index == 1:
                cells = cells.replace("Technology", "ChangedTechnology")
            data = '<c r="A2" t="inlineStr"><is><t>00123</t></is></c>'
            if index in {1, 3}:
                data += '<c r="AO2" t="inlineStr"><is><t>synthetic element</t></is></c><c r="AT2"/><c r="AV2" t="e"><f>1/0</f><v>#DIV/0!</v></c>'
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml",
                f'<worksheet xmlns="{MAIN}"><dimension ref="{reported_dimension}"/><sheetData><row r="1">{cells}</row><row r="2">{data}</row></sheetData></worksheet>',
            )
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>{"".join(sheets)}</sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{PACKAGE}">{"".join(relationships)}</Relationships>',
        )
    return output.getvalue()


def test_annotation_and_declining_membership_do_not_become_current_status() -> (
    None
):
    payload = fixture()
    table = pa.Table.from_batches(
        list(iter_workbook_domain_batches(payload, _receipt(payload)))
    )
    rows = {
        (row["sheet_name"], row["coordinate"]): row for row in table.to_pylist()
    }
    element = rows["Sheet1", "AO2"]
    assert element["mapping_target"] == "legacy_annotations"
    assert element["mapping_field"] == "element"
    assert element["native_header"] == "Element"
    assert element["display_value"] == "synthetic element"
    assert rows["Sheet1", "A2"]["display_value"] == "00123"
    assert rows["Sheet3", "A2"]["mapping_field"] == "declining_list_member"
    assert rows["Sheet3", "A2"]["mapping_status"] == "source_explicit_header"
    assert rows["Sheet1", "AT2"]["conversion_status"] == "missing_value"
    assert (
        table.schema.metadata[b"claim_scope"]
        == b"legacy_source_annotations_only"
    )


def test_unlabelled_formula_cells_and_all_headers_are_retained() -> None:
    payload = fixture()
    batches = list(
        iter_workbook_domain_batches(
            payload, _receipt(payload), rows_per_batch=3
        )
    )
    rows = [row for batch in batches for row in batch.to_pylist()]
    assert len(rows) == 107
    error = next(row for row in rows if row["coordinate"] == "AV2")
    assert error["native_header"] is None
    assert error["mapping_status"] == "unlabelled"
    assert error["formula"] == "1/0"
    assert error["error_code"] == "#DIV/0!"
    assert error["source_row_id"].endswith("xl/worksheets/sheet1.xml#row=2")
    assert rows[0]["row_kind"] == "header"


def test_schema_drift_is_rejected_before_any_mapped_output() -> None:
    payload = fixture(drift=True)
    with pytest.raises(ValueError, match="header profile"):
        next(iter_workbook_domain_batches(payload, _receipt(payload)))


def test_sheet_dimension_drift_is_rejected() -> None:
    payload = fixture(sheet_drift=True)
    with pytest.raises(ValueError, match="sheet profile"):
        next(iter_workbook_domain_batches(payload, _receipt(payload)))


def test_profile_matches_observed_hosted_headers_not_just_test_builder() -> (
    None
):
    root = Path(__file__).resolve().parents[1]
    report = json.loads(
        (
            root / "quality/qualifications/mbs-workbook-storage-20260830.json"
        ).read_text()
    )
    assert report["storage_qualification"]["parquet_roundtrip_verified"] is True
    assert report["storage_qualification"]["cells"] == 13742
    observed = tuple(
        (
            sheet["name"],
            sheet["dimension"],
            tuple(
                (cell["coordinate"][:-1], cell["display_value"])
                for cell in sheet["header_candidates"]
            ),
        )
        for sheet in report["storage_qualification"]["sheets"]
    )
    assert observed == LEGACY_SHEET_PROFILES


def test_domain_mapping_is_chunk_invariant_and_parquet_portable() -> None:
    payload = fixture()
    receipt = _receipt(payload)
    first = pa.Table.from_batches(
        list(iter_workbook_domain_batches(payload, receipt, rows_per_batch=1))
    )
    second = pa.Table.from_batches(
        list(iter_workbook_domain_batches(payload, receipt, rows_per_batch=128))
    )
    assert first.equals(second, check_metadata=True)
    output = BytesIO()
    pq.write_table(first, output)
    assert pq.read_table(BytesIO(output.getvalue())).equals(
        first, check_metadata=True
    )


def test_profile_counts_all_cells_without_semantic_promotion() -> None:
    payload = fixture()
    profile = profile_workbook_domain(payload, _receipt(payload))
    assert profile["cells"] == 107
    assert profile["mapping_statuses"] == {
        "header": 97,
        "source_explicit_header": 8,
        "unlabelled": 2,
    }
    assert profile["semantic_promotion"] is False
