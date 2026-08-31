"""Portable candidate projections retain native uncertainty and lineage."""
# ruff: file-ignore[compare-to-empty-string]

import warnings

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from test_historical_comparison import row, snapshot

import global_medicines_atlas.historical_comparison_columnar as columnar
from global_medicines_atlas.historical_comparison import (
    compare_native_snapshots,
)
from global_medicines_atlas.historical_comparison_columnar import (
    project_native_comparison,
)


def test_projection_roundtrip_and_link():
    result = compare_native_snapshots(
        snapshot(rows=(row(),)), snapshot(rows=(row(value=""),))
    )
    envelope, batches = project_native_comparison(result)
    differences = pa.Table.from_batches(list(batches))
    assert (
        envelope.to_pylist()[0]["comparison_sha256"]
        == differences.to_pylist()[0]["comparison_sha256"]
    )
    assert differences.to_pylist()[0]["right"]["value"] == ""
    for table in (envelope, differences):
        sink = pa.BufferOutputStream()
        pq.write_table(table, sink)
        assert pq.read_table(pa.BufferReader(sink.getvalue())).equals(table)


def test_abstention_retains_full_inputs_without_difference_rows():
    result = compare_native_snapshots(
        snapshot(rows=(row(), row(occurrence="second"))), snapshot()
    )
    envelope, batches = project_native_comparison(result)
    assert list(batches) == []
    value = envelope.to_pylist()[0]
    assert value["outcome"] == "abstained"
    assert value["reasons"] == ["ambiguous_identity"]
    assert value["left"]["actual_rows"] == 2
    assert len(value["left"]["rows"]) == 2


def test_copied_invalid_result_rejected_before_return():
    result = compare_native_snapshots(snapshot(), snapshot())
    with pytest.raises(ValidationError, match="comparison result"):
        project_native_comparison(
            result.model_copy(update={"outcome": "abstained"})
        )


@pytest.mark.parametrize("size", [0, -1, 1025, True, 1.0, "1"])
def test_invalid_batch_sizes(size):
    with pytest.raises(ValueError, match="rows_per_batch"):
        project_native_comparison(
            compare_native_snapshots(snapshot(), snapshot()),
            rows_per_batch=size,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"complete": False},
        {"declared_rows": 1},
        {"schema_era": "other"},
        {"scope_id": "selected"},
        {"cohort": "current"},
    ],
)
def test_abstention_envelope_preserves_declarations(changes):
    result = compare_native_snapshots(snapshot(), snapshot(**changes))
    envelope, batches = project_native_comparison(result)
    assert list(batches) == []
    value = envelope.to_pylist()[0]
    assert value["outcome"] == "abstained"
    assert value["right"] == {
        **result.right.model_dump(mode="json"),
        "actual_rows": 0,
    }


def test_states_and_presence_are_distinct():
    left = snapshot(
        rows=(
            row("missing", value=None, state="missing"),
            row("null", value=None, state="null", occurrence="2"),
            row("empty", value="", occurrence="3"),
            row("left-only", occurrence="4"),
        )
    )
    right = snapshot(
        rows=(
            row("missing", occurrence="1"),
            row("null", occurrence="2"),
            row("empty", occurrence="3"),
            row("right-only", occurrence="4"),
        )
    )
    result = compare_native_snapshots(left, right)
    _, batches = project_native_comparison(result, rows_per_batch=2)
    values = list(batches)
    assert [batch.num_rows for batch in values] == [2, 2, 1]
    rows = pa.Table.from_batches(values).to_pylist()
    assert [item["ordinal"] for item in rows] == list(range(5))
    by_id = {item["native_id"]: item for item in rows}
    assert by_id["missing"]["left"]["state"] == "missing"
    assert by_id["null"]["left"]["state"] == "null"
    assert by_id["empty"]["left"]["value"] == ""
    assert by_id["right-only"]["left"] is None
    assert by_id["left-only"]["right"] is None


def test_canonical_budget_rejects_before_arrow(monkeypatch):
    monkeypatch.setattr(columnar, "MAX_CANONICAL_BYTES", 1)
    with pytest.raises(ValueError, match="canonical byte limit"):
        project_native_comparison(
            compare_native_snapshots(snapshot(), snapshot())
        )


@given(st.text(max_size=30))
def test_unicode_roundtrip_is_deterministic(text):
    result = compare_native_snapshots(
        snapshot(rows=(row(value=text),)), snapshot()
    )
    first, _ = project_native_comparison(result)
    second, _ = project_native_comparison(result)
    assert first.equals(second, check_metadata=True)
    assert first.to_pylist()[0]["left"]["rows"][0]["fields"][0]["value"] == text


def test_empty_comparison_has_envelope_and_identity_changes_are_bound():
    first, batches = project_native_comparison(
        compare_native_snapshots(snapshot(), snapshot())
    )
    second, _ = project_native_comparison(
        compare_native_snapshots(snapshot(b1_sha256="c" * 64), snapshot())
    )
    assert list(batches) == []
    assert first.to_pylist()[0]["outcome"] == "compared"
    assert (
        first.to_pylist()[0]["comparison_sha256"]
        != second.to_pylist()[0]["comparison_sha256"]
    )


def test_absent_field_object_and_explicit_missing_survive():
    left = row().model_copy(update={"fields": ()})
    right = row(value=None, state="missing")
    result = compare_native_snapshots(
        snapshot(rows=(left,)), snapshot(rows=(right,))
    )
    envelope, batches = project_native_comparison(result)
    difference = next(batches).to_pylist()[0]
    assert difference["left"] is None
    assert difference["right"] == {
        "name": "fee",
        "state": "missing",
        "value": None,
    }
    assert envelope.to_pylist()[0]["left"]["rows"][0]["fields"] == []


def test_default_batch_boundary_and_input_copy_isolation():
    rows = tuple(
        row(str(index), occurrence=str(index)) for index in range(1025)
    )
    result = compare_native_snapshots(snapshot(rows=rows), snapshot())
    mutable_rows = list(result.left.rows)
    supplied = result.model_copy(
        update={"left": result.left.model_copy(update={"rows": mutable_rows})}
    )
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        envelope, batches = project_native_comparison(supplied)
    assert not captured
    mutable_rows.clear()
    assert [batch.num_rows for batch in batches] == [1024, 1]
    assert envelope.to_pylist()[0]["left"]["actual_rows"] == 1025
