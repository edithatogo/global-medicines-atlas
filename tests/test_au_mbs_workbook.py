"""Source-native contracts for the legacy MBS P7 workbook."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from pydantic import AnyUrl, ValidationError

from global_medicines_atlas.adapters.au_mbs_workbook import (
    LEGACY_P7_SHA256,
    MbsWorkbookBatch,
    parse_mbs_workbook,
    qualify_legacy_p7_workbook,
)
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)

SHA = "b" * 64


def _xlsx(*, target: str = "worksheets/sheet1.xml") -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types' />",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1" /></sheets>
            </workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f"""<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Type="worksheet" Target="{target}" />
            </Relationships>""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            """<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <si><t>ItemNum</t></si><si><t>123</t></si>
            </sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <dimension ref="A1:C2" /><sheetData>
                <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><v>1</v></c></row>
                <row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2"><f>B1*2</f><v>2</v></c><c r="C2" t="e"><v>#N/A</v></c></row>
              </sheetData>
            </worksheet>""",
        )
    return stream.getvalue()


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="fixture:au-mbs-p7-workbook",
        source=SourceIdentity(
            catalog_id="au-mbs-p7-legacy-workbook",
            source_id="au-mbs-p7-legacy-workbook",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="Synthetic P7 workbook fixture",
            catalog_version="fixture-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://fixtures.invalid/au-mbs-p7-workbook"),
            retrieved_at=datetime(2026, 8, 29, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="au-mbs-p7-workbook-fixture",
            transformation_sha256=SHA,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def test_workbook_projection_preserves_cells_formulas_errors_and_strings() -> (
    None
):
    payload = _xlsx()

    batch = parse_mbs_workbook(payload, _receipt(payload))

    assert isinstance(batch, MbsWorkbookBatch)
    assert batch.source_id == "au-mbs-p7-legacy-workbook"
    assert batch.sheet_count == 1
    sheet = batch.sheets[0]
    assert (sheet.name, sheet.dimension, sheet.path) == (
        "Sheet1",
        "A1:C2",
        "xl/worksheets/sheet1.xml",
    )
    cells = {cell.coordinate: cell for cell in sheet.cells}
    assert cells["A1"].display_value == "ItemNum"
    assert cells["A2"].display_value == "123"
    assert cells["B2"].formula == "B1*2"
    assert cells["B2"].raw_value == "2"
    assert cells["C2"].cell_type == "e"
    assert cells["C2"].raw_value == "#N/A"


def test_workbook_projection_rejects_relationship_traversal() -> None:
    payload = _xlsx(target="../../outside.xml")
    with pytest.raises(ValueError, match="relationship target"):
        parse_mbs_workbook(payload, _receipt(payload))


def test_exact_legacy_workbook_qualification_rejects_fixture() -> None:
    payload = _xlsx()
    assert _receipt(payload).payload.sha256 != LEGACY_P7_SHA256
    with pytest.raises(ValueError, match="exact July 2024 P7 workbook"):
        qualify_legacy_p7_workbook(payload, _receipt(payload))


def test_workbook_batch_source_identity_cannot_be_overridden() -> None:
    payload = _xlsx()
    batch = parse_mbs_workbook(payload, _receipt(payload))

    with pytest.raises(ValidationError):
        MbsWorkbookBatch.model_validate({
            **batch.model_dump(),
            "source_id": "au-mbs",
        })
