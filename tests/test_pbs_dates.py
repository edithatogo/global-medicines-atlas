"""Explicit candidate PBS date conversion with complete native lineage."""

from datetime import date
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_au_pbs_v3 import (
    _production_xml,  # ruff: ignore[import-private-name] -- synthetic fixture
    _xml,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic fixture
)

from global_medicines_atlas import pbs_dates
from global_medicines_atlas.pbs_entities import iter_pbs_entity_batches


def table(
    payload: bytes, profile: str | None = None, size: int = 2
) -> pa.Table:
    return pa.Table.from_batches(
        list(
            pbs_dates.iter_pbs_date_batches(
                payload,
                _receipt(payload, "au-pbs"),
                date_profile=profile,
                rows_per_batch=size,
            )
        )
    )


@pytest.mark.parametrize("payload", [_xml(), _production_xml()])
def test_no_implicit_conversion_and_complete_native_parity(
    payload: bytes,
) -> None:
    result = table(payload)
    native = pa.Table.from_batches(
        list(iter_pbs_entity_batches(payload, _receipt(payload, "au-pbs")))
    )
    assert result.select(native.column_names).to_pylist() == native.to_pylist()
    assert all(r["date_value"] is None for r in result.to_pylist())
    assert any(
        r["date_conversion_status"] == "profile_not_selected"
        for r in result.to_pylist()
    )
    assert result.schema.metadata[b"date_profile"] == b"not-selected"


def test_selected_profile_and_parquet_preserve_exact_field_identity() -> None:
    payload = _production_xml()
    result = table(payload, pbs_dates.CANDIDATE_PROFILE)
    rows = [r for r in result.to_pylist() if r["date_role"] != "unmapped"]
    assert [r["date_role"] for r in rows] == [
        "schedule_effective_date",
        "schedule_dct_valid",
        "restriction_effective_date",
    ]
    assert [r["date_value"] for r in rows] == [
        None,
        date(2026, 4, 1),
        date(2026, 7, 15),
    ]
    assert rows[0]["date_native_state"] == "missing_field"
    assert rows[0]["date_source_field_id"] is None
    for row in rows[1:]:
        field = next(
            f
            for f in row["native_fields"]
            if f["source_field_id"] == row["date_source_field_id"]
        )
        assert field["value"] == row["date_native_value"]
    stream = BytesIO()
    pq.write_table(result, stream)
    assert pq.read_table(BytesIO(stream.getvalue())).equals(
        result, check_metadata=True
    )
    assert result.schema.field("date_value").type == pa.date32()
    assert (
        result.schema.metadata[b"source_date_era_qualification"]
        == b"not-established"
    )


@pytest.mark.parametrize(
    ("literal", "status"),
    [
        (b"", "empty_value"),
        (b" ", "blank_value"),
        (b"2026-02-30", "invalid_date"),
        (b"0000-01-01", "invalid_date"),
        (b"20260701", "unsupported_format"),
        (b"01.07.2026", "unsupported_format"),
        (b"2026-07-01T00:00:00Z", "unsupported_format"),
        (b" 2026-07-01 ", "unsupported_format"),
    ],
)
def test_native_invalid_and_unsupported_values_retained(
    literal: bytes, status: str
) -> None:
    payload = _xml().replace(b"2026-07-01", literal)
    row = table(payload, pbs_dates.CANDIDATE_PROFILE).to_pylist()[0]
    assert row["date_native_value"] == literal.decode()
    assert row["date_conversion_status"] == status
    assert row["date_value"] is None


def test_missing_attribute_and_null_text_are_distinct() -> None:
    payload = _production_xml().replace(b"2026-04-01", b"")
    rows = [
        r
        for r in table(payload, pbs_dates.CANDIDATE_PROFILE).to_pylist()
        if r["date_role"] != "unmapped"
    ]
    assert rows[0]["date_conversion_status"] == "missing_field"
    assert rows[1]["date_conversion_status"] == "null"


def test_duplicate_dates_and_native_item_ids_not_collapsed_or_prioritised() -> (
    None
):
    payload = _production_xml().replace(
        b"<dct:valid>2026-04-01</dct:valid>",
        b"<dct:valid>2026-04-01</dct:valid><dct:valid>2026-05-01</dct:valid>",
    )
    rows = [
        r
        for r in table(payload, pbs_dates.CANDIDATE_PROFILE).to_pylist()
        if r["date_role"] == "schedule_dct_valid"
    ]
    assert [r["date_occurrence_index"] for r in rows] == [1, 2]
    assert [r["date_occurrence_state"] for r in rows] == [
        "first_occurrence",
        "repeated_occurrence",
    ]
    assert [r["date_value"] for r in rows] == [
        date(2026, 4, 1),
        date(2026, 5, 1),
    ]
    assert len({r["date_source_field_id"] for r in rows}) == 2
    assert table(payload, pbs_dates.CANDIDATE_PROFILE, 1).equals(
        table(payload, pbs_dates.CANDIDATE_PROFILE, 4096), check_metadata=True
    )


def test_foreign_attributes_and_unknown_wrappers_not_converted() -> None:
    payload = (
        _xml()
        .replace(
            b' effective-date="2026-07-01"',
            b' xmlns:x="urn:x" x:effective-date="2026-07-01"',
        )
        .replace(b"<pbs:restrictions>", b"<pbs:unknown>")
        .replace(b"</pbs:restrictions>", b"</pbs:unknown>")
    )
    rows = table(payload, pbs_dates.CANDIDATE_PROFILE).to_pylist()
    assert rows[0]["date_conversion_status"] == "missing_field"
    assert all(r["date_role"] != "restriction_effective_date" for r in rows)
    assert any(f["value"] == "2026-07-01" for f in rows[0]["native_fields"])


@pytest.mark.parametrize("profile", ["iso", "mbs-dmy", "production"])
def test_unknown_profiles_rejected(profile: str) -> None:
    with pytest.raises(ValueError, match="profile"):
        table(_xml(), profile)


def test_buffer_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = table(_xml(), pbs_dates.CANDIDATE_PROFILE, 4096)
    monkeypatch.setattr(pbs_dates, "MAX_BATCH_BYTES", 20000)
    assert table(_xml(), pbs_dates.CANDIDATE_PROFILE, 4096).equals(
        baseline, check_metadata=True
    )
    monkeypatch.setattr(pbs_dates, "MAX_BATCH_BYTES", 1)
    with pytest.raises(ValueError, match="byte limit"):
        table(_xml(), pbs_dates.CANDIDATE_PROFILE)


@given(st.dates())
def test_candidate_calendar_dates_preserve_exact_literal(value: date) -> None:
    literal = value.isoformat()
    payload = _xml().replace(b"2026-07-01", literal.encode())
    result = table(payload, pbs_dates.CANDIDATE_PROFILE)
    row = result.to_pylist()[0]
    assert row["date_native_value"] == literal
    assert row["date_value"] == value
    assert result.schema.metadata[b"conversion"] == b"candidate-date32"


@pytest.mark.parametrize("size", [0, 4097, True])
def test_invalid_batch_size_rejected(size: int) -> None:
    with pytest.raises(ValueError, match="batch size"):
        table(_xml(), size=size)


def test_duplicate_item_ids_keep_independent_date_lineage() -> None:
    payload = _xml()
    start = payload.index(b"<pbs:pharmaceutical-item")
    stop = payload.index(b"</pbs:pharmaceutical-item>") + len(
        b"</pbs:pharmaceutical-item>"
    )
    payload = payload[:stop] + payload[start:stop] + payload[stop:]
    rows = [
        row
        for row in table(payload, pbs_dates.CANDIDATE_PROFILE).to_pylist()
        if row["date_role"] == "restriction_effective_date"
    ]
    assert len(rows) == 2
    assert len({row["item_occurrence_id"] for row in rows}) == 2
    assert len({row["date_source_field_id"] for row in rows}) == 2
    assert [row["date_value"] for row in rows] == [date(2026, 7, 15)] * 2
