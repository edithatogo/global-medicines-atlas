"""Versioned PBS verification checks every native field without Arrow replay."""

import json
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_pbs_value_package import inputs

from global_medicines_atlas import pbs_value_package_v2 as module
from global_medicines_atlas.mbs_demographic_package import file_fingerprint
from global_medicines_atlas.pbs_value_package import (
    build_value_package,
    verify_value_package,
)
from global_medicines_atlas.pbs_value_package_v2 import (
    qualify_value_package_pair_v2,
    verify_value_package_v2,
)


def test_v2_package_retains_every_existing_row_and_schema(tmp_path):
    args = inputs()
    build_value_package(*args, tmp_path / "v1")
    result = qualify_value_package_pair_v2(*args, tmp_path / "v2")
    actual = pq.read_table(tmp_path / "v2/first/values.parquet")
    expected = pq.read_table(tmp_path / "v1/values.parquet")
    assert actual.equals(expected, check_metadata=True)
    assert result["package"]["schema_version"] == 2
    assert result["parquet_bytes_identical"] is True
    assert (
        verify_value_package_v2(tmp_path / "v2/first", *args)
        == result["package"]
    )
    assert (
        result["package"]["coverage"]["conversion_statuses"]["unrepresentable"]
        == 1
    )


@pytest.mark.parametrize(
    "change",
    [
        "lineage",
        "field_id",
        "ordinal",
        "mapping",
        "typed",
        "native",
        "schema",
        "truncated",
    ],
)
def test_rehashed_v2_corruption_requires_full_native_and_annotation_parity(
    tmp_path, change
):
    args = inputs()
    qualify_value_package_pair_v2(*args, tmp_path / "pair")
    out = tmp_path / "pair/first"
    table = pq.read_table(out / "values.parquet")
    schema = table.schema
    rows = table.to_pylist()
    field = rows[0]["native_fields"][0]
    if change == "lineage":
        field["receipt_sha256"] = "0" * 64
    elif change == "field_id":
        field["source_field_id"] = "invented"
    elif change == "ordinal":
        field["source_ordinal"] += 1
    elif change == "mapping":
        field["mapping_target"] = "invented"
    elif change == "typed":
        next(row for row in rows if row["mapping_target"] == "prices")[
            "candidate_decimal"
        ] = Decimal(9)
    elif change == "native":
        field["value"] = "SYNTHETIC TAMPERING"
    elif change == "schema":
        schema = schema.with_metadata({**schema.metadata, b"invented": b"true"})
    else:
        rows = rows[:-1]
    pq.write_table(
        pa.Table.from_pylist(rows, schema=schema), out / "values.parquet"
    )
    manifest = json.loads((out / "manifest.json").read_bytes())
    manifest["parquet"] = file_fingerprint(out / "values.parquet")
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="PBS"):
        verify_value_package(out, *args)


@pytest.mark.parametrize("change", ["extra", "coverage", "boundary", "binding"])
def test_v2_rejects_inventory_and_manifest_promotions(tmp_path, change):
    args = inputs()
    qualify_value_package_pair_v2(*args, tmp_path / "pair")
    out = tmp_path / "pair/first"
    manifest = json.loads((out / "manifest.json").read_bytes())
    if change == "extra":
        (out / "extra").write_text("x")
    elif change == "coverage":
        manifest["coverage"]["native_fields"] += 1
    elif change == "boundary":
        manifest["boundaries"]["admitted"] = True
    else:
        manifest["member_binding_sha256"] = "0" * 64
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="PBS"):
        verify_value_package(out, *args)


@pytest.mark.parametrize("limit", [True, 0, -1, 4 * 1024**3 + 1])
def test_v2_rejects_invalid_limits_without_output(tmp_path, limit):
    with pytest.raises(ValueError, match="byte limit"):
        qualify_value_package_pair_v2(
            *inputs(), tmp_path / "out", max_file_bytes=limit
        )
    assert list(tmp_path.iterdir()) == []


def test_v2_progress_and_compatibility_dispatch(tmp_path):
    args = inputs()
    phases = []
    result = qualify_value_package_pair_v2(
        *args,
        tmp_path / "pair",
        progress=lambda phase, _batches, _rows: phases.append(phase),
    )
    assert set(phases) == {
        "package-native-oracle",
        "package-write",
        "package-restore",
    }
    assert (
        verify_value_package(tmp_path / "pair/first", *args)
        == result["package"]
    )
    assert result["independent_pipeline_builds"] is False
    assert result["new_admissions"] == result["publications"] == 0


@pytest.mark.parametrize("change", ["truncated", "interrupted"])
def test_v2_incomplete_producer_cannot_finalize(tmp_path, monkeypatch, change):
    original = module.iter_direct_historical_value_batches

    def altered(*args):
        for batch in original(*args):
            yield batch.slice(0, max(0, batch.num_rows - 1))
            if change == "interrupted":
                raise ValueError("synthetic interrupted producer")
            break

    monkeypatch.setattr(module, "iter_direct_historical_value_batches", altered)
    with pytest.raises(ValueError, match=r"PBS|synthetic"):
        qualify_value_package_pair_v2(*inputs(), tmp_path / "out")
    assert list(tmp_path.iterdir()) == []


def test_v2_byte_limit_cleanup_and_existing_output(tmp_path):
    args = inputs()
    with pytest.raises(ValueError, match="byte limit"):
        qualify_value_package_pair_v2(*args, tmp_path / "out", max_file_bytes=1)
    assert list(tmp_path.iterdir()) == []
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "manual"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        qualify_value_package_pair_v2(*args, out)
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize("change", ["source", "unequal"])
def test_v2_wrong_source_or_unequal_files_never_finalize(
    tmp_path, monkeypatch, change
):
    args = list(inputs())
    if change == "source":
        args[1] += b"changed"
    else:
        original = module.file_fingerprint

        def altered(path):
            value = original(path)
            if path.parent.name == "second":
                value["sha256"] = "0" * 64
            return value

        monkeypatch.setattr(module, "file_fingerprint", altered)
    with pytest.raises(ValueError, match=r"member|builds differ"):
        qualify_value_package_pair_v2(*args, tmp_path / "out")
    assert list(tmp_path.iterdir()) == []
