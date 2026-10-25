from __future__ import annotations

import pytest

from global_medicines_atlas.mbs_historical_value_shape_field_overlay import (
    COHORT_SHA256,
    EXPECTED_WORKFLOW_COMMIT,
    EXPECTED_WORKFLOW_RUN_ID,
    FIELD_STATE_SHA256,
    HEADER_SHA256,
    WORKBOOK_COUNT,
    bind_value_shape_overlay,
)
from global_medicines_atlas.mbs_historical_workbook_value_shapes import (
    EXPECTED_FIELDS,
)


def _field_state() -> dict[str, object]:
    return {
        "schema_id": "global-medicines-atlas.mbs-workbook-field-state-reconciliation",
        "schema_version": 1,
        "status": "field_states_reconciled_with_semantic_limits",
        "historical_workbook_cohort": {
            "workbooks_expected": WORKBOOK_COUNT,
            "candidate_outputs": WORKBOOK_COUNT,
            "cell_values": {
                "denominator": 310_177_657,
                "interpreted": 0,
                "unresolved": 310_177_657,
                "unavailable": 0,
            },
        },
    }


def _shape_report() -> dict[str, object]:
    return {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-value-shape-cohort",
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": EXPECTED_WORKFLOW_COMMIT,
        "archive_count": 6,
        "workbook_count": WORKBOOK_COUNT,
        "input_digests": {
            "header_cohort_sha256": HEADER_SHA256,
            "candidate_cohort_sha256": COHORT_SHA256,
            "field_state_sha256": FIELD_STATE_SHA256,
        },
        "source_values_emitted": False,
        "source_column_meanings_qualified": False,
        "calendar_year_vs_service_year_resolved": False,
        "calendar_month_vs_processing_month_resolved": False,
        "date_interpreted": False,
        "currency_interpreted": False,
        "cross_era_equivalence_claimed": False,
        "fields": {
            field: {
                "cell_count": 2,
                "value_shapes": {"numeric_integer_lexeme": 2},
                "native_cell_types": {"n": 2},
                "native_states": {"value": 2},
                "formula_cells": 1,
                "formula_cells_with_cache": 1,
                "source_error_cells": 0,
                "native_missing_value_cells": 0,
                "missing_physical_cell_positions": 0,
            }
            for field in EXPECTED_FIELDS
        },
    }


def _bind(
    state: dict[str, object], report: dict[str, object]
) -> dict[str, object]:
    return bind_value_shape_overlay(
        state,
        report,
        field_state_sha256=FIELD_STATE_SHA256,
        value_shape_sha256="a" * 64,
        workflow_run_id=EXPECTED_WORKFLOW_RUN_ID,
    )


def test_overlay_adds_diagnostics_without_promoting_field_states() -> None:
    state = _field_state()
    result = _bind(state, _shape_report())

    cohort = result["historical_workbook_cohort"]
    assert isinstance(cohort, dict)
    diagnostics = cohort["value_shape_diagnostics"]
    assert diagnostics["fields"][EXPECTED_FIELDS[0]]["formula_cells"] == 1
    assert diagnostics["fields"][EXPECTED_FIELDS[0]]["value_state"] == (
        "native_unresolved"
    )
    assert (
        cohort["cell_values"]
        == state["historical_workbook_cohort"]["cell_values"]
    )
    assert result["status"].endswith("value_shape_diagnostics")
    assert "value_shape_diagnostics" not in state["historical_workbook_cohort"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("semantic", "exceeds diagnostic scope"),
        ("bad_total", "do not conserve"),
        ("bad_workflow", "cohort identity differs"),
        ("bad_run_id", "workflow run identity differs"),
        ("bad_fields", "field set differs"),
    ],
)
def test_overlay_rejects_unbound_or_promoting_reports(
    mutation: str, message: str
) -> None:
    report = _shape_report()
    if mutation == "semantic":
        report["currency_interpreted"] = True
    elif mutation == "bad_total":
        report["fields"][EXPECTED_FIELDS[0]]["value_shapes"] = {
            "numeric_integer_lexeme": 1
        }
    elif mutation == "bad_workflow":
        report["workflow_commit"] = "0" * 40
    elif mutation == "bad_run_id":
        with pytest.raises(ValueError, match="workflow run identity differs"):
            bind_value_shape_overlay(
                _field_state(),
                report,
                field_state_sha256=FIELD_STATE_SHA256,
                value_shape_sha256="a" * 64,
                workflow_run_id=EXPECTED_WORKFLOW_RUN_ID - 1,
            )
        return
    elif mutation == "bad_fields":
        report["fields"].pop(EXPECTED_FIELDS[0])

    with pytest.raises(ValueError, match=message):
        _bind(_field_state(), report)
