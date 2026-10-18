"""Verify the 14-object MBS utilisation lineage increment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.reconcile_m112_historical_mbs_utilisation_lineages import (
    BASE_OVERLAY,
    EXPECTED_COMPLETE,
    EXPECTED_NEW_COMPLETE,
    EXPECTED_PRIOR_COMPLETE,
    LINEAGE_QUALIFICATION,
    OUTPUT,
    build_report,
)

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
)
from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return cast("dict[str, Any]", value)


def test_mbs_utilisation_lineages_are_complete_and_separate_from_other_gates() -> (
    None
):
    report = build_report()
    qualification = _read(LINEAGE_QUALIFICATION)
    baseline = _read(BASE_OVERLAY)
    committed = _read(OUTPUT)

    assert report == committed
    assert len(qualification["objects"]) == EXPECTED_NEW_COMPLETE
    assert report["updated_gate_totals"]["approved_denominator"] == 1759
    assert (
        report["updated_gate_totals"]["complete_raw_b1_b2_lineage"]
        == EXPECTED_COMPLETE
    )
    assert report["updated_gate_totals"]["v4_admissions"] == 0
    assert report["updated_gate_totals"]["consumer_canaries"] == 0
    assert report["updated_gate_totals"]["preserved_deferrals"] == 1759
    expansion = report["current_b1_b2_lineage_expansion"]
    assert expansion["prior_complete_lineages"] == EXPECTED_PRIOR_COMPLETE
    assert expansion["new_complete_lineages"] == EXPECTED_NEW_COMPLETE
    assert expansion["complete_lineages_after_expansion"] == EXPECTED_COMPLETE
    assert len(expansion["objects"]) == EXPECTED_NEW_COMPLETE

    before = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in baseline["objects"]
    }
    after = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in report["objects"]
    }
    changed = {key for key in before if before[key] != after[key]}
    expected = {
        (item["dataset"], item["revision"], item["path"])
        for item in qualification["objects"]
    }
    assert changed == expected
    for key in expected:
        assert before[key]["rights"] == after[key]["rights"]
        assert before[key]["v4_admission"] == after[key]["v4_admission"]
        assert before[key]["consumer_canary"] == after[key]["consumer_canary"]
        assert after[key]["b1_b2_lineage"]["complete"] is True

    for item in qualification["objects"]:
        admission = BronzeAdmissionRecord.model_validate_json(
            (ROOT / item["landed_admission_path"]).read_bytes()
        )
        b2 = RawEvidenceManifest.model_validate_json(
            (ROOT / item["b2_manifest_path"]).read_bytes()
        )
        assert admission.state is BronzeAdmissionState.LANDED
        assert admission.reviewer_status == "unreviewed"
        assert admission.acquisition_id == item["acquisition_id"]
        assert admission.content_id == item["content_sha256"]
        assert b2.row_count == 1
        assert b2.rows[0].external_reference is not None
        assert b2.rows[0].payload_sha256 is None
        assert b2.rows[0].byte_count is None
