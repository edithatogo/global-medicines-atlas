"""PBS value packages preserve every native field and restore deterministically."""

import json
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE
from test_pbs_native_values import price_payload

from global_medicines_atlas import pbs_value_package as module
from global_medicines_atlas.mbs_demographic_package import file_fingerprint
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_value_package import (
    build_value_package,
    verify_value_package,
)


def inputs():
    xml = price_payload("1.1234567891")
    archive = _zip([(PATH, xml)])
    parent = _receipt(archive, SOURCE)
    return archive, xml, parent, build_pbs_xml_member_binding(archive, parent)


def test_two_builds_and_restore_bind_exact_source_and_conversion_exception(
    tmp_path,
):
    args = inputs()
    first = build_value_package(*args, tmp_path / "one")
    second = build_value_package(*args, tmp_path / "two")
    assert first == second
    assert (tmp_path / "one" / "values.parquet").read_bytes() == (
        tmp_path / "two" / "values.parquet"
    ).read_bytes()
    assert verify_value_package(tmp_path / "one", *args) == first
    assert first["coverage"]["conversion_statuses"]["unrepresentable"] == 1
    assert first["coverage"]["native_fields"] > first["coverage"]["entities"]
    assert first["boundaries"] == {
        "rights_qualified": False,
        "admitted": False,
        "published": False,
        "domain_semantics_qualified": False,
    }
    price = next(
        row
        for row in pq.read_table(
            tmp_path / "one" / "values.parquet"
        ).to_pylist()
        if row["mapping_target"] == "prices"
    )
    assert price["native_text"] == "1.1234567891"
    assert price["candidate_decimal"] is None


def test_existing_output_is_never_overwritten(tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "manual.txt"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        build_value_package(*inputs(), destination)
    assert sentinel.read_text() == "keep"


def test_wrong_member_leaves_no_partial_output(tmp_path):
    archive, xml, parent, binding = inputs()
    with pytest.raises(ValueError, match="member"):
        build_value_package(
            archive, xml + b"changed", parent, binding, tmp_path / "out"
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "change", ["parquet", "extra", "coverage", "boundary", "binding"]
)
def test_restore_rejects_corruption_and_unearned_promotions(tmp_path, change):
    args = inputs()
    out = tmp_path / "out"
    build_value_package(*args, out)
    if change == "parquet":
        with (out / "values.parquet").open("ab") as stream:
            stream.write(b"changed")
    elif change == "extra":
        (out / "extra").write_text("x")
    else:
        manifest = json.loads((out / "manifest.json").read_bytes())
        if change == "coverage":
            manifest["coverage"]["native_fields"] += 1
        elif change == "boundary":
            manifest["boundaries"]["admitted"] = True
        else:
            manifest["member_binding_sha256"] = "0" * 64
        (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="PBS"):
        verify_value_package(out, *args)


@pytest.mark.parametrize("change", ["native", "typed", "schema", "truncated"])
def test_rehashed_parquet_still_requires_source_and_value_parity(
    tmp_path, change
):

    args = inputs()
    out = tmp_path / "out"
    build_value_package(*args, out)
    table = pq.read_table(out / "values.parquet")
    schema = table.schema
    rows = table.to_pylist()
    if change == "native":
        rows[0]["native_fields"][0]["value"] = "SYNTHETIC TAMPERING"
    elif change == "typed":
        price = next(row for row in rows if row["mapping_target"] == "prices")
        price["candidate_decimal"] = Decimal(9)
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
    with pytest.raises(ValueError, match=r"PBS.*differs"):
        verify_value_package(out, *args)


def test_failed_exhaustion_removes_staging_and_never_finalizes(
    tmp_path, monkeypatch
):

    original = module.iter_pbs_historical_value_batches

    def interrupted(*args):
        yield next(iter(original(*args)))
        raise ValueError("synthetic failure after first batch")

    monkeypatch.setattr(
        module, "iter_pbs_historical_value_batches", interrupted
    )
    with pytest.raises(ValueError, match="after first batch"):
        build_value_package(*inputs(), tmp_path / "out")
    assert list(tmp_path.iterdir()) == []
