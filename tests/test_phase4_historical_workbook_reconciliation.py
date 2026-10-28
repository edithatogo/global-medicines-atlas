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
    / "phase4-mandatory-output-delivery-reconciliation-20261028-2.json"
)
PREVIOUS_PHASE4 = (
    ROOT
    / "quality"
    / "qualifications"
    / "phase4-mandatory-output-delivery-reconciliation-20261028.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase4_reconciliation_binds_bounded_header_evidence() -> None:
    report = _load(PHASE4)
    assert report["recorded_at"].startswith("2026-10-28T")
    assert report["supersedes"] == {
        "path": PREVIOUS_PHASE4.relative_to(ROOT).as_posix(),
        "sha256": _sha256(PREVIOUS_PHASE4),
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


def test_phase4_outside_m112_outputs_bind_the_exact_attested_scope() -> None:
    report = _load(PHASE4)
    candidate = next(
        item
        for item in report["candidate_obligations"]
        if item["name"] == "August 2026 MBS Bronze projections outside M-112"
    )
    rights_path = ROOT / candidate["rights_attestation"]
    scope_path = ROOT / candidate["scope_exception_receipt"]
    rights = _load(rights_path)
    scope = _load(scope_path)
    frozen = _load(
        ROOT
        / "quality/qualifications/australian-m112-frozen-object-inventory-20261018.json"
    )

    assert candidate["rights_attestation_sha256"] == _sha256(rights_path)
    assert candidate["scope_exception_sha256"] == _sha256(scope_path)
    assert candidate["object_count"] == len(rights["authorized_objects"]) == 4
    assert candidate["objects"] == [
        {
            "path": row["path"],
            "sha256": row["sha256"],
            "byte_count": row["byte_count"],
            "product_id": row["path"].split("/")[4],
            "in_frozen_m112_inventory": False,
            "rights_attestation": candidate["rights_attestation"],
            "identity_readback_revision": row["revision"],
        }
        for row in rights["authorized_objects"]
    ]
    assert all(
        row["path"] not in {item["path"] for item in frozen["members"]}
        for row in candidate["objects"]
    )
    assert candidate["federation_v4_admissions"] == 0
    assert {row["product_id"] for row in candidate["products"]} == {
        "d78170f1944e8c209833b86193d403b12553a3932579dc571ff10f8485a6483b",
        "f9f9af5a152ea74c25a617102e3cf271054ef78867ed0eb84fb69822b6767d63",
    }
    f9_product = next(
        row
        for row in candidate["products"]
        if row["product_id"].startswith("f9f9")
    )
    assert f9_product["bronze_parser_admission"] == (
        "unadmitted_no_admission_sidecar"
    )
    assert scope["scope"]["outside_frozen_inventory_object_count"] == 4

    readiness = _load(
        ROOT
        / "quality/qualifications/stable-v1-release-readiness-reconciliation.json"
    )
    contract_path = ROOT / "quality/qualifications/stable-v1-contract.json"
    assert readiness["contract"]["sha256"] == _sha256(contract_path)
    assert {
        (row["path"], row["sha256"])
        for row in readiness["current_evidence_reconciliation"][
            "system_receipts"
        ]
        if row["path"] == PHASE4.relative_to(ROOT).as_posix()
    } == {
        (
            PHASE4.relative_to(ROOT).as_posix(),
            _sha256(PHASE4),
        )
    }
