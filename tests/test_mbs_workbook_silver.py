"""All-sheet workbook typing uses synthetic source-native cells only."""

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZipInfo

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import AnyUrl

from global_medicines_atlas.mbs_p7_date_consistency import (
    classify_p7_cell_status,
    decide_p7_date_consistency,
)
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
        paths.update(
            sheet["path"].encode()
            for sheet in json.loads(batch.schema.metadata[b"workbook_sheets"])
        )
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


def test_combined_parquet_preserves_every_sheet_and_empty_sheet() -> None:
    payload = _payload()
    batches = list(iter_workbook_silver_batches(payload, _receipt(payload)))
    table = pa.Table.from_batches(batches)
    rows = table.to_pylist()
    assert {row["sheet_name"] for row in rows} == {"Sheet1", "Sheet2", "Sheet3"}
    assert table.schema.metadata is not None
    manifest = json.loads(table.schema.metadata[b"workbook_sheets"])
    assert [sheet["name"] for sheet in manifest] == [
        "Sheet1",
        "Sheet2",
        "Sheet3",
        "Sheet4",
    ]
    assert manifest[-1]["cell_count"] == 0
    assert all(
        batch.schema.equals(table.schema, check_metadata=True)
        for batch in batches
    )
    output = BytesIO()
    pq.write_table(table, output)
    restored = pq.read_table(BytesIO(output.getvalue()))
    assert restored.equals(table, check_metadata=True)


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


def _p7_consistency_profile(
    *,
    statuses: dict[str, int] | None = None,
    lexical: dict[str, int] | None = None,
    source_sha256: str = (
        "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
    ),
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_sha256": source_sha256,
        "source_byte_count": 87727,
        "date_order_selected": False,
        "source_values_emitted": False,
        "by_field": {
            "BenefitStartDate": {
                "ambiguous_calendar_order": 310,
                "unique_calendar_date": 10,
            },
            "DescriptionStartDate": {
                "ambiguous_calendar_order": 310,
                "unique_calendar_date": 8,
                "unique_dmy_calendar_date": 2,
            },
            "FeeStartDate": {
                "ambiguous_calendar_order": 262,
                "unique_calendar_date": 56,
                "unique_dmy_calendar_date": 2,
            },
            "ItemStartDate": statuses
            or {
                "ambiguous_calendar_order": 312,
                "unique_calendar_date": 8,
            },
        },
        "lexical_profile_by_field": {
            **{
                field: {"dd_mm_yyyy_dotted": 320}
                for field in (
                    "BenefitStartDate",
                    "DescriptionStartDate",
                    "FeeStartDate",
                )
            },
            "ItemStartDate": lexical or {"dd_mm_yyyy_dotted": 320},
        },
    }


def test_p7_dmy_consistency_selects_exact_copy_internal_inference() -> None:
    source_sha256 = str(_p7_consistency_profile()["source_sha256"])
    decision = decide_p7_date_consistency(
        _p7_consistency_profile(), expected_source_sha256=source_sha256
    )

    assert decision["selected_profile"] == "mbs-dmy"
    assert decision["evidence_counts"]["unique_dmy_calendar_date"] == 4
    assert decision["date_fields_with_populated_values"] == [
        "BenefitStartDate",
        "DescriptionStartDate",
        "FeeStartDate",
        "ItemStartDate",
    ]
    assert decision["department_provenance_or_attestation"] == "not_established"
    assert decision["scope"] == {
        "source_sha256": source_sha256,
        "other_workbooks": False,
        "other_mbs_eras": False,
        "domain_meaning": False,
    }
    assert decision["source_values_emitted"] is False


@pytest.mark.parametrize(
    ("statuses", "lexical", "expected_digest"),
    [
        ({"unique_mdy_calendar_date": 1}, {"dd_mm_yyyy_dotted": 1}, None),
        ({"invalid": 1}, {"dd_mm_yyyy_dotted": 1}, None),
        ({"unsupported_serial_date": 1}, {}, None),
        ({"formula_unresolved": 1}, {"dd_mm_yyyy_dotted": 1}, None),
        ({"source_error": 1}, {}, None),
        ({"ambiguous_calendar_order": 2}, {"other_text_profile": 2}, None),
        (
            {"unique_dmy_calendar_date": 1},
            {"dd_mm_yyyy_dotted": 1},
            "wrong-digest",
        ),
    ],
)
def test_p7_dmy_consistency_abstains_on_negative_controls(
    statuses: dict[str, int],
    lexical: dict[str, int],
    expected_digest: str | None,
) -> None:
    profile = _p7_consistency_profile(statuses=statuses, lexical=lexical)
    digest = expected_digest or str(profile["source_sha256"])

    decision = decide_p7_date_consistency(
        profile, expected_source_sha256=digest
    )

    assert decision["selected_profile"] is None


def test_p7_dmy_consistency_needs_at_least_one_dmy_only_value() -> None:
    profile = _p7_consistency_profile()
    by_field = profile["by_field"]
    assert isinstance(by_field, dict)
    by_field["DescriptionStartDate"] = {"ambiguous_calendar_order": 320}
    by_field["FeeStartDate"] = {"ambiguous_calendar_order": 320}

    decision = decide_p7_date_consistency(
        profile, expected_source_sha256=str(profile["source_sha256"])
    )

    assert decision["selected_profile"] is None
    assert decision["selection_status"] == "unresolved"


@pytest.mark.parametrize(
    ("cell_type", "formula_state", "display_value", "present", "expected"),
    [
        ("e", "missing_field", None, ["display_value"], "source_error"),
        ("s", "formula", None, ["display_value"], "formula_unresolved"),
        ("s", "missing_field", None, ["display_value"], "null"),
        ("s", "missing_field", None, [], "missing_value"),
    ],
)
def test_p7_cell_state_precedes_null_display_value(
    cell_type: str,
    formula_state: str,
    display_value: str | None,
    present: list[str],
    expected: str,
) -> None:
    assert (
        classify_p7_cell_status({
            "cell_type": cell_type,
            "formula_state": formula_state,
            "display_value": display_value,
            "present_properties": present,
        })
        == expected
    )


@pytest.mark.parametrize("field", ["ItemStartDate", "FeeStartDate"])
def test_p7_dmy_consistency_rejects_missing_or_truncated_field_inventory(
    field: str,
) -> None:
    profile = _p7_consistency_profile()
    by_field = profile["by_field"]
    assert isinstance(by_field, dict)
    if field == "FeeStartDate":
        del by_field[field]
    else:
        field_counts = by_field[field]
        assert isinstance(field_counts, dict)
        field_counts["ambiguous_calendar_order"] -= 1

    decision = decide_p7_date_consistency(
        profile, expected_source_sha256=str(profile["source_sha256"])
    )

    assert decision["selected_profile"] is None
    assert decision["selection_status"] == "unresolved"


def test_p7_dmy_consistency_requires_one_profile_across_populated_fields() -> (
    None
):
    profile = _p7_consistency_profile()
    by_field = profile["by_field"]
    lexical_by_field = profile["lexical_profile_by_field"]
    assert isinstance(by_field, dict)
    assert isinstance(lexical_by_field, dict)
    by_field["FeeStartDate"] = {
        "ambiguous_calendar_order": 3,
        "unique_dmy_calendar_date": 1,
    }
    lexical_by_field["FeeStartDate"] = {"other_text_profile": 4}

    decision = decide_p7_date_consistency(
        profile, expected_source_sha256=str(profile["source_sha256"])
    )

    assert decision["selected_profile"] is None
