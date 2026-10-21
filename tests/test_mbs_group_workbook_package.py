"""Complete group workbook packages preserve primary, ancillary and source inventory."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_group_workbook_silver import context, fixture_payload

from global_medicines_atlas import mbs_group_workbook_package as module
from global_medicines_atlas.mbs_demographic_package import file_fingerprint


def test_two_builds_and_source_restore_preserve_all_cells(tmp_path):
    payload = fixture_payload()
    source = context(payload)
    first = module.build_group_workbook_package(
        payload, source, tmp_path / "one"
    )
    second = module.build_group_workbook_package(
        payload, source, tmp_path / "two"
    )
    assert first == second
    assert (
        module.verify_group_workbook_package(tmp_path / "one", payload, source)
        == first
    )
    assert first["coverage"]["native_primary_rows"] == 1
    assert first["coverage"]["native_field_slots"] == 8
    assert first["coverage"]["ancillary_cells"] == 10
    assert first["coverage"]["native_workbook_cells"] == 18
    assert first["coverage"]["benefit_conversion_statuses"] == {
        "unrepresentable": 1
    }
    assert first["boundaries"] == {
        "rights_qualified": False,
        "admitted": False,
        "published": False,
    }
    for name in module.DATA_FILES:
        assert (tmp_path / "one" / name).read_bytes() == (
            tmp_path / "two" / name
        ).read_bytes()


def test_wrong_payload_never_leaves_staging_or_output(tmp_path):
    payload = fixture_payload()
    with pytest.raises(ValueError, match="identity"):
        module.build_group_workbook_package(
            payload + b"changed", context(payload), tmp_path / "out"
        )
    assert list(tmp_path.iterdir()) == []


def test_existing_output_is_preserved(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "human.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        module.build_group_workbook_package(
            fixture_payload(), context(fixture_payload()), out
        )
    assert (out / "human.txt").read_text() == "keep"


@pytest.mark.parametrize(
    "change",
    ["primary", "ancillary", "inventory", "coverage", "promotion", "extra"],
)
def test_restore_rejects_corruption_or_unearned_qualification(tmp_path, change):
    payload = fixture_payload()
    source = context(payload)
    out = tmp_path / "out"
    module.build_group_workbook_package(payload, source, out)
    manifest = json.loads((out / "manifest.json").read_bytes())
    if change in {"primary", "ancillary"}:
        path = out / (change + ".parquet")
        table = pq.read_table(path)
        rows = table.to_pylist()
        if change == "primary":
            rows[0]["native_cells"][0]["value"] = "SYNTHETIC TAMPERING"
        else:
            rows[0]["native_value"] = "SYNTHETIC TAMPERING"
        pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), path)
        manifest["files"][path.name] = file_fingerprint(path)
    elif change == "inventory":
        inventory = json.loads((out / "inventory.json").read_bytes())
        inventory["sheets"][0]["native_cell_count"] += 1
        (out / "inventory.json").write_text(json.dumps(inventory))
        manifest["files"]["inventory.json"] = file_fingerprint(
            out / "inventory.json"
        )
    elif change == "coverage":
        manifest["coverage"]["native_primary_rows"] += 1
    elif change == "promotion":
        manifest["boundaries"]["admitted"] = True
    else:
        (out / "extra").write_text("x")
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="group workbook"):
        module.verify_group_workbook_package(out, payload, source)


@pytest.mark.parametrize(
    "change", ["digest", "schema", "extra_primary", "extra_ancillary"]
)
def test_restore_rejects_storage_and_denominator_tampering(tmp_path, change):
    payload = fixture_payload()
    source = context(payload)
    out = tmp_path / "out"
    module.build_group_workbook_package(payload, source, out)
    manifest = json.loads((out / "manifest.json").read_bytes())
    path = out / (
        "ancillary.parquet"
        if change == "extra_ancillary"
        else "primary.parquet"
    )
    table = pq.read_table(path)
    if change == "digest":
        path.write_bytes(path.read_bytes() + b"changed")
    else:
        if change == "schema":
            table = table.replace_schema_metadata({b"unexpected": b"schema"})
        else:
            table = pa.concat_tables([table, table.slice(0, 1)])
        pq.write_table(table, path)
        manifest["files"][path.name] = file_fingerprint(path)
        (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="group workbook"):
        module.verify_group_workbook_package(out, payload, source)
