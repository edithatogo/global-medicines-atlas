"""Sidecar candidate records retain exact native fields without interpretation."""

import pyarrow as pa
import pytest
from test_mbs_sidecar_layout import source

from global_medicines_atlas import mbs_sidecar_silver as module
from global_medicines_atlas.mbs_sidecar_silver import iter_sidecar_batches


def rows(payload, kind, size=1024):
    batches = list(
        iter_sidecar_batches(
            payload, source(payload, kind), rows_per_batch=size
        )
    )
    return pa.Table.from_batches(batches).to_pylist()


def test_csv_retains_header_candidate_empty_records_and_leading_zero_identity():
    result = rows(b"ITEM,DESCRIPTION\r\n00123,SYNTHETIC\r\n\r\n", "csv", 1)
    assert len(result) == 3
    assert result[0]["native_fields"][0]["value"] == "ITEM"
    assert result[1]["native_fields"][0]["value"] == "00123"
    assert result[2]["native_fields"] == []
    assert result[0]["interpretation_state"] == "native_unresolved"


def test_xml_preserves_mixed_text_tail_empty_attribute_and_parent_links():
    result = rows(b'<r a=""><c>SYNTHETIC</c>tail<c/></r>', "xml")
    assert len(result) == 3
    fields = [field for row in result for field in row["native_fields"]]
    assert len(fields) == 7
    assert sum(field["state"] == "null" for field in fields) == 4
    assert result[0]["parent_record_id"] == "/r/1"
    attribute = next(
        field for field in fields if field["slot_name"] == "attributes/a"
    )
    assert attribute["value"] is not None
    assert not attribute["value"]
    assert attribute["state"] == "value"


def test_text_retains_literal_tabs_quotes_and_every_line_ending():
    payload = b'00123\t"SYNTHETIC"\t\r\n\t2\nlast\r'
    result = rows(payload, "text", 1)
    restored = b"".join(
        (
            "\t".join(field["value"] for field in row["native_fields"])
            + row["line_ending"]
        ).encode()
        for row in result
    )
    assert restored == payload
    assert result[0]["native_fields"][0]["value"] == "00123"
    assert result[0]["native_fields"][1]["value"] == '"SYNTHETIC"'


@pytest.mark.parametrize("size", [0, -1, True, 4097])
def test_invalid_batch_bounds_reject_before_projection(size):
    payload = b"A,B\n"
    with pytest.raises(ValueError, match="batch row bound"):
        list(
            iter_sidecar_batches(
                payload, source(payload, "csv"), rows_per_batch=size
            )
        )


def test_byte_limits_reject_records_without_truncation(monkeypatch):
    payload = b"A,B\n"
    monkeypatch.setattr(module, "MAX_BATCH_BYTES", 1)
    with pytest.raises(ValueError, match="record byte bound"):
        list(iter_sidecar_batches(payload, source(payload, "csv")))


def test_unqualified_text_encoding_is_not_replaced_or_guessed():
    payload = b"\xff\n"
    with pytest.raises(ValueError, match="encoding is unqualified"):
        list(iter_sidecar_batches(payload, source(payload, "text")))


def test_changed_independent_denominator_rejects_complete_candidate(
    monkeypatch,
):
    payload = b"A,B\n1,2\n"
    original = module.profile_sidecar

    def changed(data, selected):
        report = original(data, selected)
        report["layout"]["native_fields"] += 1
        return report

    monkeypatch.setattr(module, "profile_sidecar", changed)
    with pytest.raises(ValueError, match="complete native parity"):
        list(
            iter_sidecar_batches(
                payload, source(payload, "csv"), rows_per_batch=1
            )
        )


def test_batch_partition_does_not_change_native_records_or_metadata():
    payload = b"A,B\n00123,SYNTHETIC\n"
    selected = source(payload, "csv")
    first = pa.Table.from_batches(
        list(iter_sidecar_batches(payload, selected, rows_per_batch=1))
    )
    second = pa.Table.from_batches(
        list(iter_sidecar_batches(payload, selected))
    )
    assert first.equals(second, check_metadata=True)
    assert first.schema.metadata[b"patient_rates"] == b"unavailable"
    assert first.schema.metadata[b"date_interpretation"] == b"unqualified"
