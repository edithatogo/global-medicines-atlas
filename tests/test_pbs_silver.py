"""Synthetic PBS native-field Arrow preservation and boundary tests."""

from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import AnyUrl
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic receipt
)

from global_medicines_atlas.australian_source_contracts import pbs_native_fields
from global_medicines_atlas.pbs_silver import iter_pbs_silver_batches

XML = b"""<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"
 xmlns:x="urn:synthetic:extension" xmlns:db="http://docbook.org/ns/docbook"
 version="3.1"><pbs:schedule effective-date="bad-date"/>
 <pbs:pharmaceutical-item xml:id="00123A"><db:para> Before <db:emphasis>bold</db:emphasis> after </db:para>
 <pbs:price currency="AUD">001.2300</pbs:price><pbs:restriction/>
 <x:code type="ATC">001</x:code><x:code type="AMT" empty=""/>
 </pbs:pharmaceutical-item><pbs:pharmaceutical-item xml:id="00123A"/>
</pbs:root>"""


def test_every_native_slot_survives_ordered_arrow_and_parquet() -> None:
    receipt = _receipt(XML, "au-pbs")
    native = list(pbs_native_fields(XML, receipt))
    batches = list(iter_pbs_silver_batches(XML, receipt, rows_per_batch=3))
    table = pa.Table.from_batches(batches)
    rows = table.to_pylist()
    assert all(batch.num_rows <= 3 for batch in batches)
    assert len(rows) == len(native)
    for ordinal, (row, field) in enumerate(zip(rows, native, strict=True)):
        assert row["source_ordinal"] == ordinal
        assert row["source_field_id"] == f"{field.source_sha256}:{field.path}"
        assert row["receipt_sha256"] == receipt.digest()
        for key, value in field.model_dump().items():
            assert row[key] == value
    assert len({row["source_field_id"] for row in rows}) == len(rows)
    assert [row["value"] for row in rows].count("00123A") == 2
    assert " after " in [row["value"] for row in rows]
    assert "001.2300" in [row["value"] for row in rows]
    assert "bad-date" in [row["value"] for row in rows]
    assert any(row["value"] is None and row["state"] == "null" for row in rows)
    assert any(
        row["value"] == ""  # ruff: ignore[compare-to-empty-string] -- null differs
        and row["state"] == "value"
        for row in rows
    )
    output = BytesIO()
    pq.write_table(table, output)
    restored = pq.read_table(BytesIO(output.getvalue()))
    assert restored.equals(table, check_metadata=True)
    assert all(
        batch.schema.equals(table.schema, check_metadata=True)
        for batch in batches
    )


@pytest.mark.parametrize("size", [0, -1, 4097, True, 1.5])
def test_invalid_batch_bound_rejected(size: int) -> None:
    with pytest.raises(ValueError, match="batch size"):
        list(
            iter_pbs_silver_batches(
                XML, _receipt(XML, "au-pbs"), rows_per_batch=size
            )
        )


@pytest.mark.parametrize(
    "payload", [b"<root/>", b"<broken", b"<!DOCTYPE root><root/>"]
)
def test_invalid_envelope_never_yields_rows(payload: bytes) -> None:
    with pytest.raises(ValueError, match=r"PBS namespace/root|XML"):
        next(iter_pbs_silver_batches(payload, _receipt(payload, "au-pbs")))


def test_receipt_mismatch_and_other_source_rejected() -> None:
    with pytest.raises(ValueError, match="source bytes"):
        next(iter_pbs_silver_batches(XML, _receipt(b"other", "au-pbs")))
    with pytest.raises(ValueError, match="source_id"):
        next(iter_pbs_silver_batches(XML, _receipt(XML, "au-mbs")))


def test_metadata_is_candidate_not_regulatory_or_terminology_assertion() -> (
    None
):
    receipt = _receipt(XML, "au-pbs")
    receipt = receipt.model_copy(
        update={
            "retrieval": receipt.retrieval.model_copy(
                update={
                    "uri": AnyUrl(
                        "https://user:synthetic-password@fixtures.invalid/pbs?token=synthetic-token#secret"
                    )
                }
            )
        }
    )
    table = pa.Table.from_batches(list(iter_pbs_silver_batches(XML, receipt)))
    metadata = table.schema.metadata
    assert metadata is not None
    assert metadata[b"qualification"] == b"candidate"
    assert metadata[b"dimension"] == b"uninterpreted_source_structure"
    assert metadata[b"absence_interpretation"] == b"unknown"
    assert metadata[b"source_receipt_sha256"] == receipt.digest().encode()
    assert b"synthetic-password" not in repr(metadata).encode()
    assert b"synthetic-token" not in repr(metadata).encode()
    assert b"secret" not in repr(metadata).encode()
    assert "regulatory_status" not in table.column_names


def test_batch_size_does_not_change_table_or_parquet_bytes() -> None:
    receipt = _receipt(XML, "au-pbs")
    outputs = []
    for size in (1, 2, 4096):
        table = pa.Table.from_batches(
            list(iter_pbs_silver_batches(XML, receipt, rows_per_batch=size))
        )
        stream = BytesIO()
        pq.write_table(table.combine_chunks(), stream)
        outputs.append(stream.getvalue())
    assert outputs[0] == outputs[1] == outputs[2]


@given(
    st.text(
        alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=40
    )
)
def test_identifier_values_remain_literal_strings(value: str) -> None:
    payload = XML.replace(b"00123A", value.encode())
    rows = pa.Table.from_batches(
        list(iter_pbs_silver_batches(payload, _receipt(payload, "au-pbs")))
    ).to_pylist()
    ids = [
        row for row in rows if row["path"].endswith("XML~11998~1namespace}id")
    ]
    assert len(ids) == 2
    assert all(row["value"] == value for row in ids)


def test_namespace_prefix_spelling_does_not_change_expanded_paths() -> None:
    alternate = XML.replace(b"pbs:", b"other:").replace(
        b"xmlns:pbs=", b"xmlns:other="
    )
    tables = [
        pa.Table.from_batches(
            list(iter_pbs_silver_batches(payload, _receipt(payload, "au-pbs")))
        ).to_pylist()
        for payload in (XML, alternate)
    ]
    assert [row["path"] for row in tables[0]] == [
        row["path"] for row in tables[1]
    ]
    assert any("urn:synthetic:extension" in row["path"] for row in tables[0])
    assert tables[0][0]["source_field_id"] != tables[1][0]["source_field_id"]
