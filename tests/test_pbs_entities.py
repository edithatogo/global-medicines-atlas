"""Lossless, bounded PBS entity rows over synthetic native occurrences."""

from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic fixture
)
from test_pbs_silver import XML

from global_medicines_atlas import pbs_entities
from global_medicines_atlas.pbs_domain import iter_pbs_domain_batches


def table(payload: bytes = XML, size: int = 2) -> pa.Table:
    return pa.Table.from_batches(
        list(
            pbs_entities.iter_pbs_entity_batches(
                payload, _receipt(payload, "au-pbs"), rows_per_batch=size
            )
        )
    )


def test_all_native_fields_roundtrip_and_tree_identity_survive() -> None:
    result = table()
    rows = result.to_pylist()
    original = pa.Table.from_batches(
        list(iter_pbs_domain_batches(XML, _receipt(XML, "au-pbs")))
    ).to_pylist()
    assert [field for row in rows for field in row["native_fields"]] == original
    ids = {row["entity_id"] for row in rows}
    assert len(ids) == len(rows)
    assert rows[0]["parent_entity_id"] is None
    assert all(row["parent_entity_id"] in ids for row in rows[1:])
    item_rows = [
        row
        for row in rows
        if row["native_name"].endswith("}pharmaceutical-item")
    ]
    assert [row["native_xml_id"] for row in item_rows] == ["00123A", "00123A"]
    assert all(row["xml_id_state"] == "value" for row in item_rows)
    assert len({row["entity_id"] for row in item_rows}) == 2
    assert rows[0]["xml_id_state"] == "missing_field"
    assert any(row["native_text"] == " Before " for row in rows)
    assert any(row["native_tail"] == " after " for row in rows)
    empty = next(
        row for row in rows if row["native_name"].endswith("}restriction")
    )
    assert empty["native_text"] is None
    assert empty["text_state"] == "null"
    unknown = next(row for row in rows if row["native_text"] == "001.2300")
    assert unknown["mapping_target"] == "unmapped"
    stream = BytesIO()
    pq.write_table(result, stream)
    assert pq.read_table(BytesIO(stream.getvalue())).equals(
        result, check_metadata=True
    )


def test_grouping_survives_arbitrary_native_and_output_batch_boundaries() -> (
    None
):
    baseline = table(size=1)
    for size in (2, 3, 4096):
        assert table(size=size).equals(baseline, check_metadata=True)


def test_blank_xml_id_is_not_missing() -> None:
    rows = table(XML.replace(b'xml:id="00123A"', b'xml:id=""')).to_pylist()
    items = [row for row in rows if row["xml_id_state"] == "value"]
    assert len(items) == 2
    assert all(row["native_xml_id"] == "" for row in items)  # ruff: ignore[compare-to-empty-string] -- missing differs


@pytest.mark.parametrize("bound", ["MAX_ELEMENT_FIELDS", "MAX_ELEMENT_BYTES"])
def test_oversized_element_rejected_not_truncated(
    monkeypatch: pytest.MonkeyPatch, bound: str
) -> None:
    monkeypatch.setattr(pbs_entities, bound, 1)
    with pytest.raises(ValueError, match="element"):
        table()


def test_batch_byte_budget_flushes_without_changing_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = table(size=4096)
    monkeypatch.setattr(pbs_entities, "MAX_BATCH_BYTES", 12000)
    batches = list(
        pbs_entities.iter_pbs_entity_batches(
            XML, _receipt(XML, "au-pbs"), rows_per_batch=4096
        )
    )
    assert len(batches) > 1
    assert pa.Table.from_batches(batches).equals(baseline, check_metadata=True)


def test_entity_larger_than_batch_budget_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pbs_entities, "MAX_BATCH_BYTES", 1)
    with pytest.raises(ValueError, match="batch byte"):
        table()


@pytest.mark.parametrize("size", [0, 4097, True])
def test_invalid_batch_size_rejected(size: int) -> None:
    with pytest.raises(ValueError, match="batch size"):
        table(size=size)


def test_schema_is_constructed_once_per_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = pbs_entities._schema
    calls: list[pa.Schema] = []

    def counted(native: pa.Schema) -> pa.Schema:
        calls.append(native)
        return original(native)

    monkeypatch.setattr(pbs_entities, "_schema", counted)
    result = table(size=1)
    assert result.num_rows > 1
    assert len(calls) == 1
