"""Domain types supplement native workbook evidence without guessing."""

import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from scripts import qualify_australian_legacy_payload as cli
from test_mbs_workbook_domain import fixture
from test_mbs_workbook_silver import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic receipt
)

from global_medicines_atlas.adapters.au_mbs_workbook import parse_mbs_workbook
from global_medicines_atlas.mbs_workbook_values import (
    iter_workbook_value_batches,
    profile_workbook_values,
)


def payload_with(cells: str) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(fixture())) as source, ZipFile(output, "w") as target:
        for entry in source.infolist():
            value = source.read(entry)
            if entry.filename == "xl/worksheets/sheet1.xml":
                value = value.replace(
                    b"</row></sheetData>",
                    cells.encode() + b"</row></sheetData>",
                )
            target.writestr(entry, value)
    return output.getvalue()


def rows_for(payload: bytes, **kwargs):
    return {
        row["coordinate"]: row
        for batch in iter_workbook_value_batches(
            payload, _receipt(payload), **kwargs
        )
        for row in batch.to_pylist()
        if row["sheet_name"] == "Sheet1"
    }


def test_identifiers_dates_money_and_annotations_keep_native_values() -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>01.07.2024</t></is></c><c r="V2"><v>1e2</v></c>'
    )
    rows = rows_for(payload, date_format="mbs-dmy")
    assert rows["A2"]["domain_text"] == "00123"
    assert rows["A2"]["domain_decimal"] is None
    assert rows["C2"]["domain_date"] == date(2024, 7, 1)
    assert rows["V2"]["domain_decimal"] == Decimal(100)
    assert rows["V2"]["domain_currency"] == "AUD"
    assert rows["V2"]["raw_value"] == "1e2"
    assert rows["AO2"]["domain_text"] == "synthetic element"
    assert rows["AT2"]["domain_status"] == "missing_value"
    assert rows["A1"]["domain_status"] == "header"
    assert rows["AV2"]["domain_status"] == "unmapped"


def test_dates_need_explicit_profile_and_serials_are_never_guessed() -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>01.07.2024</t></is></c><c r="D2"><v>45000</v></c>'
    )
    rows = rows_for(payload)
    assert rows["C2"]["domain_status"] == "unsupported_format"
    assert rows["D2"]["domain_status"] == "unsupported_serial_date"
    assert rows["D2"]["domain_date"] is None


@pytest.mark.parametrize(
    ("cell", "encoding"),
    [
        ('t="inlineStr"><is><t>01.07.2024</t></is>', "two_two_four_dot"),
        ('t="inlineStr"><is><t>2024-07-01</t></is>', "four_two_two_hyphen"),
        ('t="inlineStr"><is><t>01/07/2024</t></is>', "two_two_four_slash"),
        ('t="inlineStr"><is><t>99.99.0000</t></is>', "two_two_four_dot"),
        ('t="inlineStr"><is><t> 01.07.2024</t></is>', "other_text"),
        (
            't="inlineStr"><is><t>\u0661\u0662.\u0660\u0667.\u0662\u0660\u0662\u0664</t></is>',
            "other_text",
        ),
        ('t="n"><v>45000</v>', "numeric_storage_uninterpreted"),
        ('t="b"><v>1</v>', "unsupported_storage"),
        ('t="e"><v>#VALUE!</v>', "source_error"),
        ('t="inlineStr"><is><t></t></is>', "empty_text"),
        ('t="str">', "missing_value"),
    ],
)
def test_date_encoding_observation_does_not_select_profile(
    cell: str, encoding: str
) -> None:
    payload = payload_with(f'<c r="C2" {cell}</c>')
    report = profile_workbook_values(payload, _receipt(payload))
    assert report["date_encoding_counts"][encoding] == 1
    assert report["date_profile"] is None
    assert report["semantic_promotion"] is False
    assert rows_for(payload)["C2"]["domain_date"] is None
    assert "01.07.2024" not in json.dumps(report)
    assert report == profile_workbook_values(payload, _receipt(payload))
    assert sum(report["date_encoding_counts"].values()) == sum(
        sum(counts.values())
        for counts in report["date_encodings_by_field"].values()
    )


def test_errors_boolean_storage_and_precision_loss_are_explicit() -> None:
    payload = payload_with(
        '<c r="W2" t="e"><v>#VALUE!</v></c><c r="X2" t="b"><v>1</v></c><c r="AL2" t="inlineStr"><is><t>1.0000000001</t></is></c>'
    )
    rows = rows_for(payload)
    assert rows["W2"]["domain_status"] == "source_error"
    assert rows["X2"]["domain_status"] == "unsupported_storage_type"
    assert rows["AL2"]["domain_status"] == "unrepresentable"
    assert rows["AL2"]["display_value"] == "1.0000000001"
    assert rows["AL2"]["domain_decimal"] is None


def test_cached_values_remain_caches_and_parquet_roundtrips() -> None:
    payload = payload_with('<c r="V2"><f>1+1</f><v>2</v></c>')
    table = pa.Table.from_batches(
        list(iter_workbook_value_batches(payload, _receipt(payload)))
    )
    rows = rows_for(payload)
    assert rows["V2"]["domain_decimal"] == Decimal(2)
    assert rows["V2"]["value_origin"] == "formula_cache"
    output = BytesIO()
    pq.write_table(table, output)
    assert pq.read_table(BytesIO(output.getvalue())).equals(
        table, check_metadata=True
    )


def test_unknown_date_profile_fails_before_output() -> None:
    payload = fixture()
    with pytest.raises(ValueError, match="date format"):
        next(
            iter_workbook_value_batches(
                payload, _receipt(payload), date_format="guess"
            )
        )


def test_null_empty_annotations_and_text_encoded_money() -> None:
    payload = payload_with(
        '<c r="B2"><v/></c><c r="AU2" t="inlineStr"><is/></c><c r="V2" t="inlineStr"><is><t>25.05</t></is></c><c r="AK2" t="inlineStr"><is><t>1+1</t></is></c>'
    )
    rows = rows_for(payload)
    assert rows["B2"]["domain_value_state"] == "null"
    assert rows["B2"]["domain_status"] == "null"
    assert rows["AU2"]["domain_text"] == ""  # ruff: ignore[compare-to-empty-string] -- distinct from null
    assert rows["AU2"]["domain_status"] == "preserved"
    assert rows["V2"]["domain_decimal"] == Decimal("25.05")
    assert rows["AK2"]["domain_text"] == "1+1"


def test_invalid_text_values_remain_native() -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>31.02.2024</t></is></c><c r="V2" t="inlineStr"><is><t>not money</t></is></c>'
    )
    rows = rows_for(payload, date_format="mbs-dmy")
    assert rows["C2"]["domain_status"] == "invalid"
    assert rows["C2"]["display_value"] == "31.02.2024"
    assert rows["V2"]["domain_status"] == "invalid"
    assert rows["V2"]["domain_decimal"] is None


def test_boolean_annotation_remains_literal_not_a_clinical_flag() -> None:
    payload = payload_with('<c r="AU2" t="b"><v>1</v></c>')
    rows = rows_for(payload)
    assert rows["AU2"]["domain_text"] == "1"
    assert rows["AU2"]["domain_value_type"] == "legacy_annotation"
    assert rows["AU2"]["domain_status"] == "preserved"


def test_conversion_profile_has_complete_denominators() -> None:
    payload = fixture()
    result = profile_workbook_values(payload, _receipt(payload))
    assert result["cells"] == 107
    assert sum(result["statuses"].values()) == 107
    assert result["by_field"]["ItemNum"]["preserved"] == 3
    assert result["source_error_cells"] == 2
    assert result["semantic_promotion"] is False


def test_hosted_workbook_qualifier_does_not_select_xml_date_profile(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>01.07.2024</t></is></c>'
    )
    monkeypatch.setattr(
        cli,
        "_arguments",
        lambda: SimpleNamespace(
            kind="p7-workbook",
            public_hf_workbook=True,
            source_uri=cli.PUBLIC_WORKBOOK_URI,
            retrieved_at="2026-08-30T00:00:00Z",
        ),
    )
    monkeypatch.setattr(cli, "acquire_hosted_workbook", lambda _client: payload)
    monkeypatch.setattr(
        cli, "_receipt", lambda *_args, **_kwargs: _receipt(payload)
    )
    monkeypatch.setattr(cli, "qualify_legacy_p7_workbook", parse_mbs_workbook)
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "1")
    cli.main()
    report = json.loads(capsys.readouterr().out)
    assert report["domain_value_profile"]["date_profile"] is None
    assert (
        report["domain_value_profile"]["by_field"]["ItemStartDate"][
            "unsupported_format"
        ]
        == 1
    )
