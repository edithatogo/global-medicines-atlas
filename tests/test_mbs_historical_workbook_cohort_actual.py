"""The retained two-run workbook cohort remains candidate-only."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT
    / "quality/qualifications/mbs-historical-workbook-cohort-20261023-39724026209-39891918206.json"
)
RETRY = {65, 71, 80, 84, 86, 87}


def test_all_frozen_workbooks_have_distinct_candidate_outputs() -> None:
    report = json.loads(REPORT.read_bytes())
    assert report["status"] == "passed"
    assert report["groups"] == 91
    assert report["unique_member_identities"] == 91
    assert report["unique_output_ids"] == 91
    assert report["retry_groups"] == sorted(RETRY)
    assert len(report["receipt_sha256_by_group"]) == 91
    assert len(report["baseline_incomplete_receipt_sha256_by_group"]) == 6
    assert len(report["candidate_outputs_by_group"]) == 91
    outputs = list(report["candidate_outputs_by_group"].values())
    assert len({output["output_id"] for output in outputs}) == 91
    assert (
        len({
            (output["source_sha256"], output["member_path_sha256"])
            for output in outputs
        })
        == 91
    )
    assert {
        int(group)
        for group, origin in report["receipt_origin_by_group"].items()
        if origin["run_id"] == 39891918206
    } == RETRY
    assert report["totals"]["records"] == 348_952_606
    assert report["totals"]["cells"] == 310_177_657
    assert report["silver_field_state_coverage"]["native_unresolved_cells"] == (
        310_177_657
    )
    assert report["silver_field_state_coverage"]["interpreted_cells"] == 0
    assert report["source_column_semantics_qualified"] is False
    assert report["new_admissions"] == 0
    assert report["new_federated_canaries"] == 0
    assert report["publications"] == 0
    for output in outputs:
        assert output["field_state"] == "native_unresolved"
        assert output["rights_qualified"] is False
        assert output["admitted"] is False
        assert output["published"] is False
