"""Verify the pinned reimbursement and PBS projection lineage evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts import (
    reconcile_m112_reimbursement_medallion_projection_lineage as module,
)

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceManifest,
    RawEvidenceState,
)
from global_medicines_atlas.receipts import AcquisitionEvent, RightsState


def _read(path: str) -> dict[str, Any]:
    return json.loads((module.ROOT / path).read_text(encoding="utf-8"))


def test_frozen_inventory_has_complete_b1_b2_lineage_without_gate_changes() -> (
    None
):
    report = _read(module.OUTPUT.as_posix())
    overlay = _read(module.OVERLAY_OUTPUT.as_posix())
    baseline = _read(module.BASE.as_posix())

    scope = report["scope"]
    assert scope["frozen_inventory_count"] == 1759
    assert scope["projection_path_count"] == 13
    assert scope["new_sources_added"] is False
    assert scope["producer_repository_modified"] is False
    assert scope["payload_values_inspected"] is False
    assert report["lineage_disposition"]["incomplete_configs"] == []
    assert report["lineage_disposition"]["unresolved_input_sha256"] == []

    counts = overlay["lineage_counts_after_expansion"]
    gates = overlay["updated_gate_totals"]
    assert counts["inventory_objects"] == 1759
    assert counts["complete_raw_lineages"] == 1736
    assert counts["incomplete_raw_lineages"] == 0
    assert counts["complete_projection_lineages"] == 23
    assert counts["incomplete_projection_lineages"] == 0
    assert counts["complete_lineage_objects"] == 1759
    assert gates["complete_b1_b2_lineage_objects"] == 1759
    assert gates["exact_raw_digest_path_joins"] == 118
    assert gates["preserved_deferrals"] == 1759
    assert gates["v4_admissions"] == 0
    assert gates["consumer_canaries"] == 0
    assert gates["exact_source_release_rights"] == 2

    baseline_objects = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in baseline["objects"]
    }
    for row in overlay["objects"]:
        assert row["b1_b2_lineage"]["complete"] is True
        original = baseline_objects[
            row["dataset"], row["revision"], row["path"]
        ]
        assert row["rights"] == original["rights"]
        assert row["v4_admission"] == original["v4_admission"]
        assert row["consumer_canary"] == original["consumer_canary"]

    report_bytes = (module.ROOT / module.OUTPUT).read_bytes()
    expected_report_sha = hashlib.sha256(report_bytes).hexdigest()
    assert (
        overlay["projection_b1_b2_lineage_expansion"]["qualification_sha256"]
        == expected_report_sha
    )


def test_cms_reference_only_b1_b2_records_match_report_bindings() -> None:
    report = _read(module.OUTPUT.as_posix())
    records = report["cms_bronze_records"]
    bindings = records["output_bindings"]
    for path, expected_sha in bindings.items():
        actual = hashlib.sha256((module.ROOT / path).read_bytes()).hexdigest()
        assert actual == expected_sha

    event = AcquisitionEvent.model_validate_json(
        (module.ROOT / records["event_path"]).read_bytes()
    )
    manifest = RawEvidenceManifest.model_validate_json(
        (module.ROOT / records["b2_manifest_path"]).read_bytes()
    )
    admission = BronzeAdmissionRecord.model_validate_json(
        (module.ROOT / records["admission_path"]).read_bytes()
    )

    assert event.content_id == module.CMS_SOURCE_SHA256
    assert event.payload_sha256 == module.CMS_SOURCE_SHA256
    assert event.rights_state is RightsState.UNKNOWN
    assert manifest.row_count == 1
    assert manifest.rows[0].state is RawEvidenceState.EXTERNAL_REFERENCE_ONLY
    assert manifest.rows[0].content_id == module.CMS_SOURCE_SHA256
    assert manifest.rows[0].payload_sha256 is None
    assert admission.state is BronzeAdmissionState.LANDED
    assert admission.reviewer_status == "unreviewed"
    assert records["payload_persisted"] is False
    assert records["v4_admission"] is False
    assert records["consumer_canary"] is False


def test_pbs_parquet_projection_is_bound_to_its_existing_b2_archive() -> None:
    report = _read(module.OUTPUT.as_posix())
    projection = report["pbs_source_parquet_lineage"]
    assert projection["lineage_complete"] is True
    assert projection["projection_sha256"] == module.PBS_OUTPUT_SHA256
    assert projection["projection_byte_count"] == module.PBS_OUTPUT_BYTES
    assert projection["source_of_truth_sha256"] == module.PBS_INPUT_SHA256
    assert projection["source_of_truth_byte_count"] == module.PBS_INPUT_BYTES
    assert projection["raw_parent_b1_b2_lineage"]["complete"] is True
    assert projection["source_admission_state"] == "accepted"
    assert projection["payload_values_inspected"] is False
    assert projection["payload_persisted_locally"] is False
    assert projection["m112_rights_state_changed"] is False


def test_existing_cms_readback_is_reused_without_duplicate_acquisition() -> (
    None
):
    reused = module.reuse_cms_readback()
    assert reused is not None
    readback, bronze, artifacts = reused
    assert readback["sha256"] == module.CMS_SOURCE_SHA256
    assert bronze["acquisition_id"] == report_acquisition_id()
    assert set(artifacts) == set(bronze["output_bindings"])


def report_acquisition_id() -> str:
    report = _read(module.OUTPUT.as_posix())
    return report["cms_bronze_records"]["acquisition_id"]
