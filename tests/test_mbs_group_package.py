"""Group candidate packages preserve all native fields without demographic roles."""

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_group_silver import context, csv_payload

from global_medicines_atlas.mbs_demographic_package import file_fingerprint
from global_medicines_atlas.mbs_group_package import (
    build_group_package,
    verify_group_package,
)


def test_group_package_rebuilds_and_restores_deterministically(tmp_path: Path):
    payload = csv_payload()
    first = build_group_package(payload, context(payload), tmp_path / "first")
    second = build_group_package(payload, context(payload), tmp_path / "second")
    assert first == second
    assert first["coverage"]["data_records"] == 1
    assert first["coverage"]["native_field_slots"] == 16
    assert verify_group_package(tmp_path / "first", payload) == first
    assert {p.name: p.read_bytes() for p in (tmp_path / "first").iterdir()} == {
        p.name: p.read_bytes() for p in (tmp_path / "second").iterdir()
    }


def test_failed_source_never_finalizes_output(tmp_path: Path):
    payload = csv_payload() + b"invalid,row\n"
    with pytest.raises(ValueError, match="shape"):
        build_group_package(payload, context(payload), tmp_path / "failed")
    assert not list(tmp_path.iterdir())


def test_existing_package_and_changed_bytes_are_rejected(tmp_path: Path):
    payload = csv_payload()
    output = tmp_path / "package"
    build_group_package(payload, context(payload), output)
    with pytest.raises(FileExistsError):
        build_group_package(payload, context(payload), output)
    with (output / "group.parquet").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="digest"):
        verify_group_package(output, payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("coverage", {}),
        ("candidate_only", False),
        ("source_object_id", "wrong"),
        ("benefit_semantics", {}),
        ("boundaries", {}),
    ],
)
def test_inconsistent_manifest_is_rejected(tmp_path: Path, field, value):
    payload = csv_payload()
    output = tmp_path / "package"
    report = build_group_package(payload, context(payload), output)
    report[field] = value
    (output / "qualification.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match=r"coverage|binding"):
        verify_group_package(output, payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("services_count", 99),
        ("group_native", "other"),
        ("evidence_class", "live"),
        ("physical_line_end", 999),
        ("source_row_id", "other"),
        ("source_object_id", "other"),
        ("native_record_index", 3),
        ("patient_rate_state", "available"),
        ("benefit_interpretation_state", "interpreted"),
    ],
)
def test_rehashed_but_inconsistent_native_output_is_rejected(
    tmp_path: Path, field, value
):
    payload = csv_payload()
    output = tmp_path / "package"
    report = build_group_package(payload, context(payload), output)
    original = pq.read_table(output / "group.parquet")
    rows = original.to_pylist()
    rows[1][field] = value
    pq.write_table(
        pa.Table.from_pylist(rows, schema=original.schema),
        output / "group.parquet",
    )
    report["parquet"] = file_fingerprint(output / "group.parquet")
    (output / "qualification.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="source-field parity"):
        verify_group_package(output, payload)


def test_quoted_multiline_and_blank_strings_are_preserved(tmp_path: Path):
    payload = (
        csv_payload()
        .replace(b"SYNTHETIC-GROUP", b'"SYNTHETIC\nGROUP"')
        .replace(b"SYNTHETIC-STATE", b"")
    )
    report = build_group_package(
        payload, context(payload), tmp_path / "package"
    )
    assert report["coverage"]["data_records"] == 1
    assert verify_group_package(tmp_path / "package", payload) == report
