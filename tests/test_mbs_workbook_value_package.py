"""P7 typed candidates retain native evidence and restore without interpretation."""

import json
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_workbook_silver import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_mbs_workbook_values import payload_with

from global_medicines_atlas import mbs_workbook_value_package as module
from global_medicines_atlas.mbs_workbook_value_package import (
    build_workbook_value_package,
    verify_workbook_value_package,
)


def test_typed_package_rebuild_and_restore_keep_native_evidence(tmp_path: Path):
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>01.07.2024</t></is></c>'
        '<c r="V2"><f>1/3</f><v>0.3333333333333333</v></c>'
    )
    receipt = _receipt(payload)
    first = build_workbook_value_package(payload, receipt, tmp_path / "first")
    second = build_workbook_value_package(payload, receipt, tmp_path / "second")
    assert first == second
    assert (
        verify_workbook_value_package(tmp_path / "first", payload, receipt)
        == first
    )
    assert first["candidate_only"] is True
    assert first["date_profile"] is None
    assert (
        first["coverage"]["unresolved_cells"]
        == first["coverage"]["native_cells"]
    )
    assert first["coverage"]["domain_statuses"]["unrepresentable"] >= 1


def build_fixture(tmp_path):
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>01.07.2024</t></is></c>'
    )
    receipt = _receipt(payload)
    output = tmp_path / "candidate"
    build_workbook_value_package(payload, receipt, output)
    return payload, receipt, output


def test_existing_destination_is_never_replaced(tmp_path):
    payload, receipt, output = build_fixture(tmp_path)
    original = (output / "cells.parquet").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        build_workbook_value_package(payload, receipt, output)
    assert (output / "cells.parquet").read_bytes() == original


@pytest.mark.parametrize(
    "change", ["manifest", "extra", "symlink", "size", "large_manifest"]
)
def test_package_integrity_failures(tmp_path, monkeypatch, change):
    payload, receipt, output = build_fixture(tmp_path)
    if change == "manifest":
        report = json.loads((output / "qualification.json").read_text())
        report["coverage"]["native_cells"] += 1
        (output / "qualification.json").write_text(json.dumps(report))
    elif change == "extra":
        (output / "untracked").write_text("unexpected")
    elif change == "symlink":
        original = output / "cells.parquet"
        original.rename(tmp_path / "outside.parquet")
        original.symlink_to(tmp_path / "outside.parquet")
    elif change == "size":
        monkeypatch.setattr(module, "MAX_PARQUET_BYTES", 1)
    else:
        (output / "qualification.json").write_text(" " * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="P7 candidate"):
        verify_workbook_value_package(output, payload, receipt)


@pytest.mark.parametrize("change", ["value", "schema"])
def test_rehashed_parquet_does_not_override_native_source(tmp_path, change):
    payload, receipt, output = build_fixture(tmp_path)
    table = pq.read_table(output / "cells.parquet")
    if change == "value":
        rows = table.to_pylist()
        rows[0]["raw_value"] = "TAMPERED"
        table = pa.Table.from_pylist(rows, schema=table.schema)
    else:
        table = table.replace_schema_metadata({"schema_name": "counterfeit"})
    pq.write_table(table, output / "cells.parquet")
    report = json.loads((output / "qualification.json").read_text())
    report["parquet"] = module.file_fingerprint(output / "cells.parquet")
    (output / "qualification.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="differs"):
        verify_workbook_value_package(output, payload, receipt)


def test_source_identity_mismatch_leaves_no_package(tmp_path):
    payload = payload_with("")
    with pytest.raises(ValueError, match="payload"):
        build_workbook_value_package(
            payload + b"changed", _receipt(payload), tmp_path / "candidate"
        )
    assert not (tmp_path / "candidate").exists()
    assert list(tmp_path.iterdir()) == []


def test_late_restore_failure_is_transactional(tmp_path, monkeypatch):
    payload = payload_with("")

    def fail(*_args):
        raise ValueError("synthetic restore failed")

    monkeypatch.setattr(module, "verify_workbook_value_package", fail)
    with pytest.raises(ValueError, match="synthetic restore failed"):
        build_workbook_value_package(
            payload, _receipt(payload), tmp_path / "candidate"
        )
    assert list(tmp_path.iterdir()) == []


def test_retained_p7_typed_source_qualification_preserves_unresolved_evidence():
    path = (
        Path(__file__).resolve().parents[1]
        / "quality/qualifications/mbs-p7-typed-qualification-20261022-39636095527.json"
    )
    assert (
        sha256(path.read_bytes()).hexdigest()
        == "26b8952a41dacc2a88df23f6bd2b4c0df7cd9ba91fe29d580e0a5e46016d9929"
    )
    report = json.loads(path.read_text())
    typed = report["typed_candidate_package"]
    assert (
        report["workflow_commit"] == "d7bdaeb8c276eb50617a6d205aa4b97a02fe22c3"
    )
    assert (
        typed["source_sha256"]
        == "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
    )
    assert typed["coverage"]["native_cells"] == 13742
    assert typed["coverage"]["unresolved_cells"] == 13742
    assert typed["coverage"]["formula_cells"] == 4
    assert typed["coverage"]["error_cells"] == 2
    assert typed["coverage"]["domain_statuses"]["unrepresentable"] == 36
    assert typed["coverage"]["domain_statuses"]["unsupported_format"] == 1280
    assert sum(typed["coverage"]["domain_statuses"].values()) == 13742
    assert typed["native_cell_parity_verified"] is True
    assert typed["typed_parquet_restore_verified"] is True
    assert typed["rebuild_equal"] is True
    assert typed["date_profile"] is None
    assert typed["semantic_promotion"] is False
    assert typed["output_admitted"] is False
    assert typed["rights_qualified"] is False
    assert typed["published"] is False
