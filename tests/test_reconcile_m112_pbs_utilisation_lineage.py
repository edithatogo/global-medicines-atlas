"""Verify cumulative M-112 PBS utilisation lineage accounting."""

from __future__ import annotations

from scripts.reconcile_m112_pbs_utilisation_lineage import (
    EXPECTED_ADDITIONS,
    build_report,
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
