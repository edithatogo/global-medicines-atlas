"""Reconcile value-free field states for the retained MBS workbook cohorts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

PACKAGE_PATH = (
    "quality/qualifications/mbs-historical-workbook-cohort-"
    "20261023-39724026209-39891918206.json"
)
HEADER_PATH = (
    "quality/qualifications/mbs-historical-workbook-header-cohort-"
    "20261024-40040624592.json"
)
P7_TYPED_PATH = (
    "quality/qualifications/mbs-p7-typed-qualification-"
    "20261022-39636095527.json"
)
P7_RULES_PATH = "quality/qualifications/mbs-p7-value-era-rules-20261024.json"
WORKBOOK_COUNT = 91
P7_CELL_COUNT = 13_742
SHA256_HEX_LENGTH = 64
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
                row_index = _int(candidate.get("row_index"), "candidate row index")
                bindings = _dict_list(
                    candidate.get("column_bindings", []),
                    "header column bindings",
                )
                for binding in bindings:
                    column = binding.get("column")
                    status = binding.get("status")
                    state = status_map.get(status) if isinstance(status, str) else None
                    if not isinstance(column, str) or state is None:
                        raise ValueError("header field binding is malformed")
                    field = binding.get("field")
                    if state == "interpreted" and not isinstance(field, str):
                        raise ValueError("interpreted header binding lacks a field")
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
    if sum(_int(row.get("cell_count"), "P7 field cell count") for row in fields) != P7_CELL_COUNT:
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
        header_state = "native_unresolved" if mapping_target == "unmapped" else "interpreted"
        if mapping_target not in {"unmapped", "services", "benefits", "fees", "caps", "descriptions", "hierarchy", "legacy_annotations", "source_headers"}:
            raise ValueError("P7 field mapping target is unsupported")
        rows.append({
            "sheet_name": row.get("sheet_name"),
            "column": row.get("column"),
            "field": row.get("mapping_field"),
            "mapping_target": mapping_target,
            "header_state": header_state,
            "source_value_state": "native_unresolved",
            "cell_count": cell_count,
            "conversion_statuses": statuses,
        })
    return sorted(rows, key=lambda row: (str(row["sheet_name"]), str(row["column"])))


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
) -> dict[str, Any]:
    """Validate independent receipts and produce non-additive state totals."""
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
    value_profile = _dict(
        p7_typed.get("domain_value_profile"), "P7 typed value profile"
    )
    candidate = _dict(
        p7_typed.get("typed_candidate_package"), "P7 candidate package"
    )
    p7_cells = _int(value_profile.get("cells"), "P7 cell denominator")
    if (
        p7_cells != P7_CELL_COUNT
        or _dict(candidate.get("coverage"), "P7 candidate coverage").get(
            "unresolved_cells"
        )
        != p7_cells
    ):
        raise ValueError("P7 all-cell unresolved denominator differs")
    if (
        p7_rules.get("schema_id")
        != "global-medicines-atlas.mbs-p7-value-era-rules"
    ):
        raise ValueError("P7 value-era rules schema differs")
    if _dict(p7_rules.get("source"), "P7 value-era source").get(
        "sha256"
    ) != value_profile.get("source_sha256"):
        raise ValueError("P7 typed qualification and value-era source differ")
    typed_ref = _dict(p7_rules.get("evidence"), "P7 rule evidence").get(
        "typed_candidate_qualification", {}
    )
    if _dict(typed_ref, "P7 typed receipt reference").get(
        "sha256"
    ) != input_sha256.get("p7_typed"):
        raise ValueError("P7 value-era rules do not bind the typed receipt")
    rule_groups = _dict(p7_rules.get("rules"), "P7 rules")
    date_rules = _dict(rule_groups.get("dates"), "P7 date rules")
    if (
        date_rules.get("selected_profile") is not None
        or date_rules.get("semantic_promotion") is not False
    ):
        raise ValueError("P7 date profile must remain unselected")

    expected_hash_keys = {
        "package_cohort",
        "header_cohort",
        "p7_typed",
        "p7_value_era_rules",
    }
    if set(input_sha256) != expected_hash_keys or any(
        type(value) is not str or len(value) != SHA256_HEX_LENGTH
        for value in input_sha256.values()
    ):
        raise ValueError("exact input receipt digests are required")

    p7_coverage = _dict(candidate.get("coverage"), "P7 candidate coverage")
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
        "schema_version": 1,
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
            "field_rows": _p7_field_rows(p7_typed),
            "cell_values": {
                "denominator": p7_cells,
                "interpreted": 0,
                "unresolved": p7_cells,
                "unavailable": 0,
                "denominator_relation": "independent_source_cell_denominator_not_added_to_historical_cohort",
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
            "cross_era_equivalence_qualified": False,
            "source_values_emitted": False,
            "new_sources_added": False,
        },
    }


def reconcile_from_paths(paths: dict[str, Path]) -> dict[str, Any]:
    reports = {key: _read_json(path) for key, path in paths.items()}
    digests = {key: _sha256(path) for key, path in paths.items()}
    return reconcile_workbook_field_states(
        reports["package_cohort"],
        reports["header_cohort"],
        reports["p7_typed"],
        reports["p7_value_era_rules"],
        digests,
    )


def canonical_json(report: dict[str, Any]) -> str:
    return (
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
