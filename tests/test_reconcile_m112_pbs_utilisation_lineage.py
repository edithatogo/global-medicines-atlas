"""Verify cumulative M-112 PBS utilisation lineage accounting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import reconcile_m112_pbs_utilisation_lineage as module
from scripts.reconcile_m112_pbs_utilisation_lineage import (
    EXPECTED_ADDITIONS,
    build_report,
)

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
)


def test_cumulative_report_adds_only_the_six_qualified_pbs_objects() -> None:
    report = build_report()
    assert len(report["objects"]) == 1759
    assert report["updated_gate_totals"]["complete_raw_b1_b2_lineage"] == 1731
    assert report["updated_gate_totals"]["complete_projection_lineage"] == 10
    assert (
        report["updated_gate_totals"]["complete_b1_b2_lineage_objects"] == 1741
    )
    assert (
        report["lineage_counts_after_expansion"]["incomplete_raw_lineages"] == 5
    )
    assert (
        report["lineage_counts_after_expansion"][
            "incomplete_projection_lineages"
        ]
        == 13
    )
    assert report["updated_gate_totals"]["preserved_deferrals"] == 1759
    assert report["updated_gate_totals"]["v4_admissions"] == 0
    assert report["updated_gate_totals"]["consumer_canaries"] == 0
    assert "PBS utilisation" in report["purpose"]
    assert report["observed_at"] == "2026-10-18T22:37:23Z"
    assert report["boundaries"]["projection_bytes_streamed_this_run"] == 0
    assert report["boundaries"]["source_payload_bytes_read_this_run"] is False
    assert report["boundaries"]["source_payload_bytes_streamed_this_run"] == 0
    assert (
        report["boundaries"]["receipt_sidecar_metadata_bytes_read_this_run"]
        == 4226
    )
    assert (
        report["pbs_utilisation_lineage_increment"]["new_complete_raw_lineages"]
        == EXPECTED_ADDITIONS
    )

    changed = [
        row
        for row in report["objects"]
        if row["dataset"] == "edithatogo/australian-pbs-utilisation-archive"
    ]
    assert len(changed) == EXPECTED_ADDITIONS
    for row in changed:
        assert row["b1_b2_lineage"]["complete"] is True
        assert row["disposition"] == "deferred_not_admitted"
        assert (
            row["rights"]["state"]
            == "source-specific rights review absent; per-object sidecar has no rights_state"
        )
        assert row["v4_admission"] is False
        assert row["consumer_canary"] is False


def test_non_landed_admission_cannot_complete_lineage() -> None:
    lineage = json.loads(
        (
            module.ROOT
            / "quality/qualifications/australian-pbs-utilisation-landed-lineage-20261019.json"
        ).read_text(encoding="utf-8")
    )
    item = lineage["objects"][0]
    admission = BronzeAdmissionRecord.model_validate_json(
        (module.ROOT / Path(item["landed_admission_path"])).read_bytes()
    )
    non_landed = admission.model_copy(
        update={"state": BronzeAdmissionState.ACCEPTED}
    )

    with pytest.raises(ValueError, match="admission is not landed"):
        module.require_landed_admission(non_landed)
