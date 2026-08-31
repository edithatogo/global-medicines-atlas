"""PBS structural family mappings must not infer medicine assertions."""

from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from profile_pbs_domain import row_reference
from test_au_pbs_v3 import (
    _production_xml,  # ruff: ignore[import-private-name] -- synthetic fixture
    _xml,  # ruff: ignore[import-private-name] -- synthetic fixture
    _zip,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic receipt
)
from test_pbs_historical_silver import PATH, SOURCE

from global_medicines_atlas import pbs_domain as domain
from global_medicines_atlas.pbs_domain import iter_pbs_domain_batches
from global_medicines_atlas.pbs_historical_silver import (
    iter_pbs_historical_silver_batches,
)
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_silver import iter_pbs_silver_batches


@pytest.mark.parametrize("payload", [_xml(), _production_xml()])
def test_established_families_preserve_every_native_row(payload: bytes) -> None:
    receipt = _receipt(payload, "au-pbs")
    native = pa.Table.from_batches(
        list(iter_pbs_silver_batches(payload, receipt))
    )
    mapped = pa.Table.from_batches(
        list(iter_pbs_domain_batches(payload, receipt, rows_per_batch=2))
    )
    assert mapped.num_rows == native.num_rows
    assert mapped.select(native.column_names).to_pylist() == native.to_pylist()
    rows = mapped.to_pylist()
    assert {row["mapping_target"] for row in rows} >= {
        "schedules",
        "items",
        "presentations",
        "restrictions",
        "amt_references",
        "classifications",
    }
    by_value = {row["value"]: row for row in rows if row["value"]}
    assert (
        by_value["Exampleline 10 mg tablet"]["mapping_target"]
        == "presentations"
    )
    assert by_value["123456"]["mapping_target"] == "amt_references"
    assert by_value["A01AA01"]["mapping_target"] == "classifications"
    assert by_value["Authority required"]["mapping_target"] == "restrictions"
    assert by_value["2026-07-15"]["value"] == "2026-07-15"
    assert by_value["1234A"]["item_occurrence_id"].startswith(
        receipt.payload.sha256
    )
    stream = BytesIO()
    pq.write_table(mapped, stream)
    assert pq.read_table(BytesIO(stream.getvalue())).equals(
        mapped, check_metadata=True
    )


def test_unknown_namespaces_prices_and_wrappers_are_not_guessed() -> None:
    payload = _xml().replace(
        b"</pbs:pharmaceutical-item>",
        b"""
      <pbs:price currency="AUD">001.2300</pbs:price>
      <other:restriction xmlns:other="urn:other">not a PBS restriction</other:restriction>
      <pbs:unknown><pbs:classification><pbs:code type="ATC">FAKE</pbs:code></pbs:classification></pbs:unknown>
      </pbs:pharmaceutical-item>""",
    )
    rows = pa.Table.from_batches(
        list(iter_pbs_domain_batches(payload, _receipt(payload, "au-pbs")))
    ).to_pylist()
    for value in ("001.2300", "not a PBS restriction", "FAKE"):
        row = next(row for row in rows if row["value"] == value)
        assert row["mapping_target"] == "unmapped"
        assert row["mapping_status"] == "unmapped"
        assert row["item_occurrence_id"] is not None


def test_duplicate_native_item_ids_have_distinct_occurrence_lineage() -> None:
    payload = _xml().replace(
        b"</pbs:schedule>",
        b'<pbs:pharmaceutical-item xml:id="1234A"/></pbs:schedule>',
    )
    rows = pa.Table.from_batches(
        list(iter_pbs_domain_batches(payload, _receipt(payload, "au-pbs")))
    ).to_pylist()
    ids = [row["item_occurrence_id"] for row in rows if row["value"] == "1234A"]
    assert len(ids) == len(set(ids)) == 2


def test_foreign_item_wrapper_never_receives_pbs_item_identity() -> None:
    payload = (
        _xml()
        .replace(
            b"<pbs:pharmaceutical-item",
            b'<foreign xmlns="urn:other"><pbs:pharmaceutical-item',
        )
        .replace(
            b"</pbs:pharmaceutical-item>",
            b"</pbs:pharmaceutical-item></foreign>",
        )
    )
    rows = pa.Table.from_batches(
        list(iter_pbs_domain_batches(payload, _receipt(payload, "au-pbs")))
    ).to_pylist()
    item = next(row for row in rows if row["value"] == "1234A")
    assert item["mapping_target"] == "unmapped"
    assert item["item_occurrence_id"] is None


def test_mapping_keeps_metadata_candidate_and_errors_fail_closed() -> None:
    payload = _xml()
    receipt = _receipt(payload, "au-pbs")
    batch = next(iter_pbs_domain_batches(payload, receipt))
    assert batch.schema.metadata[b"qualification"] == b"candidate"
    assert (
        batch.schema.metadata[b"dimension"] == b"uninterpreted_source_structure"
    )
    assert batch.schema.metadata[b"conversion"] == b"none"
    with pytest.raises(ValueError, match="batch size"):
        next(iter_pbs_domain_batches(payload, receipt, rows_per_batch=0))
    with pytest.raises(ValueError, match="source bytes"):
        next(iter_pbs_domain_batches(payload + b" ", receipt))


def test_mixed_docbook_text_and_extensions_remain_separate() -> None:
    payload = (
        _xml()
        .replace(
            b"Exampleline 10 mg tablet",
            b'Before <dbk:emphasis>inner</dbk:emphasis> after <x:para xmlns:x="urn:other">foreign</x:para>',
        )
        .replace(
            b"Authority required",
            b"<dbk:para>Restriction <dbk:emphasis>detail</dbk:emphasis></dbk:para>",
        )
    )
    rows = pa.Table.from_batches(
        list(iter_pbs_domain_batches(payload, _receipt(payload, "au-pbs")))
    ).to_pylist()
    by_value = {row["value"]: row for row in rows if row["value"]}
    assert by_value["inner"]["mapping_target"] == "presentations"
    assert by_value[" after "]["mapping_target"] == "presentations"
    assert by_value["foreign"]["mapping_target"] == "unmapped"
    assert by_value["detail"]["mapping_target"] == "restrictions"


def test_mapping_is_identical_across_batch_sizes() -> None:
    payload = _production_xml()
    receipt = _receipt(payload, "au-pbs")
    tables = [
        pa.Table.from_batches(
            list(iter_pbs_domain_batches(payload, receipt, rows_per_batch=size))
        )
        for size in (1, 3, 4096)
    ]
    assert all(table.equals(tables[0], check_metadata=True) for table in tables)


@pytest.mark.parametrize("historical", [False, True])
@pytest.mark.parametrize(("offset", "length"), [(0, 0), (0, 1), (1, 11)])
def test_mapping_reuses_native_buffers_and_matches_row_reference(
    historical, offset, length
):
    payload = _production_xml()
    if historical:
        archive = _zip([(PATH, payload)])
        parent = _receipt(archive, SOURCE)
        binding = build_pbs_xml_member_binding(archive, parent)
        native = next(
            iter_pbs_historical_silver_batches(
                archive, payload, parent, binding
            )
        )
    else:
        native = next(
            iter_pbs_silver_batches(payload, _receipt(payload, "au-pbs"))
        )
    native = native.slice(offset, length)
    mapped = next(domain._domain_batches(iter([native])))
    expected = row_reference(native)
    assert mapped.equals(expected, check_metadata=True)
    for index in range(native.num_columns):
        before, after = native.column(index), mapped.column(index)
        assert before.offset == after.offset
        assert [
            buffer.address if buffer is not None else None
            for buffer in before.buffers()
        ] == [
            buffer.address if buffer is not None else None
            for buffer in after.buffers()
        ]
    assert mapped.schema.names == [
        *native.schema.names,
        "mapping_target",
        "mapping_status",
        "item_occurrence_id",
    ]
    assert mapped.schema.metadata == {
        **native.schema.metadata,
        b"schema_name": b"global-medicines-atlas.pbs-silver.domain-fields",
        b"mapping_profile": b"pbs-adapter-structural-v1",
    }


def test_mapping_materializes_only_required_columns(monkeypatch):
    payload = _production_xml()
    native = next(iter_pbs_silver_batches(payload, _receipt(payload, "au-pbs")))
    original = domain._mapping
    calls = 0

    def checked(row):
        nonlocal calls
        calls += 1
        assert set(row) == {"record_id", "source_sha256"}
        return original(row)

    monkeypatch.setattr(domain, "_mapping", checked)
    mapped = next(domain._domain_batches(iter([native])))
    assert calls == mapped.num_rows == native.num_rows
