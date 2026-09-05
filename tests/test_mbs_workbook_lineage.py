"""Workbook lineage is complete, value-free and batch-independent."""

import hashlib
import json

import pytest
from test_mbs_workbook_domain import fixture
from test_mbs_workbook_silver import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic fixture
)
from test_mbs_workbook_values import payload_with

from global_medicines_atlas import mbs_workbook_lineage as module
from global_medicines_atlas.mbs_workbook_lineage import (
    WorkbookFieldLineageReport,
    build_workbook_field_lineage,
)
from global_medicines_atlas.mbs_workbook_values import (
    iter_workbook_value_batches,
)


def test_complete_column_lineage_preserves_sheet_and_unlabelled_denominators():
    payload = fixture()
    receipt = _receipt(payload)
    report = build_workbook_field_lineage(payload, receipt, rows_per_batch=1)
    assert report == build_workbook_field_lineage(payload, receipt)
    assert report.source_sha256 == receipt.payload.sha256
    assert report.receipt_sha256 == receipt.digest()
    assert report.cell_count == 107
    assert len(report.sheets) == 4
    assert sum(field.cell_count for field in report.fields) == 107
    assert sum(field.header_count for field in report.fields) == 97
    unlabelled = [
        field for field in report.fields if field.native_header is None
    ]
    assert len(unlabelled) == 2
    assert all(field.mapping_target == "unmapped" for field in unlabelled)
    assert "synthetic element" not in report.model_dump_json()
    assert "00123" not in report.model_dump_json()
    assert report.date_profile is None
    assert report.qualification == "candidate_only"


def test_formula_and_date_states_are_counted_without_interpretation():
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>01.07.2024</t></is></c><c r="V2"><f>1+1</f><v>2</v></c>'
    )
    report = build_workbook_field_lineage(payload, _receipt(payload))
    fields = {
        (field.sheet_name, field.column): field for field in report.fields
    }
    assert fields["Sheet1", "C"].statuses == (
        ("header", 1),
        ("unsupported_format", 1),
    )
    assert fields["Sheet1", "V"].formula_count == 1
    assert fields["Sheet1", "V"].statuses == (("converted", 1), ("header", 1))
    assert "01.07.2024" not in report.model_dump_json()
    assert "1+1" not in report.model_dump_json()


@pytest.mark.parametrize("drift", [True, False])
def test_original_header_and_sheet_guards_remain(drift):
    payload = fixture(drift=drift, sheet_drift=not drift)
    with pytest.raises(ValueError, match="profile"):
        build_workbook_field_lineage(payload, _receipt(payload))


@pytest.mark.parametrize("limit", [0, True, 4097])
def test_invalid_batch_limits_fail(limit):
    payload = fixture()
    with pytest.raises(ValueError, match="batch"):
        build_workbook_field_lineage(
            payload, _receipt(payload), rows_per_batch=limit
        )


def test_report_json_roundtrip_and_digest_tamper():
    payload = fixture()
    report = build_workbook_field_lineage(payload, _receipt(payload))
    assert type(report).model_validate_json(report.model_dump_json()) == report
    document = json.loads(report.model_dump_json())
    document["cell_count"] += 1
    with pytest.raises(ValueError, match="total differs"):
        type(report).model_validate(document)


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_sheet",
        "native_header",
        "mapping",
        "cell_count",
        "status_order",
        "status_sum",
        "unknown_status",
        "sheet_shape",
        "duplicate_path",
        "duplicate_column",
        "sheet_path",
        "header_count",
        "digest",
        "dimension",
    ],
)
def test_resigned_reports_cannot_change_contracts(mutation):  # ruff: ignore[too-many-branches] -- explicit corruption controls
    payload = fixture()
    document = json.loads(
        build_workbook_field_lineage(
            payload, _receipt(payload)
        ).model_dump_json()
    )
    field = document["fields"][0]
    if mutation == "unknown_sheet":
        field["sheet_name"] = "Unknown"
    elif mutation == "native_header":
        field["native_header"] = "Changed"
    elif mutation == "mapping":
        field["mapping_target"] = "medicines"
    elif mutation == "cell_count":
        field["cell_count"] = 0
    elif mutation == "status_order":
        field["statuses"] = list(reversed(field["statuses"]))
    elif mutation == "status_sum":
        field["statuses"][0][1] += 1
    elif mutation == "unknown_status":
        field["statuses"][0][0] = "qualified"
    elif mutation == "sheet_shape":
        document["sheets"][0]["dimension"] = "A1:B2"
    elif mutation == "duplicate_path":
        document["sheets"][1]["path"] = document["sheets"][0]["path"]
    elif mutation == "duplicate_column":
        document["fields"].append(dict(field))
    elif mutation == "sheet_path":
        field["sheet_path"] = "different"
    elif mutation == "header_count":
        field["header_count"] = 0
        field["statuses"] = [["preserved", field["cell_count"]]]
    elif mutation == "dimension":
        document["dimension"] = "regulatory"
    if mutation != "digest":
        document["report_sha256"] = hashlib.sha256(
            json.dumps(
                {
                    key: value
                    for key, value in document.items()
                    if key != "report_sha256"
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()
    else:
        document["report_sha256"] = "0" * 64
    with pytest.raises(
        ValueError, match=r"differ|duplicated|Input should|unknown workbook"
    ):
        WorkbookFieldLineageReport.model_validate(document)


@pytest.mark.parametrize("limit", [0, True, 4097, 1])
def test_column_accumulation_is_bounded(limit):
    payload = fixture()
    with pytest.raises(ValueError, match="column limit"):
        build_workbook_field_lineage(
            payload, _receipt(payload), max_columns=limit
        )


def test_explicit_date_profile_changes_digest_not_source_identity():
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>01.07.2024</t></is></c>'
    )
    receipt = _receipt(payload)
    unselected = build_workbook_field_lineage(payload, receipt)
    selected = build_workbook_field_lineage(
        payload, receipt, date_profile="mbs-dmy"
    )
    assert unselected.source_sha256 == selected.source_sha256
    assert unselected.receipt_sha256 == selected.receipt_sha256
    assert unselected.report_sha256 != selected.report_sha256
    before = next(
        field
        for field in unselected.fields
        if (field.sheet_name, field.column) == ("Sheet1", "C")
    )
    after = next(
        field
        for field in selected.fields
        if (field.sheet_name, field.column) == ("Sheet1", "C")
    )
    assert before.lineage_sha256 != after.lineage_sha256
    assert dict(after.statuses)["converted"] == 1
    assert selected.qualification == "candidate_only"


def test_copied_receipt_is_revalidated():
    payload = fixture()
    receipt = _receipt(payload)
    copied = receipt.model_copy(
        update={
            "payload": receipt.payload.model_copy(update={"sha256": "0" * 64})
        }
    )
    with pytest.raises(ValueError, match=r"digest|payload"):
        build_workbook_field_lineage(payload, copied)


def test_column_digest_binds_every_native_and_typed_cell_field():
    payload = fixture()
    receipt = _receipt(payload)
    report = build_workbook_field_lineage(payload, receipt)
    rows = [
        row
        for batch in iter_workbook_value_batches(payload, receipt)
        for row in batch.to_pylist()
        if row["sheet_name"] == "Sheet1" and row["header_coordinate"] == "AV1"
    ]
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(
                row, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
            + b"\n"
        )
    actual = next(
        field
        for field in report.fields
        if (field.sheet_name, field.column) == ("Sheet1", "AV")
    )
    assert actual.lineage_sha256 == digest.hexdigest()
    assert actual.formula_count == actual.error_count == 1


@pytest.mark.parametrize("empty", [True, False])
def test_missing_or_drifting_producer_manifest_is_rejected(monkeypatch, empty):
    payload = fixture()
    receipt = _receipt(payload)
    batches = list(
        iter_workbook_value_batches(payload, receipt, rows_per_batch=1)
    )
    if empty:
        batches = []
    else:
        metadata = dict(batches[1].schema.metadata)
        manifest = json.loads(metadata[b"workbook_sheets"])
        manifest[0]["cell_count"] += 1
        metadata[b"workbook_sheets"] = json.dumps(manifest).encode()
        batches[1] = batches[1].replace_schema_metadata(metadata)
    monkeypatch.setattr(
        module,
        "iter_workbook_value_batches",
        lambda *_args, **_kwargs: iter(batches),
    )
    with pytest.raises(ValueError, match=r"manifest|metadata drift"):
        build_workbook_field_lineage(payload, receipt)
