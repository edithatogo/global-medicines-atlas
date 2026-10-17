from __future__ import annotations

import json
import sys
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from scripts import qualify_m112_historical_receipt_gate_crosswalk as crosswalk

OUTPUT_PATH = crosswalk.OUTPUT_PATH
build_qualification = crosswalk.build_qualification

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_crosswalk_binds_all_historical_receipts_to_exact_gate_rows() -> None:
    report = build_qualification()
    objects = report["objects"]
    assert report["scope"] == {
        "approved_denominator": 1759,
        "reconciled_paths": 1759,
        "denominator_changed": False,
        "historical_receipt_projection_paths": 14,
        "unmatched_historical_receipt_projections": 0,
    }
    assert len(objects) == 14
    assert len({(item["dataset"], item["path"]) for item in objects}) == 14
    assert all(
        item["gate_row"]["approved_denominator_member"] for item in objects
    )
    assert all(
        item["receipt"]["evidence_class"] == "historical" for item in objects
    )
    assert all(
        item["receipt"]["satisfies_live_gate"] is False for item in objects
    )


def test_crosswalk_keeps_unmet_lifecycle_gates_explicit() -> None:
    report = build_qualification()
    assert report["counts"] == {
        "historical_source_receipt_projections": 14,
        "live_source_receipts": 0,
        "independent_storage_receipts": 0,
        "complete_b1_b2_lineage": 0,
        "v4_admissions": 0,
        "consumer_canaries": 0,
        "preserved_deferred_paths": 1759,
    }
    assert all(
        not item["gate_row"]["b1_b2_lineage_complete"]
        for item in report["objects"]
    )
    assert all(
        not item["gate_row"]["v4_admission"] for item in report["objects"]
    )
    assert all(
        not item["gate_row"]["consumer_canary"] for item in report["objects"]
    )


def test_committed_crosswalk_is_deterministic_and_inputs_are_digest_bound() -> (
    None
):
    committed = _load(ROOT / OUTPUT_PATH)
    rebuilt = build_qualification()
    assert committed == rebuilt
    for reference in committed["inputs"]:
        content = (ROOT / reference["path"]).read_bytes()
        assert sha256(content).hexdigest() == reference["sha256"]


def test_crosswalk_rejects_receipt_to_gate_identity_mismatch() -> None:
    gate_row = {
        "approved_denominator_member": True,
        "b1_b2_lineage": {"complete": False},
        "consumer_canary": False,
        "dataset": "edithatogo/australian-mbs-utilisation-archive",
        "identity": {
            "byte_count": 12,
            "sha256": "a" * 64,
        },
        "path": "raw/example.csv",
        "revision": "b" * 40,
        "v4_admission": False,
    }
    receipt = {
        "evidence_class": "historical",
        "payload": {"byte_count": 12, "sha256": "a" * 64},
        "source": {"source_id": "source-a"},
        "temporal": {"acquisition_id": "c" * 64},
    }
    acquisition = {
        "acquisition_id": "c" * 64,
        "b2_raw_reference": {
            "byte_count": 12,
            "dataset": "edithatogo/australian-mbs-utilisation-archive",
            "path": "raw/different.csv",
            "revision": "b" * 40,
            "sha256": "a" * 64,
            "state": "immutable_public_archive_reference",
        },
    }
    with pytest.raises(
        ValueError, match="does not match the per-object gate row"
    ):
        crosswalk.crosswalk_receipt(
            output={"acquisition_id": "c" * 64, "source_id": "source-a"},
            receipt_path="receipt.json",
            receipt_bytes=b"{}",
            receipt=receipt,
            acquisition=acquisition,
            gate_row=gate_row,
        )
    incomplete_receipt = deepcopy(receipt)
    incomplete_receipt.pop("temporal")
    with pytest.raises(ValueError, match="lacks source, temporal"):
        crosswalk.crosswalk_receipt(
            output={"acquisition_id": "c" * 64, "source_id": "source-a"},
            receipt_path="receipt.json",
            receipt_bytes=b"{}",
            receipt=incomplete_receipt,
            acquisition=acquisition,
            gate_row=gate_row,
        )
    incomplete_gate_row = deepcopy(gate_row)
    incomplete_gate_row.pop("identity")
    with pytest.raises(TypeError, match="no identity"):
        crosswalk.crosswalk_receipt(
            output={"acquisition_id": "c" * 64, "source_id": "source-a"},
            receipt_path="receipt.json",
            receipt_bytes=b"{}",
            receipt=receipt,
            acquisition=acquisition,
            gate_row=incomplete_gate_row,
        )


@pytest.mark.parametrize(
    ("source_name", "mutation", "message", "error_type"),
    [
        ("gate", "short_denominator", "denominator changed", ValueError),
        (
            "acquisition",
            "duplicate_id",
            "duplicate acquisition IDs",
            ValueError,
        ),
        (
            "historical",
            "wrong_gate_hash",
            "not bound to the current gate",
            ValueError,
        ),
        (
            "historical",
            "wrong_receipt_hash",
            "receipt digest mismatch",
            ValueError,
        ),
        (
            "historical",
            "missing_acquisition",
            "no acquisition record",
            ValueError,
        ),
        ("acquisition", "missing_b2", "no immutable B2 reference", TypeError),
        (
            "acquisition",
            "outside_denominator",
            "outside the approved denominator",
            ValueError,
        ),
        (
            "historical",
            "duplicate_receipt",
            "duplicate historical receipt",
            ValueError,
        ),
        ("historical", "short_cohort", "projection cohort changed", ValueError),
        (
            "acquisition",
            "invalid_b2_identity",
            "invalid B2 identity",
            TypeError,
        ),
    ],
)
def test_crosswalk_rejects_stale_or_incomplete_source_evidence(
    monkeypatch: pytest.MonkeyPatch,
    source_name: str,
    mutation: str,
    message: str,
    error_type: type[Exception],
) -> None:
    originals = {
        "gate": crosswalk.GATE_REPORT,
        "historical": crosswalk.HISTORICAL_REPORT,
        "acquisition": crosswalk.ACQUISITION_IMPORT,
    }
    original_read = crosswalk.read_json

    def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
        value, content = original_read(path)
        if path != originals[source_name]:
            return value, content
        value = deepcopy(value)
        if mutation == "short_denominator":
            value["objects"].pop()
        elif mutation == "duplicate_id":
            value["records"].append(deepcopy(value["records"][0]))
        elif mutation == "wrong_gate_hash":
            value["inputs"]["per_object_gate_reconciliation_sha256"] = "0" * 64
        elif mutation == "wrong_receipt_hash":
            value["outputs"][0]["sha256"] = "0" * 64
        elif mutation == "missing_acquisition":
            value["outputs"][0]["acquisition_id"] = "f" * 64
        elif mutation == "missing_b2":
            historical, _ = original_read(originals["historical"])
            target_id = historical["outputs"][0]["acquisition_id"]
            next(
                record
                for record in value["records"]
                if record["acquisition_id"] == target_id
            )["b2_raw_reference"] = None
        elif mutation == "outside_denominator":
            historical, _ = original_read(originals["historical"])
            target_id = historical["outputs"][0]["acquisition_id"]
            next(
                record
                for record in value["records"]
                if record["acquisition_id"] == target_id
            )["b2_raw_reference"]["path"] = "raw/outside.csv"
        elif mutation == "invalid_b2_identity":
            historical, _ = original_read(originals["historical"])
            target_id = historical["outputs"][0]["acquisition_id"]
            next(
                record
                for record in value["records"]
                if record["acquisition_id"] == target_id
            )["b2_raw_reference"]["path"] = None
        elif mutation == "duplicate_receipt":
            value["outputs"].append(deepcopy(value["outputs"][0]))
        elif mutation == "short_cohort":
            value["outputs"].pop()
        return value, content

    monkeypatch.setattr(crosswalk, "read_json", read_json)
    with pytest.raises(error_type, match=message):
        crosswalk.build_qualification()


def test_crosswalk_rejects_non_object_source_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "array.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(crosswalk, "ROOT", tmp_path)
    with pytest.raises(TypeError, match="expected a JSON object"):
        crosswalk.read_json(Path("array.json"))


def test_cli_check_accepts_current_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["qualify_m112_historical_receipt_gate_crosswalk", "--check"],
    )
    assert crosswalk.main() == 0


def test_cli_check_rejects_a_missing_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["qualify_m112_historical_receipt_gate_crosswalk", "--check"],
    )
    monkeypatch.setattr(crosswalk, "ROOT", tmp_path)
    monkeypatch.setattr(crosswalk, "OUTPUT_PATH", Path("missing.json"))
    monkeypatch.setattr(
        crosswalk, "build_qualification", lambda: {"status": "pass"}
    )
    with pytest.raises(SystemExit, match="qualification is stale"):
        crosswalk.main()


def test_cli_write_regenerates_current_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["qualify_m112_historical_receipt_gate_crosswalk"]
    )
    monkeypatch.setattr(crosswalk, "ROOT", tmp_path)
    monkeypatch.setattr(crosswalk, "OUTPUT_PATH", Path("report.json"))
    monkeypatch.setattr(
        crosswalk, "build_qualification", lambda: {"status": "pass"}
    )
    assert crosswalk.main() == 0
    assert json.loads(
        (tmp_path / "report.json").read_text(encoding="utf-8")
    ) == {"status": "pass"}
