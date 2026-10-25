"""Reconcile value-free field states for the retained MBS workbook cohorts."""

from __future__ import annotations

import copy
import hashlib
import json
import operator
from pathlib import Path
from typing import Any, cast

from .mbs_archive_inventory import (
    DATASET as MBS_DATASET,
)
from .mbs_archive_inventory import (
    REVISION as MBS_REVISION,
)
from .mbs_historical_workbook_value_shapes import EXPECTED_FIELDS
from .mbs_p7_date_consistency import validate_p7_date_consistency_inference

PACKAGE_PATH = (
    "quality/qualifications/mbs-historical-workbook-cohort-"
    "20261023-39724026209-39891918206.json"
)
HEADER_PATH = (
    "quality/qualifications/mbs-historical-workbook-header-cohort-"
    "20261024-40040624592.json"
)
P7_TYPED_PATH = (
    "quality/qualifications/mbs-p7-workbook-storage-qualification-"
    "20261024-40094025412.json"
)
P7_RUN_RECEIPT_PATH = (
    "quality/qualifications/mbs-p7-exact-main-run-receipt-"
    "20261024-40094025412.json"
)
P7_DATE_PROFILE_PATH = (
    "quality/qualifications/mbs-p7-calendar-profile-20261024-40088209026.json"
)
P7_DATE_INFERENCE_PATH = (
    "quality/qualifications/"
    "mbs-p7-date-consistency-inference-20261025-40139026116.json"
)
P7_DATE_INFERENCE_SHA256 = (
    "a9df045f3893c0f2774d80a2a0d806ad19c17c4d7173da64bde57d1169e06486"
)
P7_DATE_RECONCILIATION_PATH = (
    "quality/qualifications/mbs-p7-date-profile-reconciliation-20261025.json"
)
P7_DATE_RECONCILIATION_SHA256 = (
    "125c1f13acb33c40dcb45355772b5bb03fa8a89b36124195f96b55cd9f279853"
)
P7_SOURCE_SHA256 = (
    "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
)
P7_SOURCE_BYTE_COUNT = 87_727
P7_RULES_PATH = "quality/qualifications/mbs-p7-value-era-rules-20261024.json"
WORKBOOK_COUNT = 91
MBS_ARCHIVE_COUNT = 6
MBS_COHORT_RUN_ID = 39724026209
P7_CELL_COUNT = 13_742
P7_HEADER_CELL_COUNT = 97
P7_VALUE_CELL_COUNT = 13_645
P7_UNIQUE_INTERPRETED_DATE_CELLS = 86
P7_INFERENCE_INTERPRETED_DATE_CELLS = 1_194
P7_INTERPRETED_DATE_CELLS = (
    P7_UNIQUE_INTERPRETED_DATE_CELLS + P7_INFERENCE_INTERPRETED_DATE_CELLS
)
P7_RETAINED_UNRESOLVED_CELL_COUNT = 13_656
P7_RETAINED_UNRESOLVED_VALUE_COUNT = 13_559
P7_CANDIDATE_UNRESOLVED_CELL_COUNT = 12_462
P7_CANDIDATE_UNRESOLVED_VALUE_COUNT = 12_365
P7_EXACT_MAIN_RUN_ID = 40094025412
P7_EXACT_MAIN_COMMIT = "11be72e328affc0df87395fd59165ef4f5bf9055"
P7_EXACT_MAIN_ARTIFACT_ID = 12559848688
SHA256_HEX_LENGTH = 64
GIT_COMMIT_HEX_LENGTH = 40
P7_STATUS_PAIR_LENGTH = 2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("receipt root must be an object")
    return cast("dict[str, Any]", value)


def _validate_p7_date_reconciliation(
    report: dict[str, Any], digest: str
) -> dict[str, Any]:
    """Bind the narrow, value-free P7 internal consistency reconciliation."""
    source = _dict(report.get("source"), "P7 date reconciliation source")
    reconciliation = _dict(
        report.get("reconciliation"), "P7 date reconciliation"
    )
    evidence = _dict(
        reconciliation.get("evidence_counts"),
        "P7 date reconciliation evidence counts",
    )
    limits = _dict(
        report.get("operational_limits"), "P7 date reconciliation limits"
    )
    checks = [
        digest == P7_DATE_RECONCILIATION_SHA256,
        report.get("schema_id")
        == "global-medicines-atlas.mbs-p7-date-profile-reconciliation",
        report.get("schema_version") == 1,
        report.get("status")
        == "internal_exact_copy_dmy_inference_reconciled_conversion_disabled",
        source.get("sha256") == P7_SOURCE_SHA256,
        source.get("byte_count") == P7_SOURCE_BYTE_COUNT,
        source.get("schema_era") == "mbs-p7-2024-07-headers-v1",
        reconciliation.get("inferred_profile") == "mbs-dmy",
        reconciliation.get("inference_scope")
        == "internal_file_consistency_for_this_exact_donor_archived_copy_only",
        reconciliation.get("profile_selection_status")
        == "selected_as_internal_consistency_inference",
        evidence
        == {
            "populated_date_fields": 4,
            "profiled_cells": 1_280,
            "ambiguous_calendar_order_cells_before_inference": 1_194,
            "unique_dmy_calendar_date_cells": 4,
            "unique_mdy_calendar_date_cells": 0,
            "unique_calendar_date_cells": 86,
        },
        limits.get("operational_date_conversion_enabled") is False,
        limits.get("source_owner_confirmation") is False,
        limits.get("official_provenance_confirmed") is False,
        limits.get("domain_date_meaning_qualified") is False,
        limits.get("temporal_comparison_enabled") is False,
        limits.get("cross_era_equivalence_promoted") is False,
        limits.get("other_workbooks_or_eras_in_scope") is False,
        limits.get("source_values_emitted") is False,
    ]
    if not all(checks):
        raise ValueError("P7 date reconciliation evidence binding differs")
    return {
        "date_fields_with_populated_values": [
            "BenefitStartDate",
            "DescriptionStartDate",
            "FeeStartDate",
            "ItemStartDate",
        ]
    }


def _int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _dict_list(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a list of objects")
    rows = cast("list[Any]", value)
    if any(not isinstance(row, dict) for row in rows):
        raise TypeError(f"{label} must be a list of objects")
    return cast("list[dict[str, Any]]", value)


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return cast("dict[str, Any]", value)


def _candidate_identity(row: dict[str, Any]) -> tuple[str, str, str]:
    parts = tuple(
        row.get(key)
        for key in ("source_sha256", "member_path_sha256", "member_sha256")
    )
    if any(
        not isinstance(part, str) or len(part) != SHA256_HEX_LENGTH
        for part in parts
    ):
        raise ValueError("workbook candidate identity is malformed")
    return cast("tuple[str, str, str]", parts)


def _candidate_hosted_run_matches(
    exact_run: dict[str, Any], p7_typed: dict[str, Any]
) -> bool:
    run_id = exact_run.get("run_id")
    url = exact_run.get("url")
    return not any([
        exact_run.get("conclusion") != "success",
        exact_run.get("python") != "3.15.1",
        type(run_id) is not int,
        run_id <= 0 if type(run_id) is int else True,
        run_id == P7_EXACT_MAIN_RUN_ID,
        exact_run.get("exact_commit") != p7_typed.get("workflow_commit"),
        url != p7_typed.get("workflow_run"),
        not isinstance(url, str),
        not url.startswith(
            "https://github.com/edithatogo/global-medicines-atlas/actions/runs/"
        )
        if isinstance(url, str)
        else True,
        not url.endswith(f"/{run_id}") if isinstance(url, str) else True,
    ])


def _profile_field_rows(
    profile_by_digest: dict[str, dict[str, Any]],
    member_counts: dict[str, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    status_map = {
        "interpreted": "interpreted",
        "unresolved": "native_unresolved",
        "native_unresolved": "native_unresolved",
        "unavailable": "unavailable",
    }
    for digest in sorted(profile_by_digest):
        profile = profile_by_digest[digest]
        sheets = _dict_list(profile.get("sheets"), "header profile sheets")
        for sheet in sheets:
            sheet_ordinal = _int(sheet.get("ordinal"), "sheet ordinal")
            candidates = _dict_list(
                sheet.get("candidate_rows"), "header profile candidates"
            )
            for candidate in candidates:
                row_index = _int(
                    candidate.get("row_index"), "candidate row index"
                )
                bindings = _dict_list(
                    candidate.get("column_bindings", []),
                    "header column bindings",
                )
                for binding in bindings:
                    column = binding.get("column")
                    status = binding.get("status")
                    state = (
                        status_map.get(status)
                        if isinstance(status, str)
                        else None
                    )
                    if not isinstance(column, str) or state is None:
                        raise ValueError("header field binding is malformed")
                    field = binding.get("field")
                    if state == "interpreted" and not isinstance(field, str):
                        raise ValueError(
                            "interpreted header binding lacks a field"
                        )
                    rows.append({
                        "header_profile_sha256": digest,
                        "workbooks_represented": member_counts[digest],
                        "sheet_ordinal": sheet_ordinal,
                        "candidate_row_index": row_index,
                        "column": column,
                        "field": field if isinstance(field, str) else None,
                        "header_state": state,
                        "source_value_state": "native_unresolved",
                    })
    return rows


def _p7_field_rows(
    p7_typed: dict[str, Any],
) -> list[dict[str, Any]]:
    lineage = _dict(
        p7_typed.get("workbook_field_lineage"), "P7 workbook field lineage"
    )
    fields = _dict_list(lineage.get("fields"), "P7 lineage fields")
    domain_profile = _dict(
        p7_typed.get("domain_value_profile"), "P7 typed value profile"
    )
    if lineage.get("source_sha256") != domain_profile.get("source_sha256"):
        raise ValueError("P7 field lineage source identity differs")
    if (
        sum(
            _int(row.get("cell_count"), "P7 field cell count") for row in fields
        )
        != P7_CELL_COUNT
    ):
        raise ValueError("P7 field rows differ from cell denominator")
    rows: list[dict[str, Any]] = []
    for row in fields:
        cell_count = _int(row.get("cell_count"), "P7 field cell count")
        statuses_raw = row.get("statuses")
        if not isinstance(statuses_raw, list):
            raise TypeError("P7 field conversion statuses are malformed")
        statuses: list[dict[str, Any]] = []
        for item in cast("list[Any]", statuses_raw):
            if (
                not isinstance(item, list)
                or len(cast("list[Any]", item)) != P7_STATUS_PAIR_LENGTH
            ):
                raise ValueError("P7 field conversion status is malformed")
            state, count = cast("list[Any]", item)
            if not isinstance(state, str) or not state:
                raise ValueError("P7 field conversion status is malformed")
            statuses.append({
                "state": state,
                "count": _int(count, "P7 field status count"),
            })
        if sum(item["count"] for item in statuses) != cell_count:
            raise ValueError("P7 field status counts differ from cell count")
        mapping_target = row.get("mapping_target")
        header_state = (
            "native_unresolved"
            if mapping_target == "unmapped"
            else "interpreted"
        )
        if mapping_target not in {
            "unmapped",
            "services",
            "benefits",
            "fees",
            "caps",
            "descriptions",
            "hierarchy",
            "legacy_annotations",
            "source_headers",
        }:
            raise ValueError("P7 field mapping target is unsupported")
        rows.append({
            "sheet_name": row.get("sheet_name"),
            "column": row.get("column"),
            "field": row.get("mapping_field"),
            "mapping_target": mapping_target,
            "header_state": header_state,
            # This is a structural lineage row for one sheet/column. The
            # separate P7 date profile aggregates across sheets and cannot be
            # allocated back to these rows without per-sheet date evidence.
            "source_value_state": "not_classified_per_sheet_column",
            "source_value_state_detail": (
                "aggregate_date_field_states report date counts across sheets"
            ),
            "cell_count": cell_count,
            "conversion_statuses": statuses,
        })
    return sorted(
        rows, key=lambda row: (str(row["sheet_name"]), str(row["column"]))
    )


def _p7_date_field_rows(
    date_profile: dict[str, Any],
    inference: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    profile = _dict(date_profile.get("profile"), "P7 calendar profile")
    fields = _dict(profile.get("by_field"), "P7 calendar profile fields")
    rows: list[dict[str, Any]] = []
    for field in sorted(fields):
        states = _dict(fields[field], "P7 calendar field states")
        interpreted = _int(
            states.get("unique_calendar_date", 0),
            "unique calendar date count",
        ) + _int(
            states.get("unique_dmy_calendar_date", 0),
            "unique DMY calendar date count",
        )
        date_states = {
            key: _int(value, "calendar field state count")
            for key, value in states.items()
        }
        ambiguous = _int(
            date_states.get("ambiguous_calendar_order", 0),
            "ambiguous calendar field count",
        )
        unresolved = sum(date_states.values()) - interpreted
        inference_fields: list[Any] = []
        if inference is not None:
            inference_fields_raw = inference.get(
                "date_fields_with_populated_values", []
            )
            if not isinstance(inference_fields_raw, list):
                raise TypeError("P7 inferred date fields must be a list")
            inference_fields = cast("list[Any]", inference_fields_raw)
        # A selected DMY profile interprets the ambiguous cells for this
        # exact-copy internal-consistency view. Operational conversion remains
        # disabled by the separately bound date reconciliation receipt.
        inferred = ambiguous if field in inference_fields else 0
        interpreted += inferred
        unresolved -= inferred
        if inferred:
            date_states["ambiguous_calendar_order"] = ambiguous - inferred
            date_states["internal_file_consistency_dmy"] = inferred
        rows.append({
            "field": field,
            "scope": "source_column_across_all_sheets",
            "cell_count": sum(
                _int(count, "calendar field state count")
                for count in states.values()
            ),
            "interpreted": interpreted,
            "native_unresolved": unresolved,
            "unavailable": 0,
            "date_states": dict(sorted(date_states.items())),
            "interpretation_basis": {
                "per_cell_unique_calendar_date": interpreted - inferred,
                "selected_internal_file_consistency_dmy": inferred,
            },
        })
    return rows


def _p7_source_field_states(
    field_rows: list[dict[str, Any]],
    date_field_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in field_rows:
        field_name = row.get("field")
        source_field = (
            field_name
            if isinstance(field_name, str)
            else f"unmapped::{row['sheet_name']}::{row['column']}"
        )
        target = row["mapping_target"]
        field_state = grouped.setdefault(
            source_field,
            {
                "source_field": source_field,
                "mapping_target": target,
                "source_columns": [],
                "source_cells": 0,
                "header_cells": 0,
                "interpreted_header_cells": 0,
            },
        )
        if field_state["mapping_target"] != target:
            raise ValueError("P7 source field has inconsistent mapping targets")
        field_state["source_columns"].append({
            "sheet_name": row["sheet_name"],
            "column": row["column"],
        })
        field_state["source_cells"] += _int(
            row.get("cell_count"), "P7 source field cell count"
        )
        for status in row["conversion_statuses"]:
            if status["state"] == "header":
                field_state["header_cells"] += status["count"]
                if row["header_state"] == "interpreted":
                    field_state["interpreted_header_cells"] += status["count"]

    date_by_field = {row["field"]: row for row in date_field_rows}
    if not set(date_by_field).issubset(grouped):
        raise ValueError("P7 date profile fields lack source-column lineage")
    result: list[dict[str, Any]] = []
    for source_field in sorted(grouped):
        field_state = grouped[source_field]
        source_columns = sorted(
            field_state["source_columns"],
            key=operator.itemgetter("sheet_name", "column"),
        )
        header_cells = field_state["header_cells"]
        value_cells = field_state["source_cells"] - header_cells
        date_state = date_by_field.get(source_field)
        interpreted_values = 0
        date_states: dict[str, int] | None = None
        if date_state is not None:
            if date_state["cell_count"] != value_cells:
                raise ValueError(
                    "P7 date field and source-column denominators differ"
                )
            interpreted_values = date_state["interpreted"]
            date_states = date_state["date_states"]
        result.append({
            "source_field": source_field,
            "mapping_target": field_state["mapping_target"],
            "source_columns": source_columns,
            "header_cells": {
                "denominator": header_cells,
                "interpreted": field_state["interpreted_header_cells"],
                "native_unresolved": (
                    header_cells - field_state["interpreted_header_cells"]
                ),
                "unavailable": 0,
            },
            "value_cells": {
                "denominator": value_cells,
                "interpreted": interpreted_values,
                "native_unresolved": value_cells - interpreted_values,
                "unavailable": 0,
            },
            "value_state_basis": (
                "per-cell unique calendar profile plus exact-P7 internal file-consistency inference"
                if date_state is not None
                and date_state["interpretation_basis"][
                    "selected_internal_file_consistency_dmy"
                ]
                else "source-column calendar profile"
                if date_state is not None
                else "no supported domain interpretation in bound evidence"
            ),
            **({"date_states": date_states} if date_states is not None else {}),
        })
    return result


def _profile_binding_count(profile: dict[str, Any]) -> tuple[int, int]:
    interpreted = 0
    unresolved = 0
    sheets_raw = profile.get("sheets")
    if not isinstance(sheets_raw, list):
        raise TypeError("header profile sheets are malformed")
    sheets = _dict_list(sheets_raw, "header profile sheets")
    for sheet in sheets:
        candidates = _dict_list(
            sheet.get("candidate_rows"), "header profile candidates"
        )
        for candidate in candidates:
            bindings = _dict_list(
                candidate.get("column_bindings", []), "header column bindings"
            )
            for binding in bindings:
                status = binding.get("status")
                if status == "interpreted":
                    interpreted += 1
                else:
                    unresolved += 1
    return interpreted, unresolved


# ruff: ignore[too-many-branches, too-many-statements, too-many-locals]
def reconcile_workbook_field_states(
    package: dict[str, Any],
    headers: dict[str, Any],
    p7_typed: dict[str, Any],
    p7_rules: dict[str, Any],
    input_sha256: dict[str, str],
    *,
    candidate_qualification_receipt: dict[str, Any] | None = None,
    candidate_artifact_path: str | None = None,
) -> dict[str, Any]:
    """Validate independent receipts and produce non-additive state totals."""
    if candidate_qualification_receipt is None:
        embedded_candidate_receipt = p7_typed.get("_candidate_run_receipt")
        if isinstance(embedded_candidate_receipt, dict):
            candidate_qualification_receipt = cast(
                "dict[str, Any]", embedded_candidate_receipt
            )
    if (
        candidate_qualification_receipt is not None
        and candidate_artifact_path is None
    ):
        embedded_artifact = candidate_qualification_receipt.get("artifact")
        if isinstance(embedded_artifact, dict):
            artifact_path = cast("dict[str, Any]", embedded_artifact).get(
                "path"
            )
            if isinstance(artifact_path, str):
                candidate_artifact_path = artifact_path
    if (
        package.get("schema_id")
        != "global-medicines-atlas.mbs-historical-workbook-cohort-reconciliation"
        or package.get("status") != "passed"
    ):
        raise ValueError("historical workbook package cohort is not qualified")
    if (
        headers.get("schema_id")
        != "global-medicines-atlas.mbs-historical-workbook-header-cohort"
        or headers.get("status") != "passed"
    ):
        raise ValueError("historical workbook header cohort is not qualified")
    candidates_raw = package.get("candidate_outputs_by_group")
    assignments_raw = headers.get("workbook_assignments")
    profiles_raw = headers.get("header_profiles")
    if (
        not isinstance(candidates_raw, dict)
        or not isinstance(profiles_raw, list)
        or not isinstance(assignments_raw, list)
    ):
        raise TypeError("workbook cohort identity records are malformed")
    candidates = _dict_list(
        list(cast("dict[str, Any]", candidates_raw).values()),
        "candidate outputs",
    )
    assignments = _dict_list(assignments_raw, "workbook assignments")
    if len(candidates) != WORKBOOK_COUNT or len(assignments) != WORKBOOK_COUNT:
        raise ValueError("the exact 91-workbook denominator is required")
    candidate_ids = [_candidate_identity(row) for row in candidates]
    if (
        len(candidate_ids) != WORKBOOK_COUNT
        or len(set(candidate_ids)) != WORKBOOK_COUNT
    ):
        raise ValueError("candidate workbook identities are not unique")
    if any(row.get("field_state") != "native_unresolved" for row in candidates):
        raise ValueError("candidate cohort contains a promoted workbook state")

    assignment_ids = [
        _candidate_identity(assignment) for assignment in assignments
    ]
    if len(set(assignment_ids)) != WORKBOOK_COUNT or set(candidate_ids) != set(
        assignment_ids
    ):
        raise ValueError(
            "header profiles do not reconcile to the exact candidate cohort"
        )
    if (
        package.get("unique_member_identities") != WORKBOOK_COUNT
        or headers.get("workbook_count") != WORKBOOK_COUNT
    ):
        raise ValueError("workbook cohort summary denominator differs")

    profiles = _dict_list(profiles_raw, "header profile groups")
    profile_by_digest: dict[str, dict[str, Any]] = {}
    member_counts: dict[str, int] = {}
    for grouped in profiles:
        digest = grouped.get("header_profile_sha256")
        profile_raw = grouped.get("profile")
        if not isinstance(digest, str):
            raise TypeError("header profile group identity is malformed")
        profile = _dict(profile_raw, "header profile")
        if _canonical_sha256(profile) != digest:
            raise ValueError("header profile digest differs from profile")
        if digest in profile_by_digest:
            raise ValueError("duplicate header profile digest")
        profile_by_digest[digest] = profile
        member_counts[digest] = _int(
            grouped.get("member_count"), "header profile member count"
        )
    if sum(member_counts.values()) != WORKBOOK_COUNT or headers.get(
        "profile_count"
    ) != len(profiles):
        raise ValueError("header profile member denominator differs")
    assignment_frequency: dict[str, int] = {}
    for assignment in assignments:
        digest = assignment.get("header_profile_sha256")
        if not isinstance(digest, str):
            raise TypeError("workbook header profile digest is malformed")
        if digest not in profile_by_digest:
            raise ValueError(
                "workbook assignment references an unknown header profile"
            )
        assignment_frequency[digest] = assignment_frequency.get(digest, 0) + 1
    if assignment_frequency != member_counts:
        raise ValueError("header profile member counts differ from assignments")
    interpreted_bindings = 0
    unresolved_bindings = 0
    for digest, profile in profile_by_digest.items():
        interpreted, unresolved = _profile_binding_count(profile)
        count = member_counts[digest]
        interpreted_bindings += interpreted * count
        unresolved_bindings += unresolved * count
    header_denominator = interpreted_bindings + unresolved_bindings
    if interpreted_bindings != headers.get(
        "interpreted_header_column_binding_count"
    ):
        raise ValueError(
            "interpreted header binding count differs from profiles"
        )
    if unresolved_bindings != headers.get("unresolved_header_label_count"):
        raise ValueError("unresolved header label count differs from profiles")
    if headers.get("unresolved_header_candidate_count") != 0:
        raise ValueError("unresolved header candidates remain")

    header_field_rows = _profile_field_rows(profile_by_digest, member_counts)

    totals = _dict(package.get("totals"), "workbook totals")
    coverage = _dict(
        package.get("silver_field_state_coverage"), "workbook field coverage"
    )
    non_header_cells = _int(totals.get("cells"), "non-header cell denominator")
    if (
        coverage.get("native_unresolved_cells") != non_header_cells
        or coverage.get("interpreted_cells") != 0
    ):
        raise ValueError("historical workbook cell-state totals disagree")
    if (
        coverage.get("source_column_meaning_inferred") is not False
        or coverage.get("date_and_currency_meaning_inferred") is not False
    ):
        raise ValueError(
            "unsupported historical workbook semantics are asserted"
        )

    if p7_typed.get("kind") != "p7-workbook":
        raise ValueError("P7 typed qualification kind differs")
    reconciliation_report = p7_typed.get("_p7_date_reconciliation")
    value_profile = _dict(
        p7_typed.get("domain_value_profile"), "P7 typed value profile"
    )
    candidate = _dict(
        p7_typed.get("typed_candidate_package"), "P7 candidate package"
    )
    p7_cells = _int(value_profile.get("cells"), "P7 cell denominator")
    p7_coverage = _dict(candidate.get("coverage"), "P7 candidate coverage")
    p7_interpreted = _int(
        p7_coverage.get("interpreted_cells"), "P7 interpreted cell count"
    )
    p7_unresolved = _int(
        p7_coverage.get("unresolved_cells"), "P7 unresolved cell count"
    )
    if p7_cells != P7_CELL_COUNT or p7_interpreted + p7_unresolved != p7_cells:
        raise ValueError("P7 all-cell unresolved denominator differs")
    if reconciliation_report is not None:
        if candidate_qualification_receipt is None:
            if (
                p7_interpreted != P7_UNIQUE_INTERPRETED_DATE_CELLS
                or p7_unresolved != P7_RETAINED_UNRESOLVED_CELL_COUNT
            ):
                raise ValueError("P7 retained date-state baseline differs")
            p7_interpreted += P7_INFERENCE_INTERPRETED_DATE_CELLS
            p7_unresolved -= P7_INFERENCE_INTERPRETED_DATE_CELLS
        elif (
            p7_interpreted
            != P7_UNIQUE_INTERPRETED_DATE_CELLS
            + P7_INFERENCE_INTERPRETED_DATE_CELLS
            or p7_unresolved != P7_CANDIDATE_UNRESOLVED_CELL_COUNT
        ):
            raise ValueError("P7 candidate date-state totals differ")
    p7_run_receipt = _dict(
        p7_typed.get("_run_receipt"), "P7 exact-main run receipt"
    )
    if p7_run_receipt.get("schema_id") != (
        "global-medicines-atlas.mbs-p7-exact-main-workbook-storage-run-receipt"
    ):
        raise ValueError("P7 exact-main run receipt schema differs")
    exact_run = _dict(
        p7_run_receipt.get("workflow"), "P7 exact-main qualification"
    )
    if candidate_qualification_receipt is None:
        expected_run = {
            "run_id": P7_EXACT_MAIN_RUN_ID,
            "conclusion": "success",
            "exact_commit": P7_EXACT_MAIN_COMMIT,
            "python": "3.15.1",
            "url": "https://github.com/edithatogo/global-medicines-atlas/actions/runs/40094025412",
        }
        actual_run = {key: exact_run.get(key) for key in expected_run}
        if actual_run != expected_run:
            raise ValueError("P7 exact-main qualification identity differs")
    else:
        if candidate_qualification_receipt != p7_run_receipt:
            raise ValueError("P7 inferred candidate receipt binding differs")
        if not _candidate_hosted_run_matches(exact_run, p7_typed):
            raise ValueError("P7 exact-main qualification identity differs")
    if p7_typed.get("workflow_run") != exact_run.get("url") or p7_typed.get(
        "workflow_commit"
    ) != exact_run.get("exact_commit"):
        raise ValueError("P7 exact-main qualification identity differs")
    p7_date_profile = _dict(
        p7_typed.get("_p7_date_profile"), "P7 calendar profile receipt"
    )
    reconciliation_inference: dict[str, Any] | None = None
    if reconciliation_report is not None:
        reconciliation_inference = _validate_p7_date_reconciliation(
            _dict(reconciliation_report, "P7 date reconciliation report"),
            cast("str", input_sha256.get("p7_date_reconciliation")),
        )
    inference_decision: dict[str, Any] | None = reconciliation_inference
    inference_sha256: str | None = None
    if candidate_qualification_receipt is not None:
        p7_date_inference = _dict(
            p7_typed.get("_p7_date_inference"), "P7 date inference receipt"
        )
        inference_bytes = (
            json.dumps(
                p7_date_inference,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        inference_decision, inference_sha256 = (
            validate_p7_date_consistency_inference(
                inference_bytes,
                expected_sha256=input_sha256.get("p7_date_inference"),
                source_sha256=str(value_profile.get("source_sha256")),
                source_byte_count=87727,
            )
        )
        if (
            inference_decision is None
            or inference_sha256 != P7_DATE_INFERENCE_SHA256
        ):
            raise ValueError("P7 selected date inference evidence is required")
        if reconciliation_inference is not None:
            # The current exact-copy reconciliation is the governing evidence.
            # The older candidate receipt is retained only as an independent
            # binding and cannot expand interpretation beyond four cells.
            inference_decision = reconciliation_inference
    p7_date_profile_data = _dict(
        p7_date_profile.get("profile"), "P7 calendar profile"
    )
    if (
        p7_date_profile.get("kind") != "mbs_p7_unique_calendar_date_profile"
        or p7_date_profile_data.get("source_sha256")
        != value_profile.get("source_sha256")
        or p7_date_profile_data.get("date_order_selected") is not False
        or p7_date_profile_data.get("source_values_emitted") is not False
    ):
        raise ValueError("P7 calendar profile identity differs")
    date_evidence = _dict(
        p7_typed.get("p7_calendar_profile_evidence"),
        "P7 calendar profile evidence",
    )
    date_profile_digest = input_sha256.get("p7_date_profile", "")
    calendar_ref = _dict(
        p7_run_receipt.get("calendar_profile"),
        "P7 calendar profile receipt reference",
    )
    expected_calendar_binding = {
        "path": P7_DATE_PROFILE_PATH,
        "sha256": date_profile_digest,
        "source_sha256": value_profile.get("source_sha256"),
        "date_order_selected": False,
        "source_values_emitted": False,
    }
    actual_calendar_binding = {
        "path": calendar_ref.get("path"),
        "sha256": date_evidence.get("sha256"),
        "source_sha256": date_evidence.get("source_sha256"),
        "date_order_selected": date_evidence.get("date_order_selected"),
        "source_values_emitted": date_evidence.get("source_values_emitted"),
    }
    if actual_calendar_binding != expected_calendar_binding or (
        calendar_ref.get("sha256") != date_profile_digest
    ):
        raise ValueError("P7 calendar profile does not bind the exact source")
    if (
        p7_rules.get("schema_id")
        != "global-medicines-atlas.mbs-p7-value-era-rules"
    ):
        raise ValueError("P7 value-era rules schema differs")
    if _dict(p7_rules.get("source"), "P7 value-era source").get(
        "sha256"
    ) != value_profile.get("source_sha256"):
        raise ValueError("P7 typed qualification and value-era source differ")
    rule_evidence = _dict(p7_rules.get("evidence"), "P7 rule evidence")
    typed_ref = rule_evidence.get("exact_main_storage_qualification", {})
    if candidate_qualification_receipt is None and _dict(
        typed_ref, "P7 typed receipt reference"
    ).get("sha256") != input_sha256.get("p7_typed"):
        raise ValueError(
            "P7 value-era rules do not bind exact-main typed receipt"
        )
    run_ref = _dict(
        rule_evidence.get("exact_main_run_receipt", {}),
        "P7 exact-main run receipt reference",
    )
    if candidate_qualification_receipt is None and run_ref.get(
        "sha256"
    ) != input_sha256.get("p7_run_receipt"):
        raise ValueError("P7 value-era rules do not bind the exact-main run")
    date_ref = _dict(
        rule_evidence.get("calendar_profile", {}),
        "P7 calendar profile reference",
    )
    if date_ref.get("sha256") != input_sha256.get("p7_date_profile"):
        raise ValueError("P7 value-era rules do not bind the calendar profile")
    if (
        date_ref.get("path") != P7_DATE_PROFILE_PATH
        or date_ref.get("path") != calendar_ref.get("path")
        or date_ref.get("sha256") != calendar_ref.get("sha256")
    ):
        raise ValueError("P7 value-era rules calendar path differs")
    rule_groups = _dict(p7_rules.get("rules"), "P7 rules")
    date_rules = _dict(rule_groups.get("dates"), "P7 date rules")
    if (
        date_rules.get("selected_profile") is not None
        or date_rules.get("semantic_promotion") is not False
    ):
        raise ValueError("P7 date profile must remain unselected")
    if candidate_qualification_receipt is not None:
        candidate_inference = _dict(
            candidate.get("date_inference"), "P7 candidate date inference"
        )
        if candidate_inference != {
            "kind": "selected_internal_file_consistency_inference",
            "source_sha256": value_profile.get("source_sha256"),
            "profile": "dotted_DMY",
            "fields": cast("dict[str, Any]", inference_decision)[
                "date_fields_with_populated_values"
            ],
            "interpreted_cells": P7_INFERENCE_INTERPRETED_DATE_CELLS,
            "evidence_sha256": inference_sha256,
            "department_provenance_established": False,
            "domain_meaning_established": False,
            "other_workbooks_or_eras_in_scope": False,
        }:
            raise ValueError("P7 candidate date inference binding differs")
        receipt_artifact = _dict(
            candidate_qualification_receipt.get("artifact"),
            "P7 candidate artifact receipt",
        )
        if (
            candidate_artifact_path is None
            or candidate_artifact_path == P7_TYPED_PATH
            or receipt_artifact.get("path") != candidate_artifact_path
            or receipt_artifact.get("report_sha256")
            != input_sha256.get("p7_typed")
        ):
            raise ValueError("P7 inferred candidate artifact binding differs")
    if p7_interpreted != (
        P7_INTERPRETED_DATE_CELLS
        if inference_decision is not None
        else P7_UNIQUE_INTERPRETED_DATE_CELLS
    ) or p7_unresolved != (
        P7_CANDIDATE_UNRESOLVED_CELL_COUNT
        if inference_decision is not None
        else P7_RETAINED_UNRESOLVED_CELL_COUNT
    ):
        raise ValueError("P7 exact-main cell-state totals differ")
    date_field_rows = _p7_date_field_rows(p7_date_profile, inference_decision)
    if sum(row["interpreted"] for row in date_field_rows) != p7_interpreted:
        raise ValueError(
            "P7 unique date fields differ from typed qualification"
        )
    ambiguous_dates = sum(
        _int(
            _dict(row.get("date_states"), "P7 date field states").get(
                "ambiguous_calendar_order", 0
            ),
            "ambiguous calendar date count",
        )
        for row in date_field_rows
    )
    if ambiguous_dates + (
        P7_INFERENCE_INTERPRETED_DATE_CELLS
        if inference_decision is not None
        else 0
    ) != _int(
        date_rules.get("ambiguous_date_shaped_cells"),
        "ambiguous date-shaped cell count",
    ) or ambiguous_dates + (
        P7_INFERENCE_INTERPRETED_DATE_CELLS
        if inference_decision is not None
        else 0
    ) + P7_UNIQUE_INTERPRETED_DATE_CELLS != _int(
        date_rules.get("lexical_date_cells"),
        "P7 date-shaped cell count",
    ):
        raise ValueError(
            "P7 date profile counts differ from the value-era rules"
        )

    artifact = _dict(p7_run_receipt.get("artifact"), "P7 artifact receipt")
    if candidate_qualification_receipt is None:
        artifact_identity_valid = (
            artifact.get("path") == P7_TYPED_PATH
            and artifact.get("artifact_id") == P7_EXACT_MAIN_ARTIFACT_ID
            and artifact.get("member_sha256")
            == "fd893d18c6a96d7daf6c6bae27066f56d207b8d01c14d8fc7622bdc07af99bd"
        )
    else:
        artifact_identity_valid = (
            artifact.get("path") == candidate_artifact_path
            and type(artifact.get("artifact_id")) is int
            and artifact.get("artifact_id", 0) > 0
            and isinstance(artifact.get("member_sha256"), str)
            and len(artifact.get("member_sha256", "")) == SHA256_HEX_LENGTH
        )
    if (
        not artifact_identity_valid
        or artifact.get("name") != "workbook-storage-qualification"
        or artifact.get("report_sha256") != input_sha256.get("p7_typed")
    ):
        raise ValueError("P7 exact-main artifact identity differs")
    expected_hash_keys = {
        "package_cohort",
        "header_cohort",
        "p7_typed",
        "p7_run_receipt",
        "p7_date_profile",
        "p7_value_era_rules",
    }
    if reconciliation_report is not None:
        expected_hash_keys.add("p7_date_reconciliation")
    if candidate_qualification_receipt is not None:
        expected_hash_keys.add("p7_date_inference")
    if set(input_sha256) != expected_hash_keys or any(
        type(value) is not str or len(value) != SHA256_HEX_LENGTH
        for value in input_sha256.values()
    ):
        raise ValueError("exact input receipt digests are required")
    if (
        candidate_qualification_receipt is not None
        and input_sha256["p7_date_inference"] != P7_DATE_INFERENCE_SHA256
    ):
        raise ValueError("P7 date inference receipt digest differs")

    p7_statuses = _dict(value_profile.get("statuses"), "P7 value statuses")
    p7_status_total = sum(
        _int(count, "P7 value conversion status count")
        for count in p7_statuses.values()
    )
    if p7_status_total != p7_cells:
        raise ValueError(
            "P7 value conversion statuses differ from cell denominator"
        )
    p7_sheets = _dict_list(p7_typed.get("sheets"), "P7 sheets")
    if sum(
        _int(sheet.get("formula_cells"), "P7 sheet formula count")
        for sheet in p7_sheets
    ) != p7_coverage.get("formula_cells"):
        raise ValueError("P7 formula diagnostic denominators differ")
    if sum(
        _int(sheet.get("error_cells"), "P7 sheet error count")
        for sheet in p7_sheets
    ) != p7_coverage.get("error_cells"):
        raise ValueError("P7 error diagnostic denominators differ")
    p7_field_rows = _p7_field_rows(p7_typed)
    header_cells = _int(p7_statuses.get("header"), "P7 header cell count")
    if header_cells != P7_HEADER_CELL_COUNT:
        raise ValueError("P7 header cell denominator differs")
    header_roles = {"interpreted": 0, "native_unresolved": 0}
    for row in p7_field_rows:
        for status in row["conversion_statuses"]:
            if status["state"] == "header":
                header_roles[row["header_state"]] += status["count"]
    if sum(header_roles.values()) != header_cells or (
        header_roles["interpreted"] != header_cells
    ):
        raise ValueError("P7 header role states differ from header cells")
    value_cells = p7_cells - header_cells
    unresolved_values = value_cells - p7_interpreted
    expected_value_unresolved = (
        P7_CANDIDATE_UNRESOLVED_VALUE_COUNT
        if inference_decision is not None
        else P7_RETAINED_UNRESOLVED_VALUE_COUNT
    )
    if (
        value_cells != P7_VALUE_CELL_COUNT
        or unresolved_values != expected_value_unresolved
    ):
        raise ValueError("P7 non-header field-state denominator differs")
    source_field_states = _p7_source_field_states(
        p7_field_rows, date_field_rows
    )
    if (
        sum(row["value_cells"]["denominator"] for row in source_field_states)
        != value_cells
        or sum(row["value_cells"]["interpreted"] for row in source_field_states)
        != p7_interpreted
        or sum(
            row["value_cells"]["native_unresolved"]
            for row in source_field_states
        )
        != unresolved_values
        or sum(
            row["header_cells"]["denominator"] for row in source_field_states
        )
        != header_cells
    ):
        raise ValueError("P7 source field states differ from cohort totals")
    date_compatibility = _dict(
        date_rules.get("calendar_compatibility"), "P7 date compatibility"
    )
    if sum(
        _int(value, "P7 date compatibility count")
        for value in date_compatibility.values()
        if type(value) is int
    ) != _int(
        date_rules.get("lexical_date_cells"), "P7 date-shaped cell count"
    ):
        raise ValueError(
            "P7 date compatibility counts differ from date-shaped cells"
        )
    return {
        "schema_id": "global-medicines-atlas.mbs-workbook-field-state-reconciliation",
        "schema_version": 2,
        "status": "field_states_reconciled_with_semantic_limits",
        "inputs": {
            key: {"sha256": input_sha256[key]} for key in sorted(input_sha256)
        },
        "historical_workbook_cohort": {
            "workbooks_expected": WORKBOOK_COUNT,
            "candidate_outputs": len(candidates),
            "header_assignments": len(assignments),
            "unique_candidate_identities": len(set(candidate_ids)),
            "identity_matches": len(set(candidate_ids) & set(assignment_ids)),
            "header_column_roles": {
                "denominator": header_denominator,
                "interpreted": interpreted_bindings,
                "unresolved": unresolved_bindings,
                "unavailable": 0,
                "unresolved_header_candidates": headers[
                    "unresolved_header_candidate_count"
                ],
                "unresolved_header_labels": headers[
                    "unresolved_header_label_count"
                ],
                "denominator_relation": "separate_non_additive_header_role_occurrences",
            },
            "field_rows": header_field_rows,
            "cell_values": {
                "denominator": non_header_cells,
                "interpreted": 0,
                "unresolved": non_header_cells,
                "unavailable": 0,
                "decimal_candidates": _int(
                    totals.get("decimal_candidates"), "decimal candidate count"
                ),
                "missing_native_values": _int(
                    totals.get("missing_native_values"),
                    "missing native value count",
                ),
                "denominator_relation": "non_header_cell_values_only_header_role_denominator_not_added",
            },
        },
        "p7_workbook": {
            "source_sha256": value_profile["source_sha256"],
            "exact_main_qualification": exact_run,
            "exact_main_artifact": artifact,
            "field_rows": p7_field_rows,
            "source_field_states": source_field_states,
            "date_field_states": date_field_rows,
            "source_cells": {
                "denominator": p7_cells,
                "header_cells": header_cells,
                "value_cells": value_cells,
                "denominator_relation": "header_cells_plus_value_cells",
            },
            "header_column_roles": {
                "denominator": header_cells,
                "interpreted": header_roles["interpreted"],
                "unresolved": header_roles["native_unresolved"],
                "unavailable": 0,
                "denominator_relation": "separate_non_additive_header_role_occurrences",
            },
            "cell_values": {
                "denominator": value_cells,
                "interpreted": p7_interpreted,
                "unresolved": unresolved_values,
                "unavailable": 0,
                "denominator_relation": "non_header_cell_values_only_header_role_denominator_not_added",
            },
            "orthogonal_diagnostics": {
                "value_conversion_statuses": dict(sorted(p7_statuses.items())),
                "formula_cells": _int(
                    p7_coverage.get("formula_cells"), "P7 formula cell count"
                ),
                "error_cells": _int(
                    p7_coverage.get("error_cells"), "P7 error cell count"
                ),
                "decimal_unrepresentable": _int(
                    p7_statuses.get("unrepresentable"),
                    "P7 unrepresentable count",
                ),
                "date_shaped_cells": _int(
                    date_rules.get("lexical_date_cells"),
                    "P7 date-shaped cell count",
                ),
                "date_order_compatibility": dict(
                    sorted(date_compatibility.items())
                ),
                "date_profile_selected": False,
                "internal_file_consistency_inference_selected": (
                    inference_decision is not None
                ),
                "date_inference_sha256": inference_sha256,
                "file_consistency_dmy_interpreted_cells": (
                    P7_INFERENCE_INTERPRETED_DATE_CELLS
                    if inference_decision is not None
                    else 0
                ),
                "date_profile_sha256": date_profile_digest,
                "uniquely_determined_calendar_dates": P7_UNIQUE_INTERPRETED_DATE_CELLS,
                "ambiguous_date_shaped_cells": _int(
                    date_rules.get("ambiguous_date_shaped_cells"),
                    "ambiguous date-shaped cell count",
                ),
                "temporal_comparison_enabled": False,
                "diagnostics_are_additive_to_cell_state": False,
            },
            "schema_eras": _dict(
                rule_groups.get("schema_eras"), "P7 schema eras"
            ),
        },
        "semantic_boundaries": {
            "historical_workbook_non_header_domain_meanings_qualified": False,
            "benefit_currency_qualified": False,
            "p7_date_convention_selected": False,
            "p7_unique_calendar_date_values_interpreted": P7_UNIQUE_INTERPRETED_DATE_CELLS,
            "p7_internal_file_consistency_dmy_inference_selected": (
                inference_decision is not None
            ),
            "p7_internal_file_consistency_dmy_cells_interpreted": (
                P7_INFERENCE_INTERPRETED_DATE_CELLS
                if inference_decision is not None
                else 0
            ),
            "p7_department_provenance_established": False,
            "p7_domain_meaning_established": False,
            "p7_temporal_comparison_enabled": False,
            "cross_era_equivalence_qualified": False,
            "source_values_emitted": False,
            "new_sources_added": False,
        },
    }


def reconcile_from_paths(
    paths: dict[str, Path], *, candidate_artifact_path: str | None = None
) -> dict[str, Any]:
    reports = {key: _read_json(path) for key, path in paths.items()}
    digests = {key: _sha256(path) for key, path in paths.items()}
    candidate_receipt = reports.pop("p7_candidate_qualification_receipt", None)
    if "p7_date_reconciliation" not in reports:
        repository_root = Path(__file__).resolve().parents[2]
        reconciliation_path = repository_root / P7_DATE_RECONCILIATION_PATH
        reports["p7_date_reconciliation"] = _read_json(reconciliation_path)
        digests["p7_date_reconciliation"] = _sha256(reconciliation_path)
    if candidate_receipt is not None:
        digests["p7_run_receipt"] = digests.pop(
            "p7_candidate_qualification_receipt"
        )
        reports["p7_run_receipt"] = candidate_receipt
        reports["p7_typed"]["_candidate_run_receipt"] = candidate_receipt
    elif "p7_date_inference" in reports:
        raise ValueError(
            "inference evidence requires a separate candidate qualification receipt"
        )
    reports["p7_typed"]["_run_receipt"] = reports["p7_run_receipt"]
    reports["p7_typed"]["_p7_date_profile"] = reports["p7_date_profile"]
    if "p7_date_reconciliation" in reports:
        reports["p7_typed"]["_p7_date_reconciliation"] = reports[
            "p7_date_reconciliation"
        ]
    if candidate_receipt is not None:
        reports["p7_typed"]["_p7_date_inference"] = reports["p7_date_inference"]
    return reconcile_workbook_field_states(
        reports["package_cohort"],
        reports["header_cohort"],
        reports["p7_typed"],
        reports["p7_value_era_rules"],
        digests,
        candidate_qualification_receipt=candidate_receipt,
        candidate_artifact_path=candidate_artifact_path,
    )


def _value_shape_source_cell_partition(
    value_shape_report: dict[str, Any],
    row_counts: dict[str, Any],
) -> dict[str, int | str]:
    source_cell_records = _int(
        value_shape_report.get("source_cell_records"),
        "value-shape source cell record count",
    )
    header_cells = _int(
        value_shape_report.get("header_cells"), "value-shape header cell count"
    )
    pre_header_cells = _int(
        value_shape_report.get("pre_header_cells"),
        "value-shape pre-header cell count",
    )
    other_sheet_cells = _int(
        value_shape_report.get("other_sheet_cells"),
        "value-shape other-sheet cell count",
    )
    out_of_contract_data_cells = _int(
        value_shape_report.get("out_of_contract_data_cells"),
        "value-shape out-of-contract data cell count",
    )
    data_field_cells = sum(
        _int(row_counts[field], f"{field} field row count")
        for field in EXPECTED_FIELDS
    )
    non_header_field_state_cells = source_cell_records - header_cells
    if (
        source_cell_records
        != header_cells
        + pre_header_cells
        + other_sheet_cells
        + out_of_contract_data_cells
        + data_field_cells
        or non_header_field_state_cells
        != pre_header_cells
        + other_sheet_cells
        + out_of_contract_data_cells
        + data_field_cells
    ):
        raise ValueError(
            "historical workbook source-cell categories do not conserve"
        )
    return {
        "source_cell_records": source_cell_records,
        "header_cells": header_cells,
        "non_header_field_state_cells": non_header_field_state_cells,
        "data_field_cells": data_field_cells,
        "pre_header_cells": pre_header_cells,
        "other_sheet_cells": other_sheet_cells,
        "out_of_contract_data_cells": out_of_contract_data_cells,
    }


def _apply_source_cell_partition(
    historical: dict[str, Any], partition: dict[str, int | str]
) -> None:
    cell_values = _dict(historical.get("cell_values"), "historical cell values")
    source_cell_records = partition["source_cell_records"]
    non_header_cells = partition["non_header_field_state_cells"]
    if (
        _int(cell_values.get("denominator"), "field-state denominator")
        != source_cell_records
    ):
        raise ValueError(
            "field-state denominator differs from exact source cells"
        )
    cell_values["denominator"] = non_header_cells
    cell_values["unresolved"] = non_header_cells
    cell_values["denominator_relation"] = (
        "non_header_source_cells; header_cells_reported_separately"
    )
    historical["source_cell_partition"] = {
        **partition,
        "denominator_relation": "source_cell_records_equals_header_plus_non_header_cells",
    }


def bind_historical_workbook_value_shapes(
    field_state_report: dict[str, Any],
    value_shape_report: dict[str, Any],
    *,
    value_shape_path: str,
    value_shape_sha256: str,
    expected_field_state_sha256: str,
    value_shape_workflow_run_id: int,
) -> dict[str, Any]:
    """Bind exact 91-workbook storage-shape diagnostics without promotion."""
    report_inputs = _dict(
        value_shape_report.get("input_digests"), "value-shape input digests"
    )
    contract_invalid = (
        value_shape_report.get("schema_id")
        != "global-medicines-atlas.mbs-historical-workbook-value-shape-cohort",
        value_shape_report.get("status") != "passed",
        value_shape_report.get("archive_count") != MBS_ARCHIVE_COUNT,
        value_shape_report.get("workbook_count") != WORKBOOK_COUNT,
        value_shape_report.get("candidate_cohort_run_id") != MBS_COHORT_RUN_ID,
        value_shape_report.get("dataset") != MBS_DATASET,
        value_shape_report.get("revision") != MBS_REVISION,
        value_shape_report.get("field_state_report_sha256")
        != expected_field_state_sha256,
        report_inputs.get("field_state_sha256") != expected_field_state_sha256,
        report_inputs.get("header_cohort_sha256")
        != _field_state_input_sha256(field_state_report, "header_cohort"),
        report_inputs.get("candidate_cohort_sha256")
        != _field_state_input_sha256(field_state_report, "package_cohort"),
        value_shape_report.get("source_values_emitted") is not False,
        value_shape_report.get("source_column_meanings_qualified") is not False,
        value_shape_report.get("calendar_year_vs_service_year_resolved")
        is not False,
        value_shape_report.get("calendar_month_vs_processing_month_resolved")
        is not False,
        value_shape_report.get("currency_interpreted") is not False,
        value_shape_report.get("date_interpreted") is not False,
        value_shape_report.get("p7_workbook_in_scope") is not False,
        value_shape_report.get("p7_date_inference_applied") is not False,
        value_shape_report.get("p7_domain_date_semantics_qualified")
        is not False,
        value_shape_report.get("cross_era_equivalence_claimed") is not False,
        value_shape_report.get("new_sources") != 0,
        value_shape_report.get("new_admissions") != 0,
        value_shape_report.get("consumer_canaries") != 0,
        value_shape_report.get("publications") != 0,
    )
    if any(contract_invalid):
        raise ValueError("historical workbook value-shape scope differs")
    fields = _dict(value_shape_report.get("fields"), "value-shape fields")
    row_counts = _dict(
        value_shape_report.get("field_row_counts"),
        "value-shape field row counts",
    )
    if set(fields) != set(EXPECTED_FIELDS) or set(row_counts) != set(
        EXPECTED_FIELDS
    ):
        raise ValueError(
            "historical workbook value-shape field identities differ"
        )
    archives = _dict_list(
        value_shape_report.get("archives"), "value-shape archives"
    )
    if len(archives) != MBS_ARCHIVE_COUNT or {
        row.get("archive_index") for row in archives
    } != set(range(MBS_ARCHIVE_COUNT)):
        raise ValueError("historical workbook archive partitions differ")
    bindings = _dict_list(
        value_shape_report.get("workbook_bindings"),
        "value-shape workbook bindings",
    )
    if (
        len(bindings) != WORKBOOK_COUNT
        or len({row.get("candidate_output_id") for row in bindings})
        != WORKBOOK_COUNT
        or len({row.get("candidate_group") for row in bindings})
        != WORKBOOK_COUNT
    ):
        raise ValueError("historical workbook candidate identities differ")
    source_cell_partition = _value_shape_source_cell_partition(
        value_shape_report, row_counts
    )
    if len(value_shape_sha256) != SHA256_HEX_LENGTH or any(
        char not in "0123456789abcdef" for char in value_shape_sha256
    ):
        raise ValueError("historical workbook value-shape digest is malformed")
    workflow_commit = value_shape_report.get("workflow_commit")
    if (
        type(value_shape_workflow_run_id) is not int
        or value_shape_workflow_run_id <= 0
        or not isinstance(workflow_commit, str)
        or len(workflow_commit) != GIT_COMMIT_HEX_LENGTH
        or any(char not in "0123456789abcdef" for char in workflow_commit)
    ):
        raise ValueError("historical workbook workflow identity is malformed")

    field_rows: dict[str, dict[str, Any]] = {}
    for field_name in EXPECTED_FIELDS:
        value = _dict(fields[field_name], f"value-shape field {field_name}")
        cell_count = _int(value.get("cell_count"), f"{field_name} cell count")
        if (
            _int(row_counts[field_name], f"{field_name} field row count")
            != cell_count
        ):
            raise ValueError(f"{field_name} row and cell counts differ")
        value_shapes = _dict(
            value.get("value_shapes"), f"{field_name} value shapes"
        )
        if (
            sum(
                _int(count, f"{field_name} shape count")
                for count in value_shapes.values()
            )
            != cell_count
        ):
            raise ValueError(f"{field_name} value-shape counts do not conserve")
        field_rows[field_name] = {
            "field_state": "native_unresolved",
            "cell_position_denominator": cell_count,
            "interpreted": 0,
            "native_unresolved": cell_count,
            "unavailable": 0,
            "value_shapes": dict(sorted(value_shapes.items())),
            "native_cell_types": dict(
                sorted(
                    _dict(
                        value.get("native_cell_types"),
                        f"{field_name} cell types",
                    ).items()
                )
            ),
            "native_states": dict(
                sorted(
                    _dict(
                        value.get("native_states"),
                        f"{field_name} native states",
                    ).items()
                )
            ),
            "formula_cells": _int(
                value.get("formula_cells"), f"{field_name} formula count"
            ),
            "formula_cells_with_cache": _int(
                value.get("formula_cells_with_cache"),
                f"{field_name} cached formula count",
            ),
            "source_error_cells": _int(
                value.get("source_error_cells"),
                f"{field_name} source error count",
            ),
            "native_missing_value_cells": _int(
                value.get("native_missing_value_cells"),
                f"{field_name} missing value count",
            ),
            "missing_physical_cell_positions": _int(
                value.get("missing_physical_cell_positions"),
                f"{field_name} missing cell position count",
            ),
            "meaning_qualified": False,
        }
        if (
            field_rows[field_name]["formula_cells"] > cell_count
            or field_rows[field_name]["formula_cells_with_cache"]
            > field_rows[field_name]["formula_cells"]
            or field_rows[field_name]["source_error_cells"] > cell_count
            or field_rows[field_name]["native_missing_value_cells"] > cell_count
            or field_rows[field_name]["missing_physical_cell_positions"]
            > cell_count
        ):
            raise ValueError(f"{field_name} shape subcounts exceed field count")

    result = copy.deepcopy(field_state_report)
    result_inputs = _dict(result.get("inputs"), "field-state input digests")
    result_inputs["historical_workbook_value_shapes"] = {
        "sha256": value_shape_sha256
    }
    historical = _dict(
        result.get("historical_workbook_cohort"),
        "historical workbook field states",
    )
    _apply_source_cell_partition(historical, source_cell_partition)
    historical["value_shape_diagnostics"] = {
        "path": value_shape_path,
        "sha256": value_shape_sha256,
        "workflow_run_id": value_shape_workflow_run_id,
        "workflow_url": (
            "https://github.com/edithatogo/global-medicines-atlas/actions/runs/"
            f"{value_shape_workflow_run_id}"
        ),
        "workflow_commit": workflow_commit,
        "archive_count": 6,
        "workbook_count": WORKBOOK_COUNT,
        "fields": field_rows,
        "denominator_relation": "storage-shape counts partition data-field cells; source-cell partition separates header and non-header cells",
        "source_values_emitted": False,
        "source_column_meanings_qualified": False,
        "date_meaning_qualified": False,
        "currency_qualified": False,
        "cross_era_equivalence_qualified": False,
    }
    result["status"] = (
        "field_states_reconciled_with_historical_value_shape_overlay_and_semantic_limits"
    )
    return result


def _field_state_input_sha256(report: dict[str, Any], input_name: str) -> Any:
    inputs = _dict(report.get("inputs"), "field-state input digests")
    selected = _dict(inputs.get(input_name), f"{input_name} input digest")
    return selected.get("sha256")


def canonical_json(report: dict[str, Any]) -> str:
    return (
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
