"""Bind aggregate historical MBS value shapes without semantic promotion."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from .mbs_historical_workbook_value_shapes import EXPECTED_FIELDS

FIELD_STATE_SHA256 = (
    "9cf68711d80142d248bea04eb6ef62c1a768e116891e10c1208a07249bd1481d"
)
HEADER_SHA256 = (
    "5a5858e0a458c46452188a4f52ea396bf1f98c9ce3710d747dd1a58588c196f1"
)
COHORT_SHA256 = (
    "3bbcc74fee209cee521ce6ee85ef87f3ed13df2d202cb1f96effb02274b48546"
)
EXPECTED_WORKFLOW_COMMIT = "7763d510df47e4298175ef5148cbe0998ca09411"
EXPECTED_WORKFLOW_RUN_ID = 40149410629
WORKBOOK_COUNT = 91
ARCHIVE_COUNT = 6
CELL_VALUE_COUNT = 310_177_657
SHA256_HEX_LENGTH = 64


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return cast("dict[str, Any]", value)


def _count(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def bind_value_shape_overlay(  # ruff: ignore[too-many-branches] -- validate the independent field-state and aggregate-cohort bounds
    field_state: dict[str, Any],
    value_shapes: dict[str, Any],
    *,
    field_state_sha256: str,
    value_shape_sha256: str,
    workflow_run_id: int,
) -> dict[str, Any]:
    """Add aggregate shape diagnostics while preserving unresolved states."""
    if (
        field_state_sha256 != FIELD_STATE_SHA256
        or field_state.get("schema_id")
        != "global-medicines-atlas.mbs-workbook-field-state-reconciliation"
        or field_state.get("status")
        != "field_states_reconciled_with_semantic_limits"
    ):
        raise ValueError("bound MBS field-state report differs")
    cohort = _mapping(
        field_state.get("historical_workbook_cohort"),
        "historical workbook field state",
    )
    values = _mapping(cohort.get("cell_values"), "historical workbook values")
    if (
        cohort.get("workbooks_expected") != WORKBOOK_COUNT
        or cohort.get("candidate_outputs") != WORKBOOK_COUNT
    ):
        raise ValueError("historical workbook field-state denominator differs")
    if (
        values.get("denominator") != CELL_VALUE_COUNT
        or values.get("interpreted") != 0
        or values.get("unresolved") != CELL_VALUE_COUNT
        or values.get("unavailable") != 0
    ):
        raise ValueError("historical workbook field-state denominator differs")
    if len(value_shape_sha256) != SHA256_HEX_LENGTH or any(
        char not in "0123456789abcdef" for char in value_shape_sha256
    ):
        raise ValueError("historical value-shape report digest is malformed")
    if workflow_run_id != EXPECTED_WORKFLOW_RUN_ID:
        raise ValueError("historical value-shape workflow run identity differs")
    if (
        value_shapes.get("schema_id")
        != ("global-medicines-atlas.mbs-historical-workbook-value-shape-cohort")
        or value_shapes.get("status") != "passed"
    ):
        raise ValueError("historical value-shape cohort identity differs")
    if (
        value_shapes.get("workflow_commit") != EXPECTED_WORKFLOW_COMMIT
        or value_shapes.get("archive_count") != ARCHIVE_COUNT
        or value_shapes.get("workbook_count") != WORKBOOK_COUNT
        or value_shapes.get("source_values_emitted") is not False
    ):
        raise ValueError("historical value-shape cohort identity differs")
    inputs = _mapping(value_shapes.get("input_digests"), "value-shape inputs")
    if inputs != {
        "header_cohort_sha256": HEADER_SHA256,
        "candidate_cohort_sha256": COHORT_SHA256,
        "field_state_sha256": FIELD_STATE_SHA256,
    }:
        raise ValueError("historical value-shape input binding differs")
    forbidden_claims = (
        "source_column_meanings_qualified",
        "calendar_year_vs_service_year_resolved",
        "calendar_month_vs_processing_month_resolved",
        "date_interpreted",
        "currency_interpreted",
        "cross_era_equivalence_claimed",
    )
    if any(value_shapes.get(key) is not False for key in forbidden_claims):
        raise ValueError("value-shape report exceeds diagnostic scope")
    shape_fields = _mapping(value_shapes.get("fields"), "value-shape fields")
    if set(shape_fields) != set(EXPECTED_FIELDS):
        raise ValueError("historical value-shape field set differs")
    diagnostics: dict[str, Any] = {}
    for field in EXPECTED_FIELDS:
        item = _mapping(shape_fields[field], f"value-shape field {field}")
        cell_count = _count(item.get("cell_count"), "value-shape cell count")
        shapes = _mapping(item.get("value_shapes"), "value shapes")
        native_types = _mapping(item.get("native_cell_types"), "native types")
        states = _mapping(item.get("native_states"), "native states")
        for label, counts in (
            ("value shapes", shapes),
            ("native cell types", native_types),
            ("native states", states),
        ):
            if (
                sum(_count(count, label) for count in counts.values())
                != cell_count
            ):
                raise ValueError(f"historical {label} do not conserve")
        formulas = _count(item.get("formula_cells"), "formula cell count")
        cached = _count(
            item.get("formula_cells_with_cache"), "formula cache count"
        )
        errors = _count(item.get("source_error_cells"), "source error count")
        if formulas > cell_count or cached > formulas or errors > cell_count:
            raise ValueError("historical formula/error counts exceed field")
        diagnostics[field] = {
            "cell_count": cell_count,
            "value_shapes": deepcopy(shapes),
            "native_cell_types": deepcopy(native_types),
            "native_states": deepcopy(states),
            "formula_cells": formulas,
            "formula_cells_with_cache": cached,
            "source_error_cells": errors,
            "native_missing_value_cells": _count(
                item.get("native_missing_value_cells"), "missing value count"
            ),
            "missing_physical_cell_positions": _count(
                item.get("missing_physical_cell_positions"),
                "missing physical cell count",
            ),
            "interpreted_values": 0,
            "native_unresolved_cells": cell_count,
            "unavailable_cells": 0,
            "value_state": "native_unresolved",
        }
    result = deepcopy(field_state)
    result["historical_workbook_cohort"]["value_shape_diagnostics"] = {
        "workflow_commit": EXPECTED_WORKFLOW_COMMIT,
        "workflow_run_id": workflow_run_id,
        "value_shape_report_sha256": value_shape_sha256,
        "source_values_emitted": False,
        "semantic_interpretation": False,
        "field_states_changed": False,
        "fields": diagnostics,
    }
    result["status"] = (
        "field_states_reconciled_with_semantic_limits_and_value_shape_diagnostics"
    )
    return result
