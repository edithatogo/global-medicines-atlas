"""Complete historical workbook packages require every original native record."""

import json
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_demographic_extraction import workbook
from test_mbs_historical_workbook_native import bound

from global_medicines_atlas import mbs_historical_workbook_package as module
from global_medicines_atlas.mbs_demographic_package import file_fingerprint
from global_medicines_atlas.mbs_historical_workbook_package import (
    build_workbook_package,
    qualify_workbook_member_package,
    verify_workbook_package,
)


def test_two_packages_restore_all_rows_cells_and_lossless_candidates(tmp_path):
    args = bound(
        tmp_path,
        workbook(
            data_row='<c r="A4"><v>1.25</v></c><c r="B4"><v>1.123456789123456789</v></c><c r="C4" t="e"><f>1/0</f><v>#DIV/0!</v></c>'
        ),
    )
    first = build_workbook_package(*args, tmp_path / "one")
    second = build_workbook_package(*args, tmp_path / "two")
    assert first == second
    assert verify_workbook_package(tmp_path / "one", *args) == first
    rows = pq.read_table(tmp_path / "one/records.parquet").to_pylist()
    assert any(r["decimal_candidate"] == Decimal("1.25") for r in rows)
    assert any(r["conversion_status"] == "unrepresentable" for r in rows)
    error = next(r for r in rows if r["native_value"] == "#DIV/0!")
    assert error["formula"] == "1/0"
    assert first["coverage"]["sheets"] == 2
    assert first["coverage"]["rows"] == 5
    assert not any(first["boundaries"].values())


@pytest.mark.parametrize(
    "change", ["native", "decimal", "ordinal", "truncated", "schema"]
)
def test_rehashed_changes_cannot_establish_complete_restore(tmp_path, change):
    args = bound(tmp_path, workbook())
    out = tmp_path / "out"
    build_workbook_package(*args, out)
    path = out / "records.parquet"
    table = pq.read_table(path)
    rows = table.to_pylist()
    schema = table.schema
    if change == "native":
        rows[0]["native_record"] = "{}"
    elif change == "decimal":
        next(r for r in rows if r["record_kind"] == "cell")[
            "decimal_candidate"
        ] = Decimal(9)
    elif change == "ordinal":
        rows[0]["record_ordinal"] += 1
    elif change == "truncated":
        rows = rows[:-1]
    else:
        schema = schema.with_metadata({b"invented": b"true"})
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    report = json.loads((out / "manifest.json").read_bytes())
    report["parquet"] = file_fingerprint(path)
    (out / "manifest.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workbook"):
        verify_workbook_package(out, *args)


def test_complete_pair_uses_actual_duckdb_counts(tmp_path):
    result = qualify_workbook_member_package(*bound(tmp_path, workbook()))
    assert result["two_builds_equal"] is True
    assert result["complete_native_restore_verified"] is True
    assert result["duckdb_cells"] == 18
    assert result["duckdb_rows"] == 5
    assert result["duckdb_sheets"] == 2
    assert result["native_values_or_names_emitted"] is False


@pytest.mark.parametrize("change", ["coverage", "promotion", "extra", "file"])
def test_package_rejects_changed_manifest_and_inventory(tmp_path, change):
    args = bound(tmp_path, workbook())
    out = tmp_path / "out"
    build_workbook_package(*args, out)
    report = json.loads((out / "manifest.json").read_bytes())
    if change == "coverage":
        report["coverage"]["cells"] += 1
    elif change == "promotion":
        report["boundaries"]["semantics_qualified"] = True
    elif change == "extra":
        (out / "extra").write_text("x")
    else:
        with (out / "records.parquet").open("ab") as stream:
            stream.write(b"changed")
    (out / "manifest.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workbook"):
        verify_workbook_package(out, *args)


def test_existing_package_is_preserved(tmp_path):
    args = bound(tmp_path, workbook())
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "manual"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        build_workbook_package(*args, out)
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize("change", ["manifest", "file", "record"])
def test_resource_bounds_fail_closed(tmp_path, monkeypatch, change):
    args = bound(tmp_path, workbook())
    if change == "record":
        monkeypatch.setattr(module, "MAX_BATCH_BYTES", 1)
        with pytest.raises(ValueError, match="batch bound"):
            build_workbook_package(*args, tmp_path / "out")
        assert not (tmp_path / "out").exists()
        return
    out = tmp_path / "out"
    build_workbook_package(*args, out)
    monkeypatch.setattr(
        module,
        "MAX_MANIFEST_BYTES" if change == "manifest" else "MAX_FILE_BYTES",
        1,
    )
    with pytest.raises(ValueError, match="byte bound"):
        verify_workbook_package(out, *args)


@pytest.mark.parametrize("change", ["rows", "bytes"])
def test_bounded_batches_keep_all_records(tmp_path, monkeypatch, change):
    args = bound(tmp_path, workbook())
    if change == "rows":
        monkeypatch.setattr(module, "BATCH_ROWS", 1)
    else:
        monkeypatch.setattr(module, "MAX_BATCH_BYTES", 4096)
    report = build_workbook_package(*args, tmp_path / "out")
    assert report["coverage"]["cells"] == 18
    assert verify_workbook_package(tmp_path / "out", *args) == report


@pytest.mark.parametrize("change", ["builds", "consumer"])
def test_pair_requires_equal_builds_and_exact_consumer_denominators(
    tmp_path, monkeypatch, change
):
    args = bound(tmp_path, workbook())
    original = module.build_workbook_package

    def altered(*values):
        report = original(*values)
        if change == "builds" and values[-1].name == "second":
            report["output_id"] = "0" * 64
        elif change == "consumer":
            report["coverage"]["cells"] += 1
        return report

    monkeypatch.setattr(module, "build_workbook_package", altered)
    with pytest.raises(ValueError, match=r"builds differ|DuckDB denominators"):
        qualify_workbook_member_package(*args)


def test_writer_file_bound_removes_staging(tmp_path, monkeypatch):
    args = bound(tmp_path, workbook())
    monkeypatch.setattr(module, "MAX_FILE_BYTES", 1)
    with pytest.raises(ValueError, match="byte bound"):
        build_workbook_package(*args, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".mbs-native-workbook-*"))
