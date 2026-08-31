"""Synthetic native differences never establish current status or cessation."""

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import global_medicines_atlas.historical_comparison as comparison
from global_medicines_atlas.historical_comparison import (
    NativeComparison,
    NativeField,
    NativeRow,
    NativeSnapshot,
    compare_native_snapshots,
)


def snapshot(*, rows=(), **changes):
    return NativeSnapshot.model_validate({
        "source_id": "synthetic-mbs",
        "table": "fees",
        "dimension": "service_benefit",
        "schema_era": "fixture-v1",
        "identity_profile": "literal-item-v1",
        "source_revision": "fixture-1",
        "source_path": "fixture.xml",
        "b1_sha256": "a" * 64,
        "b2_sha256": "b" * 64,
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
        "cohort": "synthetic",
        "declared_rows": len(rows),
        "complete": True,
        "rows": rows,
        **changes,
    })


def row(identity="001", value="1.00", state="value", occurrence="/item[1]"):
    return NativeRow(
        native_id=identity,
        occurrence_id=occurrence,
        fields=(NativeField(name="fee", state=state, value=value),),
    )


def test_preserves_values_and_exact_snapshot_lineage():
    left = snapshot(rows=(row(),))
    right = snapshot(rows=(row(value="1.0"),), b2_sha256="c" * 64)
    result = compare_native_snapshots(left, right)
    assert result.outcome == "compared"
    assert result.left == left
    assert result.right == right
    difference = result.differences[0]
    assert difference.kind == "field_changed"
    assert difference.left.value == "1.00"
    assert difference.right.value == "1.0"
    assert (
        difference.left_occurrence == difference.right_occurrence == "/item[1]"
    )


def test_presence_is_not_cessation_and_identifiers_are_literal():
    result = compare_native_snapshots(
        snapshot(rows=(row(),)), snapshot(rows=(row(identity="1"),))
    )
    assert [item.kind for item in result.differences] == [
        "present_only_left",
        "present_only_right",
    ]
    assert result.absence_interpretation == "unknown"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"complete": False}, "incomplete_snapshot"),
        ({"declared_rows": 2}, "incomplete_snapshot"),
        ({"schema_era": "v2"}, "incompatible_profile"),
        ({"identity_profile": "other"}, "incompatible_profile"),
        ({"dimension": "funding"}, "incompatible_profile"),
        ({"source_id": "other"}, "incompatible_profile"),
        ({"table": "other"}, "incompatible_profile"),
        ({"cohort": "current"}, "incompatible_profile"),
    ],
)
def test_abstains_without_guessing(changes, reason):
    result = compare_native_snapshots(
        snapshot(rows=(row(),)), snapshot(rows=(row(),), **changes)
    )
    assert result.outcome == "abstained"
    assert reason in result.reasons
    assert result.differences == ()


def test_duplicate_native_identity_abstains_but_preserves_occurrences():
    ambiguous = snapshot(rows=(row(), row(occurrence="/item[2]")))
    result = compare_native_snapshots(ambiguous, snapshot())
    assert result.reasons == ("ambiguous_identity",)
    assert result.left == ambiguous


def test_empty_and_unchanged_are_explicit():
    assert compare_native_snapshots(snapshot(), snapshot()).differences == ()
    result = compare_native_snapshots(
        snapshot(rows=(row(),)), snapshot(rows=(row(),))
    )
    assert result.differences[0].kind == "unchanged"


@pytest.mark.parametrize(
    "bad", [{"state": "null", "value": ""}, {"state": "value", "value": None}]
)
def test_native_state_cannot_disagree_with_value(bad):
    with pytest.raises(ValidationError):
        NativeField(name="fee", **bad)


def test_duplicate_field_or_occurrence_rejected():
    with pytest.raises(ValidationError):
        NativeRow(
            native_id="x",
            occurrence_id="x",
            fields=(NativeField(name="x", state="null"),) * 2,
        )
    with pytest.raises(ValidationError):
        snapshot(rows=(row(), row()))


@given(st.text(max_size=100))
def test_unicode_native_text_is_not_normalized(value):
    left = snapshot(rows=(row(value=value),))
    result = compare_native_snapshots(left, left)
    assert result.differences[0].left.value == value
    assert result.differences[0].kind == "unchanged"
    assert (
        NativeComparison.model_validate_json(result.model_dump_json()) == result
    )


def test_field_order_and_row_order_do_not_change_differences():
    fields = (
        NativeField(name="z", state="value", value=""),
        NativeField(name="a", state="null"),
    )
    rows = (
        NativeRow(native_id="b", occurrence_id="1", fields=fields),
        row(occurrence="2"),
    )
    left = snapshot(rows=rows)
    reordered = snapshot(
        rows=(rows[1], rows[0].model_copy(update={"fields": fields[::-1]}))
    )
    assert (
        compare_native_snapshots(left, left).differences
        == compare_native_snapshots(reordered, left).differences
    )


@pytest.mark.parametrize("state", ["missing", "null"])
def test_null_missing_and_omitted_fields_differ_from_empty_value(state):
    left = snapshot(rows=(row(value=None, state=state),))
    right = snapshot(rows=(row(value=""),))
    event = compare_native_snapshots(left, right).differences[0]
    assert event.kind == "field_changed"
    assert event.left.state == state
    assert event.right.value == ""  # ruff: ignore[compare-to-empty-string] - distinct from None
    omitted = snapshot(rows=(row().model_copy(update={"fields": ()}),))
    assert compare_native_snapshots(omitted, left).differences[0].left is None


def test_exact_native_utf8_byte_budget(monkeypatch):
    # Bytes counted: native id3 + occurrence8 + field name3 + UTF8 value2.
    original = row(value="é")
    limit = (
        len(original.native_id.encode())
        + len(original.occurrence_id.encode())
        + len("feeé".encode())
    )
    monkeypatch.setattr(comparison, "MAX_NATIVE_BYTES", limit)
    assert snapshot(rows=(original,)).rows == (original,)
    monkeypatch.setattr(comparison, "MAX_NATIVE_BYTES", limit - 1)
    with pytest.raises(ValidationError, match="byte limit"):
        snapshot(rows=(original,))


def test_row_and_field_limits_are_inclusive():
    fields = tuple(NativeField(name=str(i), state="null") for i in range(256))
    assert (
        len(NativeRow(native_id="x", occurrence_id="x", fields=fields).fields)
        == 256
    )
    with pytest.raises(ValidationError):
        NativeRow(
            native_id="x",
            occurrence_id="x",
            fields=(*fields, NativeField(name="extra", state="null")),
        )
    rows = tuple(
        NativeRow(native_id=str(i), occurrence_id=str(i), fields=())
        for i in range(4096)
    )
    assert len(snapshot(rows=rows).rows) == 4096
    with pytest.raises(ValidationError):
        snapshot(
            rows=(
                *rows,
                NativeRow(native_id="extra", occurrence_id="extra", fields=()),
            ),
            declared_rows=4096,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"outcome": "abstained"},
        {"reasons": ("incomplete_snapshot",)},
        {"differences": ()},
        {"absence_interpretation": "ceased"},
        {"qualification": "promoted_gold"},
    ],
)
def test_forged_result_is_rejected(changes):
    original = snapshot(rows=(row(),))
    payload = compare_native_snapshots(original, original).model_dump()
    with pytest.raises(ValidationError):
        NativeComparison.model_validate({**payload, **changes})


def test_constructed_invalid_inputs_are_revalidated():
    bad = snapshot().model_copy(update={"declared_rows": -1})
    with pytest.raises(ValidationError):
        compare_native_snapshots(bad, snapshot())


@pytest.mark.parametrize(
    "changes",
    [
        {"b1_sha256": "not-a-digest"},
        {"b2_sha256": "A" * 64},
        {"source_revision": ""},
        {"source_path": ""},
        {"observed_at": "2026-01-01T00:00:00"},
        {"declared_rows": True},
        {"complete": "true"},
    ],
)
def test_lineage_and_denominator_contract_is_strict(changes):
    with pytest.raises(ValidationError):
        snapshot(**changes)


def test_direct_result_revalidates_constructed_snapshot():
    original = compare_native_snapshots(snapshot(), snapshot())
    payload = original.model_dump()
    payload["left"] = snapshot().model_copy(update={"b1_sha256": "invalid"})
    with pytest.raises(ValidationError):
        NativeComparison.model_validate(payload)


def test_json_schema_forbids_native_and_status_coercion():
    field_schema = Draft202012Validator(NativeField.model_json_schema())
    assert not field_schema.is_valid({"name": "x", "state": "value"})
    assert not field_schema.is_valid({
        "name": "x",
        "state": "null",
        "value": "",
    })
    original = snapshot(rows=(row(),))
    payload = compare_native_snapshots(original, original).model_dump(
        mode="json"
    )
    schema = Draft202012Validator(NativeComparison.model_json_schema())
    schema.validate(payload)
    payload["differences"][0]["kind"] = "ceased"
    assert not schema.is_valid(payload)


@pytest.mark.parametrize(
    "field",
    [
        "source_id",
        "table",
        "schema_era",
        "identity_profile",
        "source_revision",
        "source_path",
    ],
)
@pytest.mark.parametrize("value", [" ", " padded", "padded "])
def test_profile_metadata_cannot_be_blank_or_padded(field, value):
    with pytest.raises(ValidationError):
        snapshot(**{field: value})


def test_unknown_blank_identity_cannot_match():
    with pytest.raises(ValidationError):
        row(identity=" \t")
    assert row(identity=" 001").native_id == " 001"


def test_aggregate_fields_bound(monkeypatch):
    monkeypatch.setattr(comparison, "MAX_SNAPSHOT_FIELDS", 1)
    assert len(snapshot(rows=(row(),)).rows) == 1
    with pytest.raises(ValidationError, match="aggregate field"):
        snapshot(rows=(row(), row(identity="x", occurrence="2")))


def test_differences_bound_checked_before_output_allocation(monkeypatch):
    left = snapshot(rows=(row(),))
    right = snapshot(rows=(row(identity="other"),))
    monkeypatch.setattr(comparison, "MAX_DIFFERENCES", 2)
    assert len(compare_native_snapshots(left, right).differences) == 2
    monkeypatch.setattr(comparison, "MAX_DIFFERENCES", 1)

    def forbid_allocation(**_kwargs):
        pytest.fail("difference allocated before output bound check")

    monkeypatch.setattr(comparison, "NativeDifference", forbid_allocation)
    with pytest.raises(ValueError, match="difference limit"):
        compare_native_snapshots(left, right)


def test_mutable_nested_model_inputs_are_normalized():
    original_row = row()
    mutable_row = original_row.model_copy(
        update={"fields": list(original_row.fields)}
    )
    original = snapshot(rows=(original_row,))
    mutable = original.model_copy(update={"rows": [mutable_row]})
    payload = compare_native_snapshots(original, original).model_dump()
    payload["left"] = mutable
    result = NativeComparison.model_validate(payload)
    assert isinstance(result.left.rows, tuple)
    assert isinstance(result.left.rows[0].fields, tuple)
    mutable.rows.clear()
    assert len(result.left.rows) == 1
    assert len(result.differences) == 1


def test_constructed_difference_field_is_revalidated():
    original = snapshot(rows=(row(),))
    result = compare_native_snapshots(original, original)
    bad_field = result.differences[0].left.model_copy(update={"state": "null"})
    bad_difference = result.differences[0].model_copy(
        update={"left": bad_field}
    )
    payload = result.model_dump()
    payload["differences"] = (bad_difference,)
    with pytest.raises(ValidationError, match="state and value"):
        NativeComparison.model_validate(payload)


def test_explicit_scope_cannot_compare_with_other_or_whole_source():
    whole = snapshot()
    scoped = snapshot(scope_id="synthetic-cohort:a")
    assert whole.scope_id == "whole_source"
    assert compare_native_snapshots(whole, scoped).reasons == (
        "incompatible_profile",
    )
    assert (
        compare_native_snapshots(
            scoped, snapshot(scope_id="synthetic-cohort:b")
        ).outcome
        == "abstained"
    )
