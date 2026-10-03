"""Synthetic event-table projection preserves denominators and uncertainty."""

# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false
# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false

from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError
from test_mbs_schema_change_events import cohorts, mapping

import global_medicines_atlas.mbs_schema_change_events_columnar as columnar
from global_medicines_atlas.mbs_schema_change_events import (
    build_mbs_schema_change_report,
)
from global_medicines_atlas.mbs_schema_change_events_columnar import (
    project_mbs_schema_change_report,
)


def report():
    historical, current = cohorts()
    return build_mbs_schema_change_report(historical, current, mapping())


def test_event_projection_roundtrips_deterministically_with_denominators():
    value = report()
    envelope, batches = project_mbs_schema_change_report(
        value, rows_per_batch=4
    )
    events = pa.Table.from_batches(list(batches))

    assert envelope.schema.metadata[b"absence_interpretation"] == b"unknown"
    summary = envelope.to_pylist()[0]
    assert summary["report_sha256"] == value.report_sha256
    assert summary["absence_interpretation"] == "unknown"
    assert summary["event_count"] == len(value.events)
    assert summary["historical"]["source_id"] == "au-mbs"
    assert summary["historical"]["table"] == "fees"
    assert summary["historical"]["observed_at"] == (
        value.historical.snapshot.observed_at.isoformat()
    )
    assert summary["historical"]["source_record_count"] == 2
    assert summary["historical"]["omitted_record_count"] == 0
    assert summary["historical"]["selected_key_count"] == 3
    assert summary["historical"]["selected_row_count"] == 2
    assert summary["historical"]["unmatched_selected_key_count"] == 1
    assert summary["current"]["unmatched_selected_key_count"] == 1
    assert events.num_rows == len(value.events)
    assert events["report_sha256"].to_pylist() == [value.report_sha256] * len(
        value.events
    )

    for table in (envelope, events):
        sink = pa.BufferOutputStream()
        pq.write_table(table, sink)
        assert pq.read_table(pa.BufferReader(sink.getvalue())).equals(table)

    again, _ = project_mbs_schema_change_report(value, rows_per_batch=4)
    assert envelope.equals(again, check_metadata=True)


def test_event_projection_preserves_literal_turnover_without_status_labels():
    value = report()
    _, batches = project_mbs_schema_change_report(value)
    events = pa.Table.from_batches(list(batches)).to_pylist()
    kinds = {row["kind"] for row in events}
    assert "observed_only_historical" in kinds
    assert "observed_only_current" in kinds
    assert not kinds & {"addition", "cessation", "renumbering"}


@pytest.mark.parametrize("rows_per_batch", [0, -1, 1025, True, 1.0])
def test_event_projection_rejects_invalid_batch_sizes(rows_per_batch: object):
    with pytest.raises(ValueError, match="rows_per_batch"):
        project_mbs_schema_change_report(
            report(), rows_per_batch=cast("int", rows_per_batch)
        )


def test_event_projection_revalidates_serialized_report():
    value = report().model_copy(update={"absence_interpretation": "ceased"})
    with pytest.raises(ValidationError):
        project_mbs_schema_change_report(value)


def test_event_projection_enforces_canonical_byte_budget(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(columnar, "MAX_CANONICAL_BYTES", 1)
    with pytest.raises(ValueError, match="canonical byte limit"):
        project_mbs_schema_change_report(report())
