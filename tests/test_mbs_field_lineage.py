"""Synthetic field-addressed lineage for MBS Silver candidates."""

# pyright: reportPrivateUsage=false
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError
from test_mbs_silver_qualification import (
    _receipt,  # ruff: ignore[import-private-name]
    _xml,  # ruff: ignore[import-private-name]
)

import global_medicines_atlas.mbs_field_lineage as lineage
from global_medicines_atlas.australian_source_contracts import (
    TargetTable,
    mbs_field_contracts,
)
from global_medicines_atlas.mbs_field_lineage import (
    MbsSilverFieldLineageReport,
    build_mbs_silver_field_lineage,
)
from global_medicines_atlas.receipts import SourceReceipt

if TYPE_CHECKING:
    import pyarrow as pa


def test_complete_field_addresses_and_denominators() -> None:
    payload = _xml()
    report = build_mbs_silver_field_lineage(
        payload, _receipt(payload), date_format="mbs-dmy", rows_per_batch=1
    )

    assert report.source_record_count == 2
    assert len(report.fields) == 40
    assert [item.native_name for item in report.fields] == [
        item.native_name for item in mbs_field_contracts()
    ]
    assert all(item.occurrence_count == 2 for item in report.fields)
    schedule_fee = next(
        item for item in report.fields if item.native_name == "ScheduleFee"
    )
    assert schedule_fee.source_path == "/MBS_XML/Data/ScheduleFee"
    assert schedule_fee.target_table == "fees"
    assert schedule_fee.target_field == "ScheduleFee"
    assert schedule_fee.value_type == "aud_decimal"
    assert schedule_fee.source_value_overwritten is False
    assert {
        item.outcome: item.count for item in schedule_fee.native_states
    } == {"value": 2}
    assert {
        item.outcome: item.count for item in schedule_fee.conversion_statuses
    } == {"converted": 1, "unrepresentable": 1}


def test_report_is_deterministic_bound_and_contains_no_source_values() -> None:
    payload = _xml()
    receipt = _receipt(payload)
    first = build_mbs_silver_field_lineage(
        payload, receipt, date_format="mbs-dmy"
    )
    second = build_mbs_silver_field_lineage(
        payload, receipt, date_format="mbs-dmy"
    )

    assert first == second
    assert first.source_sha256 == receipt.payload.sha256
    assert first.receipt_sha256 == receipt.digest()
    encoded = first.model_dump_json()
    assert "Example service" not in encoded
    assert "42.500" not in encoded
    assert MbsSilverFieldLineageReport.model_validate_json(encoded) == first
    assert json.loads(encoded)["qualification"] == "candidate_only"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("mapping", "mapping differs"),
        ("field_order", "field lineage denominator"),
        ("row_count", "row denominator"),
        ("state_count", "lineage denominator"),
        ("outcome_order", "outcomes differ"),
        ("digest", "report digest"),
        ("promotion", "Input should be 'candidate_only'"),
    ],
)
def test_serialized_lineage_rejects_contract_and_evidence_drift(
    change: str, message: str
) -> None:
    payload = _xml()
    values = build_mbs_silver_field_lineage(
        payload, _receipt(payload), date_format="mbs-dmy"
    ).model_dump()
    if change == "mapping":
        values["fields"][0]["target_table"] = "fees"
    elif change == "field_order":
        values["fields"] = tuple(reversed(values["fields"]))
    elif change == "row_count":
        values["source_record_count"] += 1
    elif change == "state_count":
        values["fields"][0]["native_states"][0]["count"] += 1
    elif change == "outcome_order":
        values["fields"][0]["native_states"] = (
            {"outcome": "value", "count": 1},
            {"outcome": "missing_field", "count": 1},
        )
    elif change == "promotion":
        values["qualification"] = "qualified"
    else:
        values["report_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match=message):
        MbsSilverFieldLineageReport.model_validate(values)


def test_empty_source_and_payload_mismatch_fail_closed() -> None:
    empty = b"<MBS_XML></MBS_XML>"
    with pytest.raises(ValueError, match="no Data records"):
        build_mbs_silver_field_lineage(empty, _receipt(empty))
    payload = _xml()
    with pytest.raises(ValueError, match="payload"):
        build_mbs_silver_field_lineage(payload + b" ", _receipt(payload))


def test_internal_empty_or_mixed_table_denominators_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _xml()
    receipt = _receipt(payload)

    def empty_batches(
        _payload: bytes,
        _receipt_value: SourceReceipt,
        *,
        table: TargetTable,
        date_format: str | None = None,
        rows_per_batch: int = 1024,
    ) -> Iterator[pa.RecordBatch]:
        del table, date_format, rows_per_batch
        return
        yield

    monkeypatch.setattr(lineage, "iter_mbs_silver_batches", empty_batches)
    with pytest.raises(ValueError, match="source denominator"):
        build_mbs_silver_field_lineage(payload, receipt)

    monkeypatch.undo()
    original = lineage.iter_mbs_silver_batches
    calls = 0

    def inconsistent(
        source_payload: bytes,
        source_receipt: SourceReceipt,
        *,
        table: TargetTable,
        date_format: str | None = None,
        rows_per_batch: int = 1024,
    ) -> Iterator[pa.RecordBatch]:
        nonlocal calls
        calls += 1
        batches = tuple(
            original(
                source_payload,
                source_receipt,
                table=table,
                date_format=date_format,
                rows_per_batch=rows_per_batch,
            )
        )
        yield from batches if calls == 1 else (batches[0].slice(0, 1),)

    monkeypatch.setattr(lineage, "iter_mbs_silver_batches", inconsistent)
    with pytest.raises(ValueError, match="row denominators"):
        build_mbs_silver_field_lineage(payload, receipt)
