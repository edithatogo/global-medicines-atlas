"""Exact input and empty-source partition checks for the hosted shape profiler."""

import subprocess  # ruff: ignore[suspicious-subprocess-import] -- static interpreter and script path smoke test
import sys
from pathlib import Path

import pytest
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
    assert report["field_row_counts"] == dict.fromkeys(
        profiler.EXPECTED_FIELDS, 0
    )
    assert report["source_values_emitted"] is False
    assert report["new_sources"] == 0
    assert report["new_admissions"] == 0
    assert report["consumer_canaries"] == 0
    assert report["publications"] == 0
    assert all(field["cell_count"] == 0 for field in report["fields"].values())


def test_workbook_field_row_counts_are_validated_for_archive_readback():
    counts = dict.fromkeys(profiler.EXPECTED_FIELDS, 4)
    assert profiler._field_row_counts({"field_row_counts": counts}) == counts
    with pytest.raises(TypeError, match="row counts"):
        profiler._field_row_counts({"field_row_counts": []})
    with pytest.raises(ValueError, match="row count identities"):
        profiler._field_row_counts({"field_row_counts": {"unexpected": 1}})
    invalid_count = dict(counts)
    invalid_count[profiler.EXPECTED_FIELDS[0]] = True
    with pytest.raises(ValueError, match="row count identities"):
        profiler._field_row_counts({"field_row_counts": invalid_count})


def test_reconciler_supports_direct_script_help_invocation():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts/reconcile_mbs_historical_workbook_value_shapes.py"
    )
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed args; shell is not invoked
        [sys.executable, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--exact-commit" in result.stdout
