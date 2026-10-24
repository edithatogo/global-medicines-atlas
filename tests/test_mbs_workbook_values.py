"""Domain types supplement native workbook evidence without guessing."""

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from scripts import profile_mbs_p7_calendar_dates as calendar_cli
from scripts import qualify_australian_legacy_payload as cli
from test_mbs_workbook_domain import fixture
from test_mbs_workbook_silver import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic receipt
)

from global_medicines_atlas import mbs_workbook_values as values_module
from global_medicines_atlas.adapters.au_mbs_workbook import parse_mbs_workbook
from global_medicines_atlas.mbs_p7_calendar_profile import (
    profile_p7_calendar_dates,
)
from global_medicines_atlas.mbs_workbook_domain import (
    iter_workbook_domain_batches,
)
from global_medicines_atlas.mbs_workbook_values import (
    iter_workbook_value_batches,
    profile_workbook_values,
    workbook_date_for_comparison,
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


def p7_calendar_profile_evidence(payload: bytes, receipt) -> bytes:
    by_field = defaultdict(Counter)
    for batch in iter_workbook_domain_batches(payload, receipt):
        for row in batch.to_pylist():
            name = row["mapping_field"]
            field = values_module._FIELDS.get(name)
            if (
                row["row_kind"] == "header"
                or not field
                or field.value_type != "source_date"
            ):
                continue
            value = row["display_value"]
            if value is None:
                status = (
                    "null"
                    if "display_value" in row["present_properties"]
                    else "missing_value"
                )
            elif row["cell_type"] == "e":
                status = "source_error"
            elif row["cell_type"] in {None, "n"}:
                status = "unsupported_serial_date"
            else:
                status = values_module._calendar_profile_status(value)
            by_field[name][status] += 1
    report = {
        "kind": "mbs_p7_unique_calendar_date_profile",
        "profile": {
            "schema_version": 2,
            "rule": "unique_valid_calendar_date_per_value_no_order_selected",
            "source_sha256": receipt.payload.sha256,
            "source_byte_count": receipt.payload.byte_count,
            "date_order_selected": False,
            "source_values_emitted": False,
            "by_field": {
                name: dict(sorted(counts.items()))
                for name, counts in sorted(by_field.items())
            },
        },
    }
    return json.dumps(report, sort_keys=True, separators=(",", ":")).encode()


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


def test_aggregate_calendar_profile_counts_without_emitting_values() -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>15.07.2024</t></is></c>'
        '<c r="C3" t="inlineStr"><is><t>05.06.2024</t></is></c>'
        '<c r="C4" t="inlineStr"><is><t>06.06.2024</t></is></c>'
        '<c r="C5" t="inlineStr"><is><t>31.02.2024</t></is></c>'
        '<c r="C6"><v>45000</v></c>'
        '<c r="C7" t="inlineStr"><is><t>07.15.2024</t></is></c>'
    )
    profile = profile_p7_calendar_dates(payload, _receipt(payload))

    assert profile["source_sha256"] == sha256(payload).hexdigest()
    assert profile["schema_version"] == 2
    assert profile["date_order_selected"] is False
    assert profile["source_values_emitted"] is False
    assert profile["by_field"]["ItemStartDate"] == {
        "ambiguous_calendar_order": 1,
        "invalid": 1,
        "unique_calendar_date": 1,
        "unique_dmy_calendar_date": 1,
        "unique_mdy_calendar_date": 1,
        "unsupported_serial_date": 1,
    }
    assert "15.07.2024" not in json.dumps(profile)


def test_aggregate_calendar_profile_classifies_missing_null_error_and_text() -> (
    None
):
    payload = payload_with(
        '<c r="C3"/> '
        '<c r="C4"><v/></c>'
        '<c r="C5" t="e"><v>#N/A</v></c>'
        '<c r="C6" t="inlineStr"><is><t>not a date</t></is></c>'
    )

    profile = profile_p7_calendar_dates(payload, _receipt(payload))

    assert profile["by_field"]["ItemStartDate"] == {
        "invalid": 1,
        "missing_value": 1,
        "null": 1,
        "source_error": 1,
    }


def test_calendar_profile_cli_emits_only_pinned_aggregate_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>15.07.2024</t></is></c>'
        '<c r="C3" t="inlineStr"><is><t>05.06.2024</t></is></c>'
    )

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        calendar_cli.httpx, "Client", lambda **_kwargs: Client()
    )
    monkeypatch.setattr(
        calendar_cli, "acquire_hosted_workbook", lambda _client: payload
    )
    monkeypatch.setattr(calendar_cli, "LEGACY_P7_BYTES", len(payload))
    monkeypatch.setattr(
        calendar_cli, "LEGACY_P7_SHA256", sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profile_mbs_p7_calendar_dates.py",
            "--output",
            str(tmp_path / "profile.json"),
        ],
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "f" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")

    calendar_cli.main()
    report = json.loads((tmp_path / "profile.json").read_text())

    assert report["profile"]["by_field"]["ItemStartDate"] == {
        "ambiguous_calendar_order": 1,
        "unique_dmy_calendar_date": 1,
    }
    assert report["profile"]["source_values_emitted"] is False
    assert "15.07.2024" not in json.dumps(report)


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
        ('t="d"><v>2024-07-01</v>', "native_date_storage_uninterpreted"),
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


@pytest.mark.parametrize(
    ("value", "compatibility"),
    [
        ("15.07.2024", "dmy_only"),
        ("07.15.2024", "mdy_only"),
        ("05.06.2024", "both"),
        ("31.02.2024", "neither"),
    ],
)
def test_dotted_date_calendar_compatibility_is_value_free_and_unselected(
    value: str, compatibility: str
) -> None:
    payload = payload_with(
        f'<c r="C2" t="inlineStr"><is><t>{value}</t></is></c>'
    )
    report = profile_workbook_values(payload, _receipt(payload))
    assert report["date_order_compatibility_counts"] == {compatibility: 1}
    assert report["date_profile"] is None
    assert report["semantic_promotion"] is False
    assert value not in json.dumps(report)


def test_exact_p7_profile_interprets_only_individually_unique_text_dates(
    monkeypatch,
) -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>15.07.2024</t></is></c>'
        '<c r="D2" t="inlineStr"><is><t>05.06.2024</t></is></c>'
        '<c r="T2" t="inlineStr"><is><t>01.01.2024</t></is></c>'
    )
    receipt = _receipt(payload)
    monkeypatch.setattr(
        values_module, "_P7_SOURCE_SHA256", receipt.payload.sha256
    )
    evidence = p7_calendar_profile_evidence(payload, receipt)
    monkeypatch.setattr(
        values_module, "_P7_DATE_PROFILE_SHA256", sha256(evidence).hexdigest()
    )
    rows = rows_for(
        payload,
        date_format="mbs-dmy",
        calendar_profile_evidence=evidence,
        calendar_profile_sha256=sha256(evidence).hexdigest(),
    )

    assert rows["C2"]["interpretation_state"] == "interpreted"
    assert rows["C2"]["domain_date"] == date(2024, 7, 15)
    assert (
        rows["C2"]["semantic_evidence_sha256"] == sha256(evidence).hexdigest()
    )
    assert rows["D2"]["interpretation_state"] == "native_unresolved"
    assert rows["D2"]["domain_date"] is None
    assert rows["T2"]["interpretation_state"] == "interpreted"
    assert rows["T2"]["domain_date"] == date(2024, 1, 1)
    assert workbook_date_for_comparison(rows["C2"]) == date(2024, 7, 15)
    for coordinate in ("D2",):
        with pytest.raises(ValueError, match="interpreted"):
            workbook_date_for_comparison(rows[coordinate])


def test_p7_profile_mismatch_and_other_source_fail_closed(monkeypatch) -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>15.07.2024</t></is></c>'
    )
    receipt = _receipt(payload)
    monkeypatch.setattr(
        values_module, "_P7_SOURCE_SHA256", receipt.payload.sha256
    )
    evidence = json.loads(p7_calendar_profile_evidence(payload, receipt))
    evidence["profile"]["by_field"]["ItemStartDate"][
        "unique_dmy_calendar_date"
    ] = 99
    bad_counts = json.dumps(evidence).encode()
    monkeypatch.setattr(
        values_module, "_P7_DATE_PROFILE_SHA256", sha256(bad_counts).hexdigest()
    )
    with pytest.raises(ValueError, match="counts differ"):
        list(
            iter_workbook_value_batches(
                payload,
                receipt,
                calendar_profile_evidence=bad_counts,
                calendar_profile_sha256=sha256(bad_counts).hexdigest(),
            )
        )
    monkeypatch.setattr(values_module, "_P7_SOURCE_SHA256", "0" * 64)
    other_evidence = p7_calendar_profile_evidence(payload, receipt)
    monkeypatch.setattr(
        values_module,
        "_P7_DATE_PROFILE_SHA256",
        sha256(other_evidence).hexdigest(),
    )
    with pytest.raises(ValueError, match="source identity"):
        list(
            iter_workbook_value_batches(
                payload,
                receipt,
                calendar_profile_evidence=other_evidence,
                calendar_profile_sha256=sha256(other_evidence).hexdigest(),
            )
        )


def test_unique_cached_formula_date_remains_unresolved(monkeypatch) -> None:
    payload = payload_with(
        '<c r="C2" t="str"><f>DATE(2024,7,15)</f><v>15.07.2024</v></c>'
    )
    receipt = _receipt(payload)
    monkeypatch.setattr(
        values_module, "_P7_SOURCE_SHA256", receipt.payload.sha256
    )
    evidence = p7_calendar_profile_evidence(payload, receipt)
    monkeypatch.setattr(
        values_module, "_P7_DATE_PROFILE_SHA256", sha256(evidence).hexdigest()
    )
    row = rows_for(
        payload,
        calendar_profile_evidence=evidence,
        calendar_profile_sha256=sha256(evidence).hexdigest(),
    )["C2"]
    assert row["domain_date"] is None
    assert row["interpretation_state"] == "native_unresolved"
    with pytest.raises(ValueError, match="interpreted"):
        workbook_date_for_comparison(row)


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


def test_official_xml_date_spec_does_not_select_legacy_workbook_profile() -> (
    None
):
    root = Path(__file__).resolve().parents[1]
    review = json.loads(
        (
            root / "quality/qualifications/"
            "mbs-workbook-date-source-doc-review-20260929.json"
        ).read_text(encoding="utf-8")
    )
    assert review["xml_date_format_documented"] == "DD.MM.YYYY"
    assert review["legacy_p7_workbook_date_format_documented"] is False
    assert review["date_profile"] is None
    assert review["semantic_promotion"] is False
    request = (
        root
        / "conductor/tracks/australian_health_source_consolidation_20260829/"
        "mbs-workbook-date-convention-request.md"
    ).read_text(encoding="utf-8")
    assert "MBS Online replied on 2026-10-13" in request
    assert "First follow-up sent 2026-10-17" in request
    assert "does not list the P7 workbook" in request
    assert "date convention" in request
    assert "remain unconfirmed" in request
    assert "1,276 date cells" in request
    assert "four valid only under day-month-year" in request
    assert "No cell values are included" in request
    outreach = json.loads(
        (
            root
            / "quality/qualifications/provider-outreach-receipts-20260929.json"
        ).read_text(encoding="utf-8")
    )
    message = next(
        item
        for item in outreach["messages"]
        if item["source_id"] == "au-mbs-p7-legacy-workbook"
    )
    assert message["gmail_message_id"] == "1a0e932e4152a72e"
    assert message["recipient"] == "enquiries@health.gov.au"
    assert message["source_payloads_attached"] is False
    assert message["cell_values_included"] is False


def test_p7_source_owner_follow_up_does_not_select_workbook_date_profile() -> (
    None
):
    root = Path(__file__).resolve().parents[1]
    clarification = json.loads(
        (
            root
            / "quality/qualifications/mbs-workbook-date-source-owner-clarification-20261017.json"
        ).read_text(encoding="utf-8")
    )
    assert clarification["source_id"] == "au-mbs-p7-legacy-workbook"
    assert clarification["correspondence"]["response_message_id"] == (
        "1a137984cf9a7186"
    )
    follow_ups = clarification["correspondence"]["follow_ups"]
    assert [item["message_id"] for item in follow_ups] == [
        "1a1475b8396d9dc1",
        "1a14763bf92064a6",
    ]
    assert follow_ups[0]["official_page_lists_workbook"] is False
    assert follow_ups[1]["locator_type"] == "pinned_donor_archive_copy"
    assert (
        "original inquiry incorrectly stated"
        in clarification["correspondence"][
            "original_inquiry_locator_correction"
        ]
    )
    assert all(item["source_payload_attached"] is False for item in follow_ups)
    assert all(item["cell_values_included"] is False for item in follow_ups)
    donor = clarification["donor_archive_locator"]
    assert donor["repository"] == "edithatogo/aus-health-data-scraper"
    assert donor["commit"] == "931da0b9b6ae3e3cec0743568abb71a50d62b7cf"
    assert (
        donor["path"] == "data/source/MBS - 2024.07 - Group P7 (Genetics).xlsx"
    )
    assert donor["bytes"] == 87727
    assert donor["sha256"] == clarification["source_sha256"]
    assert (
        clarification["qualification"]["exact_archived_copy_identified"] is True
    )
    assert (
        clarification["qualification"][
            "source_owner_confirmed_official_provenance"
        ]
        is False
    )
    assert clarification["qualification"]["date_convention_confirmed"] is False
    assert clarification["qualification"]["date_profile"] is None
    assert clarification["qualification"]["semantic_promotion"] is False


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
    typed = report["typed_candidate_package"]
    assert typed["rebuild_equal"] is True
    assert typed["typed_parquet_restore_verified"] is True
    assert typed["native_cell_parity_verified"] is True
    assert typed["temporary_derivatives_removed"] is True
    assert typed["date_profile"] is None
    assert report["p7_calendar_profile_evidence"] is None
    assert typed["output_admitted"] is False
    storage = report["storage_qualification"]
    assert storage["parquet_roundtrip_verified"] is True
    assert storage["publication_performed"] is False
    assert all(
        "header_candidates" not in sheet
        and "raw_value" not in json.dumps(sheet)
        and "display_value" not in json.dumps(sheet)
        for sheet in storage["sheets"]
    )
    assert "raw_value" not in json.dumps(report)
    assert "display_value" not in json.dumps(report)
    lineage = report["workbook_field_lineage"]
    assert lineage["qualification"] == "candidate_only"
    assert lineage["date_profile"] is None
    assert len(lineage["sheets"]) == 4
    assert "01.07.2024" not in json.dumps(lineage)
    assert (
        report["domain_value_profile"]["by_field"]["ItemStartDate"][
            "unsupported_format"
        ]
        == 1
    )


def test_p7_profile_evidence_is_loaded_only_for_exact_source() -> None:
    assert cli._p7_calendar_profile_evidence("a" * 64) == (None, None)
    evidence, digest = cli._p7_calendar_profile_evidence(cli.P7_SOURCE_SHA256)
    assert evidence is not None
    assert digest == cli.P7_CALENDAR_PROFILE_SHA256
    assert b'"date_order_selected":false' in evidence
    assert b'"source_values_emitted":false' in evidence


def test_p7_parsed_dates_remain_unresolved_for_temporal_consumers() -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>01.07.2024</t></is></c>'
    )
    row = rows_for(payload, date_format="mbs-dmy")["C2"]
    assert row["interpretation_state"] == "native_unresolved"
    assert row["display_value"] == "01.07.2024"
    assert row["domain_date"] == date(2024, 7, 1)
    with pytest.raises(ValueError, match="interpreted"):
        workbook_date_for_comparison(row)


def test_workbook_temporal_consumer_rejects_nondate_columns() -> None:
    with pytest.raises(ValueError, match="not a source date"):
        workbook_date_for_comparison(rows_for(fixture())["A2"])


def test_p7_value_era_rules_bind_exact_source_without_selecting_dates() -> None:
    root = Path(__file__).resolve().parents[1]
    rules_path = (
        root / "quality/qualifications/mbs-p7-value-era-rules-20261024.json"
    )
    rules = json.loads(rules_path.read_text(encoding="utf-8"))

    assert rules["source"]["source_id"] == "au-mbs-p7-legacy-workbook"
    assert rules["source"]["sha256"] == (
        "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
    )
    assert rules["source"]["byte_count"] == 87727
    assert rules["rules"]["dates"]["selected_profile"] is None
    assert rules["rules"]["dates"]["calendar_compatibility"] == {
        "both_dmy_and_mdy_valid": 1276,
        "dmy_only": 4,
        "mdy_only": 0,
        "source_values_emitted": False,
        "profile_selected": False,
    }
    assert rules["rules"]["dates"]["consumer_state"] == "native_unresolved"
    assert rules["rules"]["dates"]["temporal_comparison_enabled"] is False
    assert rules["rules"]["benefits"]["formula_cells"] == 4
    assert rules["rules"]["benefits"]["error_cells"] == 2
    assert (
        rules["rules"]["schema_eras"]["historical_workbook"]
        != (rules["rules"]["schema_eras"]["current_xml"])
    )
    assert rules["gates"]["all_13742_cells_remain_native_unresolved"] is True
    assert rules["gates"]["date_profile_selected"] is False

    for evidence in rules["evidence"].values():
        evidence_path = root / evidence["path"]
        assert (
            sha256(evidence_path.read_bytes()).hexdigest() == evidence["sha256"]
        )

    qualification_path = (
        root / rules["evidence"]["typed_candidate_qualification"]["path"]
    )
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
    typed = qualification["typed_candidate_package"]
    assert typed["coverage"]["native_cells"] == 13742
    assert typed["coverage"]["unresolved_cells"] == 13742
    assert typed["coverage"]["formula_cells"] == 4
    assert typed["coverage"]["error_cells"] == 2
    assert typed["date_profile"] is None
    assert typed["semantic_promotion"] is False


def test_exact_main_p7_calendar_profile_is_digest_bound() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "quality/qualifications/mbs-p7-calendar-profile-20261024-40088209026.json"
    )
    evidence = path.read_bytes()
    assert sha256(evidence).hexdigest() == values_module._P7_DATE_PROFILE_SHA256
    report = json.loads(evidence)
    profile = report["profile"]
    assert report["kind"] == "mbs_p7_unique_calendar_date_profile"
    assert profile["schema_version"] == 2
    assert profile["source_sha256"] == values_module._P7_SOURCE_SHA256
    assert profile["date_order_selected"] is False
    assert profile["source_values_emitted"] is False
    assert (
        sum(
            counts.get("unique_calendar_date", 0)
            + counts.get("unique_dmy_calendar_date", 0)
            + counts.get("unique_mdy_calendar_date", 0)
            for counts in profile["by_field"].values()
        )
        == 86
    )


def test_p7_profile_rejects_digest_without_evidence() -> None:
    payload = fixture()
    with pytest.raises(ValueError, match="digest has no evidence"):
        list(
            iter_workbook_value_batches(
                payload,
                _receipt(payload),
                calendar_profile_sha256="a" * 64,
            )
        )


@pytest.mark.parametrize("evidence", [b"{", b"[]"])
def test_p7_profile_rejects_malformed_document(
    evidence: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = fixture()
    receipt = _receipt(payload)
    monkeypatch.setattr(
        values_module, "_P7_SOURCE_SHA256", receipt.payload.sha256
    )
    monkeypatch.setattr(
        values_module, "_P7_DATE_PROFILE_SHA256", sha256(evidence).hexdigest()
    )

    with pytest.raises(ValueError, match="evidence is invalid"):
        list(
            iter_workbook_value_batches(
                payload,
                receipt,
                calendar_profile_evidence=evidence,
                calendar_profile_sha256=sha256(evidence).hexdigest(),
            )
        )


def test_p7_profile_rejects_wrong_qualification_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = fixture()
    receipt = _receipt(payload)
    monkeypatch.setattr(
        values_module, "_P7_SOURCE_SHA256", receipt.payload.sha256
    )
    report = json.loads(p7_calendar_profile_evidence(payload, receipt))
    report["profile"]["date_order_selected"] = True
    evidence = json.dumps(report, separators=(",", ":")).encode()
    monkeypatch.setattr(
        values_module, "_P7_DATE_PROFILE_SHA256", sha256(evidence).hexdigest()
    )

    with pytest.raises(ValueError, match="does not qualify"):
        list(
            iter_workbook_value_batches(
                payload,
                receipt,
                calendar_profile_evidence=evidence,
                calendar_profile_sha256=sha256(evidence).hexdigest(),
            )
        )


@pytest.mark.parametrize(
    ("value", "status"),
    [
        ("2024-07-15", "invalid"),
        ("07.15.2024", "unique_mdy_calendar_date"),
        ("15.07.2024", "unique_dmy_calendar_date"),
        ("05.06.2024", "ambiguous_calendar_order"),
        ("31.02.2024", "invalid"),
    ],
)
def test_calendar_status_handles_non_dotted_and_each_date_order(
    value: str, status: str
) -> None:
    assert values_module._calendar_profile_status(value) == status


def test_profile_count_validation_accounts_for_null_missing_error_and_serial() -> (
    None
):
    payload = payload_with(
        '<c r="C10"/><c r="C11"><v/></c>'
        '<c r="C12" t="e"><v>#N/A</v></c><c r="C13"><v>45000</v></c>'
    )
    receipt = _receipt(payload)
    evidence = p7_calendar_profile_evidence(payload, receipt)
    report = json.loads(evidence)

    assert values_module._profile_counts_match(
        payload, receipt, report["profile"]
    )
    assert report["profile"]["by_field"]["ItemStartDate"] == {
        "missing_value": 1,
        "null": 1,
        "source_error": 1,
        "unsupported_serial_date": 1,
    }


def test_qualified_date_returns_unresolved_for_null_cell() -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>15.07.2024</t></is></c>'
    )
    row = rows_for(payload)["C2"]
    row["display_value"] = None
    assert values_module._qualified_profile_date(row, {}, "a" * 64) == {}


def test_profile_evidence_missing_after_validation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = fixture()
    monkeypatch.setattr(
        values_module, "_validated_p7_date_profile", lambda *_args: (None, None)
    )

    with pytest.raises(ValueError, match="evidence is missing"):
        list(
            iter_workbook_value_batches(
                payload,
                _receipt(payload),
                calendar_profile_evidence=b"qualified evidence",
                calendar_profile_sha256="a" * 64,
            )
        )
