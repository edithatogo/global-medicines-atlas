"""Deterministic candidate packages retain primary and ancillary evidence."""

import json
from pathlib import Path

import pytest
from test_mbs_demographic_extraction import workbook
from test_mbs_demographic_silver import source

from global_medicines_atlas.mbs_demographic_package import (
    build_demographic_package,
    verify_demographic_package,
)


def test_workbook_package_is_deterministic_and_restores(tmp_path: Path):
    payload = workbook()
    context = source("workbook", payload)
    first = build_demographic_package(payload, context, tmp_path / "first")
    second = build_demographic_package(payload, context, tmp_path / "second")
    assert first == second
    assert first["coverage"][context.object_id]["native_rows"] == 1
    assert first["ancillary_cells"] == 10
    assert first["native_workbook_cells"] == 18
    assert verify_demographic_package(tmp_path / "first") == first
    assert {p.name: p.read_bytes() for p in (tmp_path / "first").iterdir()} == {
        p.name: p.read_bytes() for p in (tmp_path / "second").iterdir()
    }


def test_partial_extraction_leaves_no_package(tmp_path: Path):
    payload = workbook(header=("wrong", *source("workbook").headers[1:]))
    with pytest.raises(ValueError, match="header"):
        build_demographic_package(
            payload, source("workbook", payload), tmp_path / "failed"
        )
    assert not list(tmp_path.iterdir())


def test_restore_rejects_mutation_and_build_preserves_existing(tmp_path: Path):
    payload = workbook()
    output = tmp_path / "package"
    build_demographic_package(payload, source("workbook", payload), output)
    with pytest.raises(FileExistsError):
        build_demographic_package(payload, source("workbook", payload), output)
    with (output / "primary.parquet").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="digest"):
        verify_demographic_package(output)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_object_id", "wrong"),
        ("candidate_only", False),
        ("ancillary_cells", 999),
        ("native_workbook_cells", 999),
        ("coverage", {}),
        ("benefit_semantics", {}),
        ("files", {}),
        ("limits", {}),
    ],
)
def test_restore_rejects_inconsistent_report(tmp_path: Path, field, value):
    payload = workbook()
    output = tmp_path / "package"
    report = build_demographic_package(
        payload, source("workbook", payload), output
    )
    report[field] = value
    (output / "qualification.json").write_text(json.dumps(report))
    with pytest.raises(
        ValueError, match=r"binding|coverage|accounting|inventory"
    ):
        verify_demographic_package(output)


def test_csv_package_restores_native_unknown_and_blank(tmp_path: Path):
    payload = b"Year,Month of Processing,Item Number,State,Age Range,Gender,Services,Benefit\n2016,3,00123,SYNTHETIC,Unknown,F,2,12.5\n2016,3,00124,SYNTHETIC,,F,0,\n"
    context = source("csv", payload)
    report = build_demographic_package(payload, context, tmp_path / "csv")
    assert (
        report["coverage"][context.object_id]["literal_unknown_age_rows"] == 1
    )
    assert report["ancillary_cells"] == 8
    assert report["native_workbook_cells"] == 0
    assert verify_demographic_package(tmp_path / "csv") == report


def test_ancillary_batches_and_unknown_files(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "global_medicines_atlas.mbs_demographic_package.BATCH_ROWS", 1
    )
    payload = workbook()
    output = tmp_path / "package"
    report = build_demographic_package(
        payload, source("workbook", payload), output
    )
    assert report["ancillary_cells"] == 10
    (output / "unexpected.json").write_text("{}")
    with pytest.raises(ValueError, match="inventory"):
        verify_demographic_package(output)
