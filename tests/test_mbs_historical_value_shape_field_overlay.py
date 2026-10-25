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


@pytest.mark.parametrize(
    "target",
    [
        "cohort",
        "cell_values",
        "fields",
    ],
)
def test_overlay_rejects_non_object_sections(target: str) -> None:
    state = _field_state()
    report = _shape_report()
    if target == "cohort":
        state["historical_workbook_cohort"] = None
    elif target == "cell_values":
        state["historical_workbook_cohort"]["cell_values"] = None
    else:
        report["fields"] = None

    with pytest.raises(TypeError, match="must be an object"):
        _bind(state, report)


@pytest.mark.parametrize(
    ("target", "bad_value"),
    [
        ("cell_count", True),
        ("cell_count", -1),
        ("shape_count", "2"),
    ],
)
def test_overlay_rejects_invalid_counts(target: str, bad_value: object) -> None:
    report = _shape_report()
    field = report["fields"][EXPECTED_FIELDS[0]]
    if target == "cell_count":
        field["cell_count"] = bad_value
    else:
        field["value_shapes"]["numeric_integer_lexeme"] = bad_value

    with pytest.raises(ValueError, match="must be a nonnegative integer"):
        _bind(_field_state(), report)


@pytest.mark.parametrize(
    ("target", "bad_value"),
    [
        ("digest", "0" * 64),
        ("schema_id", "wrong-schema"),
        ("status", "wrong-status"),
    ],
)
def test_overlay_rejects_mismatched_field_state_binding(
    target: str, bad_value: str
) -> None:
    state = _field_state()
    field_state_sha256 = FIELD_STATE_SHA256
    if target == "digest":
        field_state_sha256 = bad_value
    else:
        state[target] = bad_value

    with pytest.raises(ValueError, match="bound MBS field-state report differs"):
        bind_value_shape_overlay(
            state,
            _shape_report(),
            field_state_sha256=field_state_sha256,
            value_shape_sha256="a" * 64,
            workflow_run_id=EXPECTED_WORKFLOW_RUN_ID,
        )


@pytest.mark.parametrize("target", ["workbooks_expected", "candidate_outputs"])
def test_overlay_rejects_workbook_denominator_mismatch(target: str) -> None:
    state = _field_state()
    state["historical_workbook_cohort"][target] -= 1

    with pytest.raises(
        ValueError, match="historical workbook field-state denominator differs"
    ):
        _bind(state, _shape_report())


@pytest.mark.parametrize(
    ("target", "bad_value"),
    [
        ("denominator", 1),
        ("interpreted", 1),
        ("unresolved", 1),
        ("unavailable", 1),
    ],
)
def test_overlay_rejects_cell_value_state_denominator_mismatch(
    target: str, bad_value: int
) -> None:
    state = _field_state()
    state["historical_workbook_cohort"]["cell_values"][target] = bad_value

    with pytest.raises(
        ValueError, match="historical workbook field-state denominator differs"
    ):
        _bind(state, _shape_report())


@pytest.mark.parametrize("bad_digest", ["a" * 63, "a" * 63 + "g"])
def test_overlay_rejects_malformed_value_shape_digest(bad_digest: str) -> None:
    with pytest.raises(ValueError, match="value-shape report digest is malformed"):
        bind_value_shape_overlay(
            _field_state(),
            _shape_report(),
            field_state_sha256=FIELD_STATE_SHA256,
            value_shape_sha256=bad_digest,
            workflow_run_id=EXPECTED_WORKFLOW_RUN_ID,
        )


@pytest.mark.parametrize(
    ("target", "bad_value"),
    [
        ("schema_id", "wrong-schema"),
        ("status", "wrong-status"),
    ],
)
def test_overlay_rejects_value_shape_schema_or_status_mismatch(
    target: str, bad_value: str
) -> None:
    report = _shape_report()
    report[target] = bad_value

    with pytest.raises(ValueError, match="historical value-shape cohort identity differs"):
        _bind(_field_state(), report)


@pytest.mark.parametrize(
    ("target", "bad_value"),
    [
        ("header_cohort_sha256", "0" * 64),
        ("candidate_cohort_sha256", "0" * 64),
        ("field_state_sha256", "0" * 64),
    ],
)
def test_overlay_rejects_input_digest_mismatch(target: str, bad_value: str) -> None:
    report = _shape_report()
    report["input_digests"][target] = bad_value

    with pytest.raises(ValueError, match="historical value-shape input binding differs"):
        _bind(_field_state(), report)


@pytest.mark.parametrize(
    ("target", "bad_value"),
    [
        ("formula_cells", 3),
        ("formula_cells_with_cache", 2),
        ("source_error_cells", 3),
    ],
)
def test_overlay_rejects_formula_and_error_counts_above_field(
    target: str, bad_value: int
) -> None:
    report = _shape_report()
    report["fields"][EXPECTED_FIELDS[0]][target] = bad_value

    with pytest.raises(ValueError, match="historical formula/error counts exceed field"):
        _bind(_field_state(), report)
