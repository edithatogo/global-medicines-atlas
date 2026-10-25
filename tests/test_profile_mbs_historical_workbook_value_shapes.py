"""Exact input and empty-source partition checks for the hosted shape profiler."""

import scripts.profile_mbs_historical_workbook_value_shapes as profiler


def test_bound_inputs_cover_all_91_candidate_and_header_identities():
    header, cohort, field_state, assignments, outputs = profiler._inputs()

    assert header["workbook_count"] == 91
    assert cohort["run_id"] == 39724026209
    assert (
        field_state["historical_workbook_cohort"]["cell_values"]["denominator"]
        == 310177657
    )
    assert len(assignments) == len(outputs) == 91
    assert set(assignments) == set(outputs)


def test_empty_frozen_archive_partition_emits_zero_shape_counts(monkeypatch):
    monkeypatch.setattr(profiler, "require_main_actions", lambda _: None)

    report = profiler.qualify("a" * 40, 4)

    assert report["status"] == "passed"
    assert report["expected_workbook_count"] == report["workbook_count"] == 0
    assert report["workbook_bindings"] == []
    assert report["source_values_emitted"] is False
    assert report["new_sources"] == 0
    assert report["new_admissions"] == 0
    assert report["consumer_canaries"] == 0
    assert report["publications"] == 0
    assert all(field["cell_count"] == 0 for field in report["fields"].values())
