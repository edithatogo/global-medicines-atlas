"""Phase 4 must reflect bounded workbook semantics without promoting values."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PHASE4 = (
    ROOT
    / "quality"
    / "qualifications"
    / "phase4-mandatory-output-delivery-reconciliation-20261028.json"
)
PREVIOUS_PHASE4 = (
    ROOT
    / "quality"
    / "qualifications"
    / "phase4-mandatory-output-delivery-reconciliation-20261027.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase4_reconciliation_binds_bounded_header_evidence() -> None:
    report = _load(PHASE4)
    assert report["recorded_at"] == "2026-10-28T03:00:40Z"
    assert report["supersedes"] == {
        "path": PREVIOUS_PHASE4.relative_to(ROOT).as_posix(),
        "sha256": (
            "48c6ea2bf1eb50790edae6e6f0c5a1a4db31a697eef00a805b0ae69706bb5723"
        ),
    }
    assert report["scope"]["new_sources"] == 0
    assert report["scope"]["inventory_membership_changed"] is False
    assert report["scope"]["publications_performed"] == 0
    cohort = next(
        candidate
        for candidate in report["candidate_obligations"]
        if candidate["name"] == "Historical MBS workbook derived Parquet cohort"
    )
    contract = _load(ROOT / "quality/qualifications/stable-v1-contract.json")
    assert contract["qualification_state"] == "blocked"
    assert contract["unresolved_gate_ids"] == [
        "stable-v1-australian-health-federation"
    ]
    gate = next(
        gate
        for gate in contract["release_gates"]
        if gate["gate_id"] == "stable-v1-australian-health-federation"
    )
    assert gate["state"] == "blocked"
    assert PHASE4.relative_to(ROOT).as_posix() in gate["evidence"]
    requirements = {
        requirement["requirement_id"]: requirement
        for requirement in contract["requirements"]
    }
    for requirement_id in ("M-108", "M-109", "M-112"):
        assert (
            PHASE4.relative_to(ROOT).as_posix()
            in requirements[requirement_id]["evidence"]
        )

    semantics = cohort["header_semantics"]
    semantic_path = ROOT / semantics["receipt"]
    profile_path = ROOT / semantics["header_profile_receipt"]
    value_shape_path = ROOT / cohort["field_state_receipt"]

    semantic_receipt = _load(semantic_path)
    value_shape_receipt = _load(value_shape_path)

    assert _sha256(semantic_path) == semantics["receipt_sha256"]
    assert semantic_receipt["report_sha256"] == semantics["report_sha256"]
    assert _sha256(profile_path) == semantics["header_profile_receipt_sha256"]
    assert _sha256(value_shape_path) == cohort["field_state_receipt_sha256"]

    assert (
        semantics["workbooks"]
        == semantic_receipt["scope"]["workbook_member_count"]
    )
    assert (
        semantics["header_profiles"]
        == semantic_receipt["scope"]["workbook_profile_count"]
    )
    assert (
        semantics["interpreted_header_bindings"]
        == semantic_receipt["scope"]["interpreted_header_bindings"]
    )
    assert semantics["workbooks"] == 91
    assert semantics["interpreted_header_bindings"] == 728
    assert semantic_receipt["scope"]["source_column_meanings_qualified"] is True
    assert (
        semantic_receipt["scope"]["underlying_data_values_interpreted"] is False
    )

    assert semantics["non_header_values_interpreted"] == 0
    assert semantics["non_header_values_native_unresolved"] == (
        value_shape_receipt["source_cell_records"]
        - value_shape_receipt["header_cells"]
    )
    observed_shapes = semantics["observed_value_shapes"]
    archived_fields = [
        field
        for archive in value_shape_receipt["archives"]
        for field in archive["fields"].values()
    ]
    for metric, source_metric in (
        ("formula_cells", "formula_cells"),
        ("formula_cells_with_cache", "formula_cells_with_cache"),
        ("source_error_cells", "source_error_cells"),
        ("missing_value_cells", "native_missing_value_cells"),
    ):
        assert observed_shapes[metric] == sum(
            field[source_metric] for field in archived_fields
        )
    assert observed_shapes["formula_cells"] == 0
    assert observed_shapes["source_error_cells"] == 0
    assert semantics["legacy_p7_included"] is False
    assert semantics["whole_workbook_semantics_complete"] is False
    assert cohort["admissions"] == 0
    assert report["summary"]["additional_admissions"] == 0
    assert report["summary"]["additional_consumer_canaries"] == 0
    assert report["summary"]["additional_eligible_outputs"] == 0
