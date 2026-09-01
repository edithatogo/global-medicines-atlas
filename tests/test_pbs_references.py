"""Synthetic source-local PBS identifier/reference diagnostics."""

from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_au_pbs_v3 import (
    _production_xml,  # ruff: ignore[import-private-name] -- synthetic fixture
    _xml,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic fixture
)

from global_medicines_atlas import pbs_references
from global_medicines_atlas.pbs_entities import iter_pbs_entity_batches


def table(payload: bytes, size: int = 2) -> pa.Table:
    return pa.Table.from_batches(
        list(
            pbs_references.iter_pbs_reference_batches(
                payload, _receipt(payload, "au-pbs"), rows_per_batch=size
            )
        )
    )


@pytest.mark.parametrize("payload", [_xml(), _production_xml()])
def test_fixture_contracts_and_lossless_parquet(payload: bytes) -> None:
    result = table(payload)
    original = pa.Table.from_batches(
        list(iter_pbs_entity_batches(payload, _receipt(payload, "au-pbs")))
    )
    assert (
        result.select(original.column_names).to_pylist() == original.to_pylist()
    )
    mapped = [r for r in result.to_pylist() if r["contract_kind"] != "unmapped"]
    assert [r["contract_kind"] for r in mapped] == [
        "item_xml_id",
        "amt_reference",
        "atc_reference",
    ]
    assert [r["diagnostic"] for r in mapped] == [
        "unique_source_literal",
        "unresolved",
        "unresolved",
    ]
    assert mapped[1]["reference_resource"] == "http://snomed.info/id/123456"
    assert mapped[2]["reference_value"] == "A01AA01"
    stream = BytesIO()
    pq.write_table(result, stream)
    assert pq.read_table(BytesIO(stream.getvalue())).equals(
        result, check_metadata=True
    )
    assert result.schema.metadata[b"reference_resolution"] == b"not-performed"


@pytest.mark.parametrize("payload", [_xml(), _production_xml()])
def test_columnar_index_contracts_equal_row_contracts(payload: bytes) -> None:
    batches = list(
        iter_pbs_entity_batches(payload, _receipt(payload, "au-pbs"))
    )
    expected = [
        pbs_references._contract(row)  # pyright: ignore[reportPrivateUsage]
        for batch in batches
        for row in batch.to_pylist()
    ]
    assert [
        contract
        for batch in batches
        for contract in pbs_references._columnar_contracts(  # pyright: ignore[reportPrivateUsage]
            batch
        )
    ] == expected


def test_forward_duplicates_conflicts_and_literal_identity() -> None:
    payload = _xml()
    item = payload[
        payload.index(b"<pbs:pharmaceutical-item") : payload.index(
            b"</pbs:pharmaceutical-item>"
        )
        + len(b"</pbs:pharmaceutical-item>")
    ]
    payload = payload.replace(
        b"</pbs:schedule>",
        item.replace(b"http://snomed.info/id/123456", b"#123456")
        + b"</pbs:schedule>",
    )
    rows = table(payload, 1).to_pylist()
    ids = [r for r in rows if r["contract_kind"] == "item_xml_id"]
    assert [r["diagnostic"] for r in ids] == ["duplicate_source_literal"] * 2
    assert len({r["entity_id"] for r in ids}) == 2
    refs = [r for r in rows if r["contract_kind"] == "amt_reference"]
    assert [r["diagnostic"] for r in refs] == ["ambiguous_source_targets"] * 2
    assert [r["distinct_resource_count"] for r in refs] == [2, 2]
    assert [r["occurrence_count"] for r in refs] == [1, 1]
    assert table(payload, 4096).equals(table(payload, 1), check_metadata=True)
    literal = table(
        _xml().replace(b'xml:id="1234A"', b'xml:id=" 001234A "')
    ).to_pylist()
    assert (
        next(r for r in literal if r["contract_kind"] == "item_xml_id")[
            "reference_value"
        ]
        == " 001234A "
    )


@pytest.mark.parametrize(
    ("before", "after", "kind", "expected"),
    [
        (b' xml:id="1234A"', b"", "item_xml_id", "missing_value"),
        (b'xml:id="1234A"', b'xml:id=""', "item_xml_id", "empty_value"),
        (
            b">123456</pbs:code>",
            b"></pbs:code>",
            "amt_reference",
            "missing_value",
        ),
        (
            b' rdf:resource="http://snomed.info/id/123456"',
            b"",
            "amt_reference",
            "missing_target",
        ),
        (b"http://snomed.info/id/123456", b"", "amt_reference", "empty_target"),
    ],
)
def test_missing_and_empty_are_explicit(
    before: bytes, after: bytes, kind: str, expected: str
) -> None:
    rows = table(_xml().replace(before, after)).to_pylist()
    assert (
        next(r for r in rows if r["contract_kind"] == kind)["diagnostic"]
        == expected
    )


@pytest.mark.parametrize(
    "replacement", [b'type="atc"', b'type="OTHER"', b'rdf:type="ATC"']
)
def test_unknown_classification_attributes_not_atc(replacement: bytes) -> None:
    rows = table(_xml().replace(b'type="ATC"', replacement)).to_pylist()
    row = next(r for r in rows if r["native_text"] == "A01AA01")
    assert row["contract_kind"] == "unmapped"
    assert row["diagnostic"] == "unmapped"


@pytest.mark.parametrize(
    "bound", ["MAX_INDEX_ENTRIES", "MAX_INDEX_BYTES", "MAX_BATCH_BYTES"]
)
def test_bounds_fail_without_truncation(
    monkeypatch: pytest.MonkeyPatch, bound: str
) -> None:
    monkeypatch.setattr(pbs_references, bound, 1)
    with pytest.raises(ValueError, match="limit"):
        table(_xml())


def test_byte_flush_preserves_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = table(_xml(), 4096)
    monkeypatch.setattr(pbs_references, "MAX_BATCH_BYTES", 20000)
    assert table(_xml(), 4096).equals(baseline, check_metadata=True)


def test_identical_references_counted_without_resolution() -> None:
    payload = _xml()
    start = payload.index(b"<pbs:mp-reference>")
    stop = payload.index(b"</pbs:mp-reference>") + len(b"</pbs:mp-reference>")
    payload = payload[:stop] + payload[start:stop] + payload[stop:]
    refs = [
        r
        for r in table(payload).to_pylist()
        if r["contract_kind"] == "amt_reference"
    ]
    assert [r["occurrence_count"] for r in refs] == [2, 2]
    assert [r["diagnostic"] for r in refs] == ["unresolved", "unresolved"]


def test_foreign_codes_and_unknown_item_wrappers_stay_unmapped() -> None:
    payload = (
        _xml()
        .replace(b"<pbs:code", b'<x:code xmlns:x="urn:foreign"')
        .replace(b"</pbs:code>", b"</x:code>")
    )
    assert all(
        r["contract_kind"] == "unmapped"
        for r in table(payload).to_pylist()
        if r["native_name"] == "{urn:foreign}code"
    )
    payload = (
        _xml()
        .replace(
            b"<pbs:pharmaceutical-item",
            b"<pbs:unknown><pbs:pharmaceutical-item",
        )
        .replace(
            b"</pbs:pharmaceutical-item>",
            b"</pbs:pharmaceutical-item></pbs:unknown>",
        )
    )
    assert all(
        r["contract_kind"] == "unmapped" for r in table(payload).to_pylist()
    )


@pytest.mark.parametrize("size", [0, 4097, True])
def test_invalid_batch_size(size: int) -> None:
    with pytest.raises(ValueError, match="batch size"):
        table(_xml(), size)
