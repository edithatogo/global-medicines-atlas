"""Historical CSV packages preserve exact native records and original lineage."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_archive_members import fixture

from global_medicines_atlas import mbs_historical_csv_package as module
from global_medicines_atlas.mbs_demographic_package import file_fingerprint
from global_medicines_atlas.mbs_historical_csv_package import (
    FrozenMbsMember,
    build_csv_package,
    load_frozen_members,
    verify_csv_package,
)


def test_frozen_members_bind_all_retained_members_without_new_sources():
    members = load_frozen_members(Path(__file__).resolve().parents[1])
    assert len(members) == 181
    assert sum(member.suffix == ".csv" for member in members) == 90
    assert len({member.source.source_sha256 for member in members}) == 6


def test_two_builds_preserve_header_empty_records_and_exact_values(tmp_path):
    _, source = fixture(tmp_path)
    payload = b"ID,Age,Benefit\n00123,Unknown,1.1234567891\n\n"
    path = tmp_path / "private.csv"
    path.write_bytes(payload)
    native = "SYNTHETIC-MEMBER.csv"
    member = FrozenMbsMember(
        source,
        0,
        hashlib.sha256(payload).hexdigest(),
        len(payload),
        hashlib.sha256(native.encode()).hexdigest(),
        ".csv",
        "5" * 64,
    )
    one = build_csv_package(path, member, native, tmp_path / "one")
    two = build_csv_package(path, member, native, tmp_path / "two")
    assert one == two
    assert verify_csv_package(tmp_path / "one", path, member, native) == one
    rows = pq.read_table(tmp_path / "one/records.parquet").to_pylist()
    assert rows[0]["native_fields"] == ["ID", "Age", "Benefit"]
    assert rows[1]["native_fields"] == ["00123", "Unknown", "1.1234567891"]
    assert rows[2]["native_fields"] == []
    assert "SYNTHETIC-MEMBER" not in json.dumps(one)
    assert not any(one["boundaries"].values())


@pytest.fixture
def native_fixture(tmp_path):
    _, source = fixture(tmp_path)
    payload = b"A,B\n00123,1.1234567891\n\n"
    path = tmp_path / "private.csv"
    path.write_bytes(payload)
    native = "SYNTHETIC.csv"
    return (
        path,
        FrozenMbsMember(
            source,
            0,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            hashlib.sha256(native.encode()).hexdigest(),
            ".csv",
            "5" * 64,
        ),
        native,
    )


@pytest.mark.parametrize(
    "change",
    [
        "value",
        "record_id",
        "ordinal",
        "extra_row",
        "schema",
        "parquet",
        "coverage",
        "promotion",
        "extra_file",
    ],
)
def test_rehashed_corruption_does_not_establish_native_parity(
    tmp_path, native_fixture, change
):
    path, member, native = native_fixture
    out = tmp_path / "out"
    build_csv_package(path, member, native, out)
    report = json.loads((out / "manifest.json").read_bytes())
    data = out / "records.parquet"
    if change in {"value", "record_id", "ordinal", "extra_row", "schema"}:
        table = pq.read_table(data)
        if change == "schema":
            table = table.replace_schema_metadata({
                b"qualification": b"promoted"
            })
        else:
            rows = table.to_pylist()
            if change == "value":
                rows[1]["native_fields"][1] = "rounded away"
            elif change == "record_id":
                rows[0]["native_record_id"] = "wrong lineage"
            elif change == "ordinal":
                rows[0]["record_ordinal"] = 999
            else:
                rows.append(rows[-1])
            table = pa.Table.from_pylist(rows, schema=table.schema)
        pq.write_table(table, data)
        report["parquet"] = file_fingerprint(data)
    elif change == "parquet":
        with data.open("ab") as stream:
            stream.write(b"changed")
    elif change == "coverage":
        report["coverage"]["records"] += 1
    elif change == "promotion":
        report["boundaries"]["admitted"] = True
    else:
        (out / "extra.txt").write_text("extra")
    (out / "manifest.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="MBS native CSV"):
        verify_csv_package(out, path, member, native)


def test_independent_native_oracle_rejects_truncated_producer(
    tmp_path, native_fixture, monkeypatch
):
    path, member, native = native_fixture
    original = module._batches

    def truncated(*args):
        batches = original(*args)
        try:
            yield next(batches).slice(0, 1)
        finally:
            batches.close()

    monkeypatch.setattr(module, "_batches", truncated)
    with pytest.raises(ValueError, match="independent native"):
        build_csv_package(path, member, native, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".mbs-native-csv-*"))


@pytest.mark.parametrize("change", ["source", "path", "format", "bound"])
def test_wrong_source_binding_never_creates_output(
    tmp_path, native_fixture, change
):
    path, member, native = native_fixture
    if change == "source":
        path.write_bytes(path.read_bytes() + b"changed")
    elif change == "path":
        native = "wrong.csv"
    elif change == "format":
        member = replace(member, suffix=".xlsx")
    else:
        member = replace(member, byte_count=0)
    with pytest.raises(ValueError, match="MBS native CSV member"):
        build_csv_package(path, member, native, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_existing_output_is_preserved(tmp_path, native_fixture):
    out = tmp_path / "out"
    out.mkdir()
    (out / "human.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        build_csv_package(*native_fixture, out)
    assert (out / "human.txt").read_text() == "keep"


def test_native_record_batch_bound_preserves_all_rows(
    native_fixture, monkeypatch
):
    monkeypatch.setattr(module, "MAX_BATCH_ROWS", 1)
    path, member, native = native_fixture
    batches = list(module._batches(path, member, native))
    assert len(batches) == 3
    assert sum(b.num_rows for b in batches) == 3


@pytest.mark.parametrize(
    "change", ["digest", "context", "lineage", "denominator", "order", "cohort"]
)
def test_frozen_inventory_pins_and_original_lineage_are_required(
    tmp_path, monkeypatch, change
):
    root = Path(__file__).resolve().parents[1]
    sources = module.load_archives(root)
    pins = []
    for index, (path, original_digest) in enumerate(module.INVENTORY_RECEIPTS):
        selected_digest = original_digest
        data = (root / path).read_bytes()
        if index == 0 and change not in {"digest", "cohort"}:
            report = json.loads(data)
            if change == "context":
                report["dataset"] = "wrong"
            elif change == "lineage":
                report["result"]["b1_sha256"] = "0" * 64
            elif change == "denominator":
                report["result"]["member_count"] += 1
            else:
                report["result"]["members"][0]["ordinal"] = 999
            data = json.dumps(report).encode()
            selected_digest = hashlib.sha256(data).hexdigest()
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            data + b"changed" if index == 0 and change == "digest" else data
        )
        pins.append((path, selected_digest))
    monkeypatch.setattr(module, "load_archives", lambda _: sources)
    monkeypatch.setattr(module, "INVENTORY_RECEIPTS", tuple(pins))
    if change == "cohort":
        monkeypatch.setattr(module, "EXPECTED_MEMBERS", 182)
    with pytest.raises(ValueError, match=r"MBS .* differs"):
        load_frozen_members(tmp_path)


@pytest.mark.parametrize("change", ["columns", "record_bytes"])
def test_native_producer_enforces_record_bounds(
    native_fixture, monkeypatch, change
):
    monkeypatch.setattr(
        module.formats,
        "MAX_COLUMNS" if change == "columns" else "MAX_RECORD_BYTES",
        1,
    )
    with pytest.raises(ValueError, match="record bound"):
        list(module._batches(*native_fixture))


def test_native_producer_flushes_at_encoded_batch_byte_bound(
    native_fixture, monkeypatch
):
    monkeypatch.setattr(module.formats, "MAX_RECORD_BYTES", 250)
    batches = list(module._batches(*native_fixture))
    assert sum(batch.num_rows for batch in batches) == 3
    assert len(batches) > 1


@pytest.mark.parametrize("fields", [None, [None]])
def test_restored_nulls_are_not_native_csv_empty_strings(
    native_fixture, fields
):
    _, member, _ = native_fixture
    row = {
        "record_ordinal": 0,
        "native_record_id": f"{module._member_identity(member)}:/records/0",
        "native_fields": fields,
    }
    with pytest.raises((TypeError, ValueError), match="field state"):
        module._restored_profile(iter([row]), member)


def test_native_package_qualification_checks_actual_consumer_counts(
    native_fixture,
):
    report = module.qualify_csv_member_package(*native_fixture)
    assert report["two_builds_equal"] is True
    assert report["complete_native_restore_verified"] is True
    assert report["duckdb_records"] == 3
    assert report["duckdb_native_fields"] == 4
    assert "SYNTHETIC.csv" not in json.dumps(report)


def test_package_file_bound_keeps_partial_output_private(
    tmp_path, native_fixture, monkeypatch
):
    monkeypatch.setattr(module, "MAX_PARQUET_BYTES", 1)
    with pytest.raises(ValueError, match="package byte bound"):
        build_csv_package(*native_fixture, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".mbs-native-csv-*"))


def test_manifest_read_is_bounded(tmp_path, native_fixture, monkeypatch):
    build_csv_package(*native_fixture, tmp_path / "out")
    monkeypatch.setattr(module, "MAX_MANIFEST_BYTES", 1)
    with pytest.raises(ValueError, match="manifest byte bound"):
        verify_csv_package(tmp_path / "out", *native_fixture)


def test_independent_package_build_difference_is_rejected(
    native_fixture, monkeypatch
):
    original = module.build_csv_package
    count = 0

    def changed(*args):
        nonlocal count
        count += 1
        report = original(*args)
        if count == 2:
            report["output_id"] = "0" * 64
        return report

    monkeypatch.setattr(module, "build_csv_package", changed)
    with pytest.raises(ValueError, match="independent builds differ"):
        module.qualify_csv_member_package(*native_fixture)


@pytest.mark.parametrize("result", [None, (999, 999)])
def test_consumer_denominator_mismatch_is_rejected(
    native_fixture, monkeypatch, result
):
    class Fake:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            return self

        def fetchone(self):
            return result

    monkeypatch.setattr(module.duckdb, "connect", lambda _: Fake())
    with pytest.raises(ValueError, match="DuckDB denominators"):
        module.qualify_csv_member_package(*native_fixture)


def test_missing_source_file_type_rejects_before_read(tmp_path, native_fixture):
    path, member, native = native_fixture
    path.unlink()
    path.mkdir()
    with pytest.raises(ValueError, match="file type"):
        build_csv_package(path, member, native, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_restored_package_file_size_is_bounded(
    tmp_path, native_fixture, monkeypatch
):
    out = tmp_path / "out"
    build_csv_package(*native_fixture, out)
    monkeypatch.setattr(module, "MAX_PARQUET_BYTES", 1)
    with pytest.raises(ValueError, match="package byte bound"):
        verify_csv_package(out, *native_fixture)


def test_empty_native_csv_preserves_zero_without_absence_claim(native_fixture):
    path, member, native = native_fixture
    payload = b"\xef\xbb\xbf"
    path.write_bytes(payload)
    member = replace(
        member,
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_count=len(payload),
    )
    report = module.qualify_csv_member_package(path, member, native)
    assert report["duckdb_records"] == report["duckdb_native_fields"] == 0
    assert report["manifest"]["coverage"]["record_widths"] == {}
    assert report["manifest"]["boundaries"]["semantics_qualified"] is False


@pytest.mark.parametrize("scope", ["member-path", "archive-path"])
def test_identical_bytes_at_distinct_member_paths_keep_distinct_record_ids(
    tmp_path, native_fixture, scope
):
    path, member, native = native_fixture
    other_name = "SYNTHETIC-ALIAS.csv"
    other = replace(
        member,
        path_sha256=hashlib.sha256(other_name.encode()).hexdigest(),
        ordinal=1,
    )
    if scope == "archive-path":
        other_name = native
        other = replace(
            member,
            source=replace(
                member.source, source_path="raw/synthetic-alias.zip"
            ),
        )
    build_csv_package(path, member, native, tmp_path / "one")
    build_csv_package(path, other, other_name, tmp_path / "two")
    first = pq.read_table(tmp_path / "one/records.parquet").to_pylist()
    second = pq.read_table(tmp_path / "two/records.parquet").to_pylist()
    assert first[0]["native_fields"] == second[0]["native_fields"]
    assert first[0]["native_record_id"] != second[0]["native_record_id"]


def test_alias_package_cannot_substitute_for_another_member_binding(
    tmp_path, native_fixture
):
    path, member, native = native_fixture
    alias_name = "SYNTHETIC-ALIAS.csv"
    alias = replace(
        member, path_sha256=hashlib.sha256(alias_name.encode()).hexdigest()
    )
    out = tmp_path / "out"
    build_csv_package(path, alias, alias_name, out)
    with pytest.raises(ValueError, match="schema or lineage"):
        verify_csv_package(out, path, member, native)
