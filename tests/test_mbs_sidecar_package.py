"""Complete sidecar packages are deterministic and restore every native record."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_sidecar_layout import source

from global_medicines_atlas import mbs_sidecar_package as module
from global_medicines_atlas.mbs_demographic_package import file_fingerprint
from global_medicines_atlas.mbs_sidecar_package import (
    build_sidecar_package,
    verify_sidecar_package,
)


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("csv", b"A,B\n00123,SYNTHETIC\n\n"),
        ("xml", b'<r a=""><c>SYNTHETIC</c>tail</r>'),
        ("text", b"00123\tSYNTHETIC\t\r\n"),
    ],
)
def test_two_complete_packages_and_native_restore_match(
    tmp_path, kind, payload
):
    selected = source(payload, kind)
    first = build_sidecar_package(payload, selected, tmp_path / "one")
    second = build_sidecar_package(payload, selected, tmp_path / "two")
    assert first == second
    assert verify_sidecar_package(tmp_path / "one", payload, selected) == first
    assert first["boundaries"] == {
        "rights_qualified": False,
        "admitted": False,
        "published": False,
        "semantics_qualified": False,
    }
    assert first["coverage"]["records"] > 0
    assert (tmp_path / "one/records.parquet").read_bytes() == (
        tmp_path / "two/records.parquet"
    ).read_bytes()


def test_existing_output_is_preserved(tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    (output / "human.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        build_sidecar_package(b"A\n", source(b"A\n", "csv"), output)
    assert (output / "human.txt").read_text() == "keep"


def test_independent_layout_rejects_a_truncated_producer(tmp_path, monkeypatch):
    payload = b"A,B\n00123,SYNTHETIC\n4,5\n"
    original = module.iter_sidecar_batches

    def truncated(data, selected):
        batches = original(data, selected, rows_per_batch=1)
        try:
            yield next(batches)
        finally:
            batches.close()

    monkeypatch.setattr(module, "iter_sidecar_batches", truncated)
    with pytest.raises(ValueError, match="independent native"):
        build_sidecar_package(payload, source(payload, "csv"), tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "change",
    [
        "value",
        "lineage",
        "schema",
        "extra_record",
        "promotion",
        "coverage",
        "extra_file",
    ],
)
def test_rehashed_corruption_never_establishes_source_parity(tmp_path, change):
    payload = b"A,B\n00123,SYNTHETIC\n"
    selected = source(payload, "csv")
    output = tmp_path / "out"
    build_sidecar_package(payload, selected, output)
    manifest = json.loads((output / "manifest.json").read_bytes())
    path = output / "records.parquet"
    if change in {"value", "lineage", "schema", "extra_record"}:
        table = pq.read_table(path)
        if change == "schema":
            table = table.replace_schema_metadata({
                b"qualification": b"candidate"
            })
        elif change == "extra_record":
            table = pa.concat_tables([table, table.slice(0, 1)])
        else:
            records = table.to_pylist()
            if change == "value":
                records[0]["native_fields"][0]["value"] = "SYNTHETIC TAMPERING"
            else:
                records[0]["acquisition_id"] = "0" * 64
            table = pa.Table.from_pylist(records, schema=table.schema)
        pq.write_table(table, path)
        manifest["files"][path.name] = file_fingerprint(path)
    elif change == "promotion":
        manifest["boundaries"]["admitted"] = True
    elif change == "coverage":
        manifest["coverage"]["records"] += 1
    else:
        (output / "human.txt").write_text("extra")
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="MBS sidecar"):
        verify_sidecar_package(output, payload, selected)


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("csv", b"A,B\n00123,SYNTHETIC\n"),
        ("xml", b'<r a="SYNTHETIC"><c/></r>'),
        ("text", b"00123\tSYNTHETIC\r\n"),
    ],
)
def test_complete_qualification_emits_only_identity_and_coverage(kind, payload):
    report = module.qualify_sidecar_package(payload, source(payload, kind))
    assert report["two_builds_equal"] is True
    assert report["complete_native_restore_verified"] is True
    assert report["duckdb_records"] == report["manifest"]["coverage"]["records"]
    assert "SYNTHETIC" not in json.dumps(report)
    assert report["manifest"]["boundaries"]["admitted"] is False


def test_qualification_rejects_unequal_independent_builds(monkeypatch):
    original = module.build_sidecar_package
    calls = 0

    def changed(payload, selected, output):
        nonlocal calls
        calls += 1
        report = original(payload, selected, output)
        if calls == 2:
            report["output_id"] = "0" * 64
        return report

    monkeypatch.setattr(module, "build_sidecar_package", changed)
    with pytest.raises(ValueError, match="independent builds differ"):
        module.qualify_sidecar_package(b"A\n", source(b"A\n", "csv"))


@pytest.mark.parametrize("result", [None, (999,)])
def test_qualification_rejects_consumer_count_mismatch(monkeypatch, result):
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            return self

        def fetchone(self):
            return result

    monkeypatch.setattr(module.duckdb, "connect", lambda _: FakeConnection())
    with pytest.raises(ValueError, match="DuckDB record denominator"):
        module.qualify_sidecar_package(b"A\n", source(b"A\n", "csv"))
