"""All-sheet workbook typing uses synthetic source-native cells only."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZipInfo

import pyarrow as pa
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import AnyUrl

from global_medicines_atlas.mbs_workbook_silver import (
    iter_workbook_silver_batches,
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

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"


def _payload(extra: str = "") -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:

        def member(path: str, text: str) -> None:
            archive.writestr(
                ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0)), text
            )

        member(
            "xl/workbook.xml",
            f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>'
            + "".join(
                f'<sheet name="Sheet{index}" sheetId="{index}" r:id="r{index}"/>'
                for index in range(1, 5)
            )
            + "</sheets></workbook>",
        )
        member(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{PACKAGE}">'
            + "".join(
                f'<Relationship Id="r{index}" Type="worksheet" Target="worksheets/sheet{index}.xml"/>'
                for index in range(1, 5)
            )
            + "</Relationships>",
        )
        member(
            "xl/sharedStrings.xml",
            f'<sst xmlns="{MAIN}"><si><t>Element</t></si><si><t>exome</t></si></sst>',
        )
        cells = '<c r="A1" t="s"><v>0</v></c><c r="A2" t="s"><v>1</v></c><c r="B2"><f>1+1</f><v>2</v></c><c r="C2" t="e"><v>#N/A</v></c><c r="D2" t="b"><v>1</v></c><c r="E2" t="d"><v>2026-08-30</v></c><c r="F2" t="n"><v>1e2</v></c><c r="G2"/><c r="H2"><v/></c><c r="I2"><f/><v/></c>'
        for index in range(1, 5):
            contents = cells + extra if index < 4 else ""
            member(
                f"xl/worksheets/sheet{index}.xml",
                f'<worksheet xmlns="{MAIN}"><sheetData><row r="2">{contents}</row></sheetData></worksheet>',
            )
    return output.getvalue()


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="synthetic:workbook-silver",
        source=SourceIdentity(
            catalog_id="au-mbs-p7-legacy-workbook",
            source_id="au-mbs-p7-legacy-workbook",
            jurisdiction="AUS",
            authority="Synthetic",
            dataset_title="Synthetic workbook",
            catalog_version="synthetic-workbook-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(
                "https://fixtures.invalid/workbook?token=synthetic-token"
            ),
            retrieved_at=datetime(2026, 8, 30, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="synthetic",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def test_all_sheets_including_empty_are_retained_with_safe_lineage() -> None:
    payload = _payload()
    receipt = _receipt(payload)
    batches = list(
        iter_workbook_silver_batches(payload, receipt, rows_per_batch=4)
    )
    assert [batch.num_rows for batch in batches] == [4, 4, 2] * 3 + [0]
    paths: set[bytes] = set()
    for batch in batches:
        assert batch.schema.metadata is not None
        paths.add(batch.schema.metadata[b"sheet_path"])
        assert b"synthetic-token" not in b" ".join(
            batch.schema.metadata.values()
        )
        assert (
            batch.schema.metadata[b"source_receipt_sha256"]
            == receipt.digest().encode()
        )
        assert batch.schema.metadata[b"dimension"] == b"service_benefit"
        assert batch.schema.metadata[b"sheet_count"] == b"4"
    assert len(paths) == 4


def test_cached_types_formulas_errors_and_nulls_are_distinct() -> None:
    payload = _payload()
    rows = {
        row["coordinate"]: row
        for row in next(
            iter_workbook_silver_batches(payload, _receipt(payload))
        ).to_pylist()
    }
    assert rows["A2"]["text_value"] == "exome"
    assert rows["A2"]["raw_value"] == "1"
    assert rows["B2"]["decimal_value"] == Decimal(2)
    assert rows["B2"]["formula"] == "1+1"
    assert rows["B2"]["value_origin"] == "formula_cache"
    assert rows["C2"]["error_code"] == "#N/A"
    assert rows["D2"]["boolean_value"] is True
    assert rows["E2"]["text_value"] == "2026-08-30"
    assert rows["E2"]["value_kind"] == "date_text"
    assert rows["F2"]["decimal_value"] == Decimal(100)
    assert rows["G2"]["conversion_status"] == "missing_value"
    assert rows["H2"]["conversion_status"] == "null"
    assert rows["I2"]["formula_state"] == "null"
    assert rows["I2"]["value_origin"] == "formula_cache"
    assert rows["A2"]["source_path"] == "xl/worksheets/sheet1.xml#A2"
    assert rows["A2"]["row_index"] == 2
    assert rows["A2"]["column_index"] == 1


def test_inline_empty_strings_false_and_styled_serials_are_preserved() -> None:
    payload = _payload(
        '<c r="J2" t="inlineStr"><is/></c><c r="K2" t="b"><v>0</v></c><c r="L2" s="14"><v>45000</v></c>'
    )
    rows = {
        row["coordinate"]: row
        for row in next(
            iter_workbook_silver_batches(payload, _receipt(payload))
        ).to_pylist()
    }
    assert (rows["J2"]["text_value"], rows["J2"]["conversion_status"]) == (
        "",
        "preserved",
    )
    assert rows["K2"]["boolean_value"] is False
    assert rows["L2"]["decimal_value"] == Decimal(45000)
    assert rows["L2"]["style_index"] == 14
    assert rows["L2"]["value_kind"] == "number"


@pytest.mark.parametrize(
    ("cell_type", "value", "status"),
    [
        ("n", "NaN", "invalid"),
        ("n", "0.1234567891", "unrepresentable"),
        ("b", "2", "invalid"),
        ("future", "opaque", "unsupported_type"),
        ("n", "  ", "blank"),
    ],
)
def test_invalid_or_unsupported_values_are_not_lost(
    cell_type: str, value: str, status: str
) -> None:
    payload = _payload(f'<c r="J2" t="{cell_type}"><v>{value}</v></c>')
    result = next(
        iter_workbook_silver_batches(payload, _receipt(payload))
    ).to_pylist()[-1]
    assert result["raw_value"] == value
    assert result["conversion_status"] == status


def test_batches_do_not_change_cell_values() -> None:
    payload = _payload()
    receipt = _receipt(payload)
    one = list(iter_workbook_silver_batches(payload, receipt, rows_per_batch=1))
    many = list(
        iter_workbook_silver_batches(payload, receipt, rows_per_batch=100)
    )
    assert [row for batch in one for row in batch.to_pylist()] == [
        row for batch in many for row in batch.to_pylist()
    ]
    assert pa.Table.from_batches(many[:1]).num_rows == 10


def test_extreme_exponents_remain_native_without_conversion_failure() -> None:
    payload = _payload('<c r="J2" t="n"><v>1e999999999999999999999</v></c>')
    result = next(
        iter_workbook_silver_batches(payload, _receipt(payload))
    ).to_pylist()[-1]
    assert result["conversion_status"] == "unrepresentable"
    assert result["raw_value"] == "1e999999999999999999999"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1e999999", "unrepresentable"),
        ("1e-999999", "unrepresentable"),
        ("0e-999999", "converted"),
        (".5", "converted"),
        ("1.", "converted"),
    ],
)
def test_numeric_exponent_bounds_are_checked_before_arrow(
    value: str, expected: str
) -> None:
    payload = _payload(f'<c r="J2" t="n"><v>{value}</v></c>')
    result = next(
        iter_workbook_silver_batches(payload, _receipt(payload))
    ).to_pylist()[-1]
    assert result["conversion_status"] == expected


def test_disabled_decimal_traps_do_not_admit_nonfinite_values() -> None:
    payload = _payload('<c r="J2" t="n"><v>1e999999999999999999999</v></c>')
    with localcontext() as context:
        context.traps[InvalidOperation] = False
        result = next(
            iter_workbook_silver_batches(payload, _receipt(payload))
        ).to_pylist()[-1]
    assert result["conversion_status"] == "unrepresentable"


@pytest.mark.parametrize("coordinate", ["A0", "XFE1", "A1048577"])
def test_invalid_cell_coordinates_fail(coordinate: str) -> None:
    payload = _payload(f'<c r="{coordinate}"><v>1</v></c>')
    with pytest.raises(ValueError, match="coordinate"):
        next(iter_workbook_silver_batches(payload, _receipt(payload)))


def test_receipt_mismatch_and_invalid_bounds_fail_before_output() -> None:
    payload = _payload()
    with pytest.raises(ValueError, match="source bytes"):
        next(iter_workbook_silver_batches(payload, _receipt(b"different")))
    with pytest.raises(ValueError, match="batch"):
        next(
            iter_workbook_silver_batches(
                payload, _receipt(payload), rows_per_batch=0
            )
        )


@given(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Zs")),
        max_size=60,
    )
)
def test_inline_text_is_not_interpreted_as_a_number_or_formula(
    value: str,
) -> None:
    payload = _payload(
        f'<c r="J2" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
    )
    result = next(
        iter_workbook_silver_batches(payload, _receipt(payload))
    ).to_pylist()[-1]
    assert result["text_value"] == value
    assert result["decimal_value"] is None
    assert result["value_origin"] == "literal"
