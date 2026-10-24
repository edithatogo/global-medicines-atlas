from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import global_medicines_atlas.mbs_workbook_field_reconciliation as field_reconciliation
from global_medicines_atlas.mbs_workbook_field_reconciliation import (
    P7_DATE_INFERENCE_PATH,
    P7_DATE_INFERENCE_SHA256,
    _candidate_identity,  # ruff: ignore[import-private-name]
    _dict,  # ruff: ignore[import-private-name]
    _dict_list,  # ruff: ignore[import-private-name]
    _int,  # ruff: ignore[import-private-name]
    _p7_source_field_states,  # ruff: ignore[import-private-name]
    _read_json,  # ruff: ignore[import-private-name]
    _sha256,  # ruff: ignore[import-private-name]
    canonical_json,
    reconcile_from_paths,
    reconcile_workbook_field_states,
)

P7_SOURCE_SHA256 = (
    "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
)


def _hash(index: int) -> str:
    return f"{index:064x}"


def _profile_digest(profile: dict[str, Any]) -> str:
    serialized = json.dumps(
        profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, str],
]:
    candidates = {
        str(index): {
            "source_sha256": _hash(index + 1),
            "member_path_sha256": _hash(index + 101),
            "member_sha256": _hash(index + 201),
            "field_state": "native_unresolved",
        }
        for index in range(91)
    }
    bindings = [
        {
            "column": chr(65 + index),
            "field": f"field_{index}",
            "status": "interpreted",
        }
        for index in range(8)
    ]
    profile = {
        "sheets": [
            {
                "ordinal": 0,
                "candidate_rows": [
                    {
                        "row_index": 0,
                        "column_bindings": bindings,
                        "contract_id": "mbs-demographic-workbook-v1",
                        "disposition": "exact_contract_match",
                    }
                ],
            }
        ]
    }
    assignments = [
        {
            "source_sha256": _hash(index + 1),
            "member_path_sha256": _hash(index + 101),
            "member_sha256": _hash(index + 201),
            "header_profile_sha256": _profile_digest(profile),
        }
        for index in range(91)
    ]
    package = {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-cohort-reconciliation",
        "status": "passed",
        "candidate_outputs_by_group": candidates,
        "unique_member_identities": 91,
        "totals": {
            "cells": 310_177_657,
            "decimal_candidates": 154_927_930,
            "missing_native_values": 2909,
        },
        "silver_field_state_coverage": {
            "native_unresolved_cells": 310_177_657,
            "interpreted_cells": 0,
            "source_column_meaning_inferred": False,
            "date_and_currency_meaning_inferred": False,
        },
    }
    headers = {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-header-cohort",
        "status": "passed",
        "profile_count": 1,
        "workbook_count": 91,
        "workbook_assignments": assignments,
        "header_profiles": [
            {
                "header_profile_sha256": _profile_digest(profile),
                "member_count": 91,
                "profile": profile,
            }
        ],
        "interpreted_header_column_binding_count": 728,
        "unresolved_header_label_count": 0,
        "unresolved_header_candidate_count": 0,
    }
    p7_typed: dict[str, Any] = {
        "kind": "p7-workbook",
        "workflow_commit": "11be72e328affc0df87395fd59165ef4f5bf9055",
        "workflow_run": "https://github.com/edithatogo/global-medicines-atlas/actions/runs/40094025412",
        "domain_value_profile": {
            "cells": 13_742,
            "source_sha256": P7_SOURCE_SHA256,
            "statuses": {
                "converted": 924,
                "header": 97,
                "missing_value": 6080,
                "preserved": 5321,
                "unmapped": 4,
                "unrepresentable": 36,
                "unsupported_format": 1280,
            },
        },
        "typed_candidate_package": {
            "coverage": {
                "interpreted_cells": 1_280,
                "unresolved_cells": 12_462,
                "formula_cells": 4,
                "error_cells": 2,
            },
            "date_inference": {
                "kind": "selected_internal_file_consistency_inference",
                "source_sha256": P7_SOURCE_SHA256,
                "profile": "dotted_DMY",
                "fields": [
                    "BenefitStartDate",
                    "DescriptionStartDate",
                    "FeeStartDate",
                    "ItemStartDate",
                ],
                "interpreted_cells": 1_194,
                "evidence_sha256": P7_DATE_INFERENCE_SHA256,
                "department_provenance_established": False,
                "domain_meaning_established": False,
                "other_workbooks_or_eras_in_scope": False,
            },
        },
        "p7_calendar_profile_evidence": {
            "sha256": _hash(600),
            "source_sha256": "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8",
            "date_order_selected": False,
            "source_values_emitted": False,
        },
        "sheets": [
            {"formula_cells": 2, "error_cells": 1},
            {"formula_cells": 2, "error_cells": 1},
        ],
        "workbook_field_lineage": {
            "source_sha256": P7_SOURCE_SHA256,
            "fields": [],
        },
    }
    date_profile = {
        "kind": "mbs_p7_unique_calendar_date_profile",
        "profile": {
            "date_order_selected": False,
            "source_values_emitted": False,
            "source_sha256": P7_SOURCE_SHA256,
            "by_field": {
                "BenefitStartDate": {
                    "ambiguous_calendar_order": 310,
                    "unique_calendar_date": 10,
                },
                "DescriptionStartDate": {
                    "ambiguous_calendar_order": 310,
                    "unique_calendar_date": 8,
                    "unique_dmy_calendar_date": 2,
                },
                "FeeStartDate": {
                    "ambiguous_calendar_order": 262,
                    "unique_calendar_date": 56,
                    "unique_dmy_calendar_date": 2,
                },
                "ItemStartDate": {
                    "ambiguous_calendar_order": 312,
                    "unique_calendar_date": 8,
                },
                "DerivedFeeStartDate": {"missing_value": 320},
                "EMSNChangeDate": {"missing_value": 320},
                "EMSNEndDate": {"missing_value": 320},
                "EMSNStartDate": {"missing_value": 320},
                "ItemEndDate": {"missing_value": 320},
                "QFEEndDate": {"missing_value": 320},
                "QFEStartDate": {"missing_value": 320},
            },
        },
    }
    target_by_date_field = {
        "BenefitStartDate": "benefits",
        "DerivedFeeStartDate": "fees",
        "DescriptionStartDate": "descriptions",
        "EMSNChangeDate": "caps",
        "EMSNEndDate": "caps",
        "EMSNStartDate": "caps",
        "FeeStartDate": "fees",
        "ItemEndDate": "services",
        "ItemStartDate": "services",
        "QFEEndDate": "services",
        "QFEStartDate": "services",
    }
    date_fields = date_profile["profile"]["by_field"]
    p7_typed["workbook_field_lineage"]["fields"] = [
        {
            "sheet_name": "Dates",
            "column": chr(ord("A") + index),
            "mapping_field": field,
            "mapping_target": target_by_date_field[field],
            "cell_count": 322,
            "statuses": [
                ["header", 2],
                [
                    "missing_value"
                    if "missing_value" in field_states
                    else "unsupported_format",
                    320,
                ],
            ],
        }
        for index, (field, field_states) in enumerate(
            sorted(date_fields.items())
        )
    ] + [
        {
            "sheet_name": "Other",
            "column": "A",
            "mapping_field": "ItemNum",
            "mapping_target": "services",
            "cell_count": 10_196,
            "statuses": [["header", 75], ["preserved", 10_121]],
        },
        {
            "sheet_name": "Other",
            "column": "B",
            "mapping_field": None,
            "mapping_target": "unmapped",
            "cell_count": 4,
            "statuses": [["unmapped", 4]],
        },
    ]
    hashes = {
        key: _hash(index + 500)
        for index, key in enumerate((
            "package_cohort",
            "header_cohort",
            "p7_typed",
            "p7_run_receipt",
            "p7_date_profile",
            "p7_date_inference",
            "p7_value_era_rules",
        ))
    }
    hashes["p7_date_profile"] = hashlib.sha256(
        json.dumps(date_profile).encode()
    ).hexdigest()
    hashes["p7_date_inference"] = hashlib.sha256(
        Path(P7_DATE_INFERENCE_PATH).read_bytes()
    ).hexdigest()
    p7_typed["p7_calendar_profile_evidence"]["sha256"] = hashes[
        "p7_date_profile"
    ]
    p7_typed["_exact_main_qualification"] = {
        "run_id": 40094025412,
        "url": "https://github.com/edithatogo/global-medicines-atlas/actions/runs/40094025412",
        "conclusion": "success",
        "exact_commit": "11be72e328affc0df87395fd59165ef4f5bf9055",
        "python": "3.15.1",
    }
    p7_typed["_artifact_receipt"] = {
        "artifact_id": 12559848688,
        "name": "workbook-storage-qualification",
        "path": "quality/qualifications/mbs-p7-workbook-storage-qualification-20261024-40094025412.json",
        "report_sha256": hashes["p7_typed"],
        "member_sha256": "fd893d18c6a96d7daf6c6bae27066f56d207b8d01c14d8fc7622bdc07af99bd",
    }
    p7_typed["_p7_date_profile"] = date_profile
    p7_typed["_p7_date_inference"] = json.loads(
        Path(P7_DATE_INFERENCE_PATH).read_text(encoding="utf-8")
    )
    p7_typed["_p7_date_profile_receipt"] = {
        "path": "quality/qualifications/mbs-p7-calendar-profile-20261024-40088209026.json",
        "sha256": hashes["p7_date_profile"],
    }
    p7_typed["_run_receipt"] = {
        "schema_id": "global-medicines-atlas.mbs-p7-exact-main-workbook-storage-run-receipt",
        "workflow": p7_typed["_exact_main_qualification"],
        "artifact": p7_typed["_artifact_receipt"],
        "calendar_profile": p7_typed["_p7_date_profile_receipt"],
    }
    p7_rules = {
        "schema_id": "global-medicines-atlas.mbs-p7-value-era-rules",
        "source": {"sha256": P7_SOURCE_SHA256},
        "evidence": {
            "typed_candidate_qualification": {"sha256": _hash(999)},
            "exact_main_storage_qualification": {"sha256": hashes["p7_typed"]},
            "exact_main_run_receipt": {"sha256": hashes["p7_run_receipt"]},
            "calendar_profile": {
                "path": "quality/qualifications/mbs-p7-calendar-profile-20261024-40088209026.json",
                "sha256": hashes["p7_date_profile"],
            },
        },
        "rules": {
            "dates": {
                "selected_profile": None,
                "semantic_promotion": False,
                "lexical_date_cells": 1280,
                "ambiguous_date_shaped_cells": 1194,
                "calendar_compatibility": {
                    "both_dmy_and_mdy_valid": 1276,
                    "dmy_only": 4,
                    "mdy_only": 0,
                },
            },
            "schema_eras": {
                "historical_workbook": "p7-2024-07",
                "current_xml": "xml-v3-2025-07",
            },
        },
    }
    return package, headers, p7_typed, p7_rules, hashes


def test_reconciles_header_and_body_states_without_adding_denominators() -> (
    None
):
    inputs = _inputs()
    report = reconcile_workbook_field_states(*inputs)
    assert canonical_json(report) == canonical_json(
        reconcile_workbook_field_states(*inputs)
    )
    cohort = report["historical_workbook_cohort"]
    assert cohort["identity_matches"] == 91
    assert cohort["header_column_roles"] == {
        "denominator": 728,
        "interpreted": 728,
        "unresolved": 0,
        "unavailable": 0,
        "unresolved_header_candidates": 0,
        "unresolved_header_labels": 0,
        "denominator_relation": "separate_non_additive_header_role_occurrences",
    }
    assert cohort["cell_values"]["denominator"] == 310_177_657
    assert cohort["cell_values"]["unresolved"] == 310_177_657
    assert cohort["cell_values"]["interpreted"] == 0
    assert "header_column_roles" not in cohort["cell_values"]


def test_report_separates_field_mapping_from_value_state() -> None:
    report = reconcile_workbook_field_states(*_inputs())
    cohort = report["historical_workbook_cohort"]
    assert len(cohort["field_rows"]) == 8
    assert (
        sum(row["workbooks_represented"] for row in cohort["field_rows"]) == 728
    )
    assert all(
        row["header_state"] == "interpreted" for row in cohort["field_rows"]
    )
    assert all(
        row["source_value_state"] == "native_unresolved"
        for row in cohort["field_rows"]
    )
    p7_fields = report["p7_workbook"]["field_rows"]
    assert len(p7_fields) == 13
    item_num = next(row for row in p7_fields if row["field"] == "ItemNum")
    assert item_num["cell_count"] == 10_196
    assert item_num["conversion_statuses"] == [
        {"state": "header", "count": 75},
        {"state": "preserved", "count": 10_121},
    ]
    date_fields = report["p7_workbook"]["date_field_states"]
    assert sum(row["interpreted"] for row in date_fields) == 1_280
    assert (
        sum(
            row["date_states"].get("ambiguous_calendar_order", 0)
            for row in date_fields
        )
        == 1_194
    )
    assert sum(row["native_unresolved"] for row in date_fields) == 2_240
    assert sum(row["unavailable"] for row in date_fields) == 0


def test_p7_separates_header_cells_from_value_field_states() -> None:
    report = reconcile_workbook_field_states(*_inputs())
    p7 = report["p7_workbook"]
    assert p7["source_cells"] == {
        "denominator": 13_742,
        "header_cells": 97,
        "value_cells": 13_645,
        "denominator_relation": "header_cells_plus_value_cells",
    }
    assert p7["header_column_roles"] == {
        "denominator": 97,
        "interpreted": 97,
        "unresolved": 0,
        "unavailable": 0,
        "denominator_relation": "separate_non_additive_header_role_occurrences",
    }
    assert p7["cell_values"] == {
        "denominator": 13_645,
        "interpreted": 1_280,
        "unresolved": 12_365,
        "unavailable": 0,
        "denominator_relation": "non_header_cell_values_only_header_role_denominator_not_added",
    }
    fields = p7["source_field_states"]
    assert len(fields) == 13
    assert sum(row["value_cells"]["denominator"] for row in fields) == 13_645
    assert sum(row["value_cells"]["interpreted"] for row in fields) == 1_280
    assert (
        sum(row["value_cells"]["native_unresolved"] for row in fields) == 12_365
    )
    fee_start = next(
        row for row in fields if row["source_field"] == "FeeStartDate"
    )
    assert fee_start["value_cells"] == {
        "denominator": 320,
        "interpreted": 320,
        "native_unresolved": 0,
        "unavailable": 0,
    }
    unmapped = next(
        row for row in fields if row["source_field"] == "unmapped::Other::B"
    )
    assert unmapped["value_cells"] == {
        "denominator": 4,
        "interpreted": 0,
        "native_unresolved": 4,
        "unavailable": 0,
    }


def test_p7_source_field_states_reject_conflicting_mapping_targets() -> None:
    field_rows = [
        {
            "field": "SharedField",
            "mapping_target": target,
            "sheet_name": "Sheet",
            "column": column,
            "cell_count": 1,
            "conversion_statuses": [],
            "header_state": "interpreted",
        }
        for target, column in (("fees", "A"), ("benefits", "B"))
    ]
    with pytest.raises(ValueError, match="inconsistent mapping targets"):
        _p7_source_field_states(field_rows, [])


def test_p7_source_field_states_reject_date_fields_without_lineage() -> None:
    with pytest.raises(ValueError, match="lack source-column lineage"):
        _p7_source_field_states([], [{"field": "MissingField"}])


def test_p7_source_field_states_reject_date_denominator_drift() -> None:
    field_rows = [
        {
            "field": "DateField",
            "mapping_target": "services",
            "sheet_name": "Sheet",
            "column": "A",
            "cell_count": 2,
            "conversion_statuses": [],
            "header_state": "interpreted",
        }
    ]
    date_rows = [{"field": "DateField", "cell_count": 1}]
    with pytest.raises(ValueError, match="denominators differ"):
        _p7_source_field_states(field_rows, date_rows)


def test_p7_rejects_uninterpreted_header_roles() -> None:
    package, headers, typed, rules, hashes = _inputs()
    typed["workbook_field_lineage"]["fields"][-2]["mapping_target"] = "unmapped"
    with pytest.raises(ValueError, match="header role states differ"):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_p7_rejects_source_value_constant_drift(monkeypatch: Any) -> None:
    package, headers, typed, rules, hashes = _inputs()
    monkeypatch.setattr(field_reconciliation, "P7_VALUE_CELL_COUNT", 13_644)
    with pytest.raises(ValueError, match="non-header field-state denominator"):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_p7_rejects_field_state_aggregate_drift(monkeypatch: Any) -> None:
    package, headers, typed, rules, hashes = _inputs()
    original = field_reconciliation._p7_source_field_states

    def changed_field_states(
        field_rows: list[dict[str, Any]], date_rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        rows = original(field_rows, date_rows)
        rows[0]["value_cells"]["native_unresolved"] -= 1
        return rows

    monkeypatch.setattr(
        field_reconciliation, "_p7_source_field_states", changed_field_states
    )
    with pytest.raises(ValueError, match="source field states differ"):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def _rehash_headers(headers: dict[str, Any]) -> None:
    profile = headers["header_profiles"][0]["profile"]
    digest = _profile_digest(profile)
    headers["header_profiles"][0]["header_profile_sha256"] = digest
    for assignment in headers["workbook_assignments"]:
        assignment["header_profile_sha256"] = digest


def test_rejects_unrecognized_header_field_state() -> None:
    package, headers, typed, rules, hashes = _inputs()
    headers["header_profiles"][0]["profile"]["sheets"][0]["candidate_rows"][0][
        "column_bindings"
    ][0]["status"] = "unknown"
    _rehash_headers(headers)
    headers["interpreted_header_column_binding_count"] = 637
    headers["unresolved_header_label_count"] = 91
    with pytest.raises(ValueError, match="header field binding is malformed"):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_rejects_interpreted_header_without_canonical_field() -> None:
    package, headers, typed, rules, hashes = _inputs()
    headers["header_profiles"][0]["profile"]["sheets"][0]["candidate_rows"][0][
        "column_bindings"
    ][0]["field"] = None
    _rehash_headers(headers)
    with pytest.raises(
        ValueError, match="interpreted header binding lacks a field"
    ):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_rejects_p7_field_lineage_with_wrong_source_identity() -> None:
    package, headers, typed, rules, hashes = _inputs()
    typed["workbook_field_lineage"]["source_sha256"] = _hash(778)
    with pytest.raises(
        ValueError, match="P7 field lineage source identity differs"
    ):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_rejects_p7_field_conversion_statuses_that_do_not_cover_cells() -> None:
    package, headers, typed, rules, hashes = _inputs()
    typed["workbook_field_lineage"]["fields"][0]["statuses"] = [
        ["preserved", 13_741]
    ]
    with pytest.raises(
        ValueError, match="P7 field status counts differ from cell count"
    ):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_rejects_unknown_p7_field_mapping_target() -> None:
    package, headers, typed, rules, hashes = _inputs()
    typed["workbook_field_lineage"]["fields"][0]["mapping_target"] = "inferred"
    with pytest.raises(
        ValueError, match="P7 field mapping target is unsupported"
    ):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_p7_diagnostics_are_orthogonal_and_date_order_stays_unselected() -> (
    None
):
    report = reconcile_workbook_field_states(*_inputs())
    p7 = report["p7_workbook"]
    assert p7["cell_values"] == {
        "denominator": 13_645,
        "interpreted": 1_280,
        "unresolved": 12_365,
        "unavailable": 0,
        "denominator_relation": "non_header_cell_values_only_header_role_denominator_not_added",
    }
    assert p7["orthogonal_diagnostics"]["formula_cells"] == 4
    assert p7["orthogonal_diagnostics"]["error_cells"] == 2
    assert p7["orthogonal_diagnostics"]["date_order_compatibility"] == {
        "both_dmy_and_mdy_valid": 1276,
        "dmy_only": 4,
        "mdy_only": 0,
    }
    assert p7["orthogonal_diagnostics"]["date_profile_selected"] is False
    assert (
        p7["orthogonal_diagnostics"][
            "internal_file_consistency_inference_selected"
        ]
        is True
    )
    assert (
        p7["orthogonal_diagnostics"]["file_consistency_dmy_interpreted_cells"]
        == 1_194
    )
    assert (
        p7["orthogonal_diagnostics"]["uniquely_determined_calendar_dates"] == 86
    )
    assert p7["orthogonal_diagnostics"]["ambiguous_date_shaped_cells"] == 1194
    assert (
        p7["orthogonal_diagnostics"]["diagnostics_are_additive_to_cell_state"]
        is False
    )
    assert "display_value" not in canonical_json(report)


def test_rejects_member_identity_mismatch_even_when_denominators_match() -> (
    None
):
    package, headers, typed, rules, hashes = _inputs()
    changed_header = copy.deepcopy(headers)
    changed_header["workbook_assignments"][0]["member_sha256"] = _hash(999)
    with pytest.raises(ValueError, match="exact candidate cohort"):
        reconcile_workbook_field_states(
            package, changed_header, typed, rules, hashes
        )


def test_rejects_profile_member_count_mismatch_with_same_total() -> None:
    package, headers, typed, rules, hashes = _inputs()
    changed_header = copy.deepcopy(headers)
    second_profile = copy.deepcopy(changed_header["header_profiles"][0])
    second_profile["profile"]["synthetic_variant"] = True
    second_digest = _profile_digest(second_profile["profile"])
    second_profile["header_profile_sha256"] = second_digest
    second_profile["member_count"] = 1
    changed_header["header_profiles"][0]["member_count"] = 90
    changed_header["header_profiles"].append(second_profile)
    changed_header["profile_count"] = 2
    changed_header["workbook_assignments"][0]["header_profile_sha256"] = (
        second_digest
    )
    changed_header["workbook_assignments"][1]["header_profile_sha256"] = (
        second_digest
    )
    with pytest.raises(
        ValueError, match="member counts differ from assignments"
    ):
        reconcile_workbook_field_states(
            package, changed_header, typed, rules, hashes
        )


def test_rejects_p7_status_total_drift() -> None:
    package, headers, typed, rules, hashes = _inputs()
    changed_typed = copy.deepcopy(typed)
    changed_typed["domain_value_profile"]["statuses"]["preserved"] -= 1
    with pytest.raises(ValueError, match="conversion statuses differ"):
        reconcile_workbook_field_states(
            package, headers, changed_typed, rules, hashes
        )


def test_rejects_missing_selected_p7_inference_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, headers, typed, rules, hashes = _inputs()
    monkeypatch.setattr(
        field_reconciliation,
        "validate_p7_date_consistency_inference",
        lambda *_args, **_kwargs: (None, P7_DATE_INFERENCE_SHA256),
    )
    with pytest.raises(ValueError, match="selected date inference evidence"):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_rejects_p7_candidate_inference_binding_mismatch() -> None:
    package, headers, typed, rules, hashes = _inputs()
    typed["typed_candidate_package"]["date_inference"]["source_sha256"] = _hash(
        999
    )
    with pytest.raises(ValueError, match="candidate date inference binding"):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_rejects_unpinned_p7_inference_input_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, headers, typed, rules, hashes = _inputs()
    monkeypatch.setattr(
        field_reconciliation,
        "validate_p7_date_consistency_inference",
        lambda *_args, **_kwargs: (
            {
                "date_fields_with_populated_values": [
                    "BenefitStartDate",
                    "DescriptionStartDate",
                    "FeeStartDate",
                    "ItemStartDate",
                ]
            },
            P7_DATE_INFERENCE_SHA256,
        ),
    )
    hashes["p7_date_inference"] = _hash(999)
    with pytest.raises(ValueError, match="receipt digest differs"):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_rejects_p7_header_role_drift() -> None:
    package, headers, typed, rules, hashes = _inputs()
    changed_typed = copy.deepcopy(typed)
    changed_typed["domain_value_profile"]["statuses"]["header"] -= 1
    changed_typed["domain_value_profile"]["statuses"]["preserved"] += 1
    with pytest.raises(ValueError, match="P7 header cell denominator differs"):
        reconcile_workbook_field_states(
            package, headers, changed_typed, rules, hashes
        )


def test_rejects_stale_summary_counters() -> None:
    package, headers, typed, rules, hashes = _inputs()
    changed_package = copy.deepcopy(package)
    changed_package["silver_field_state_coverage"][
        "native_unresolved_cells"
    ] -= 1
    with pytest.raises(ValueError, match="cell-state totals"):
        reconcile_workbook_field_states(
            changed_package, headers, typed, rules, hashes
        )


def test_rejects_a_selected_p7_date_profile() -> None:
    package, headers, typed, rules, hashes = _inputs()
    changed_rules = copy.deepcopy(rules)
    changed_rules["rules"]["dates"]["selected_profile"] = "DMY"
    with pytest.raises(ValueError, match="date profile must remain unselected"):
        reconcile_workbook_field_states(
            package, headers, typed, changed_rules, hashes
        )


@pytest.mark.parametrize("value", [True, -1, 1.0, "1"])
def test_nonnegative_integer_helper_rejects_non_integer_values(
    value: Any,
) -> None:
    with pytest.raises(ValueError, match="nonnegative integer"):
        _int(value, "count")


@pytest.mark.parametrize("value", [None, {}, "not-a-list", [1]])
def test_dict_list_helper_rejects_malformed_lists(value: Any) -> None:
    with pytest.raises((TypeError, ValueError), match="list of objects"):
        _dict_list(value, "rows")


def test_dict_helper_rejects_non_objects() -> None:
    with pytest.raises(TypeError, match="must be an object"):
        _dict([], "object")


def test_candidate_identity_helper_rejects_bad_digest() -> None:
    with pytest.raises(ValueError, match="identity is malformed"):
        _candidate_identity({"source_sha256": "short"})


def test_json_reader_rejects_non_object_and_hashes_file(tmp_path: Any) -> None:
    path = tmp_path / "receipt.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(TypeError, match="root must be an object"):
        _read_json(path)
    path.write_text('{"ok": true}', encoding="utf-8")
    assert _read_json(path) == {"ok": True}
    assert len(_sha256(path)) == 64


def test_reconcile_from_paths_binds_exact_file_digests(tmp_path: Any) -> None:
    package, headers, typed, rules, _ = _inputs()
    run_receipt = typed["_run_receipt"]
    documents = {
        "package_cohort": package,
        "header_cohort": headers,
        "p7_typed": typed,
        "p7_run_receipt": run_receipt,
        "p7_date_profile": typed["_p7_date_profile"],
        "p7_date_inference": typed["_p7_date_inference"],
        "p7_value_era_rules": rules,
    }
    paths: dict[str, Any] = {}
    for name, value in documents.items():
        path = tmp_path / f"{name}.json"
        if name == "p7_date_inference":
            path.write_bytes(Path(P7_DATE_INFERENCE_PATH).read_bytes())
        else:
            path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = path
    typed_digest = hashlib.sha256(paths["p7_typed"].read_bytes()).hexdigest()
    run_receipt["artifact"]["report_sha256"] = typed_digest
    paths["p7_run_receipt"].write_text(
        json.dumps(run_receipt), encoding="utf-8"
    )
    rules["evidence"]["exact_main_storage_qualification"]["sha256"] = (
        typed_digest
    )
    rules["evidence"]["exact_main_run_receipt"]["sha256"] = hashlib.sha256(
        paths["p7_run_receipt"].read_bytes()
    ).hexdigest()
    rules["evidence"]["calendar_profile"]["sha256"] = hashlib.sha256(
        paths["p7_date_profile"].read_bytes()
    ).hexdigest()
    paths["p7_value_era_rules"].write_text(json.dumps(rules), encoding="utf-8")
    report = reconcile_from_paths(paths)
    assert set(report["inputs"]) == set(documents)
    assert all(len(item["sha256"]) == 64 for item in report["inputs"].values())


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("package_schema", "package cohort is not qualified"),
        ("header_schema", "header cohort is not qualified"),
        ("identity_container", "identity records are malformed"),
        ("candidate_denominator", "exact 91-workbook denominator"),
        ("candidate_duplicate", "candidate workbook identities are not unique"),
        ("candidate_promoted", "promoted workbook state"),
        ("cohort_summary", "summary denominator differs"),
        ("profile_shape", "header profile group identity is malformed"),
        (
            "profile_digest_mismatch",
            "header profile digest differs from profile",
        ),
        ("profile_sheets", "header profile sheets are malformed"),
        ("profile_duplicate", "duplicate header profile digest"),
        ("profile_member_count", "profile member denominator differs"),
        ("profile_reference", "unknown header profile"),
        ("assignment_digest", "header profile digest is malformed"),
        ("interpreted_total", "interpreted header binding count differs"),
        ("unresolved_total", "unresolved header label count differs"),
        ("unresolved_candidate", "unresolved header candidates remain"),
        ("unsupported_semantics", "unsupported historical workbook semantics"),
        ("p7_kind", "typed qualification kind differs"),
        ("p7_denominator", "all-cell unresolved denominator differs"),
        ("p7_field_count", "P7 field rows differ from cell denominator"),
        ("p7_statuses_not_list", "P7 field conversion statuses are malformed"),
        ("rules_schema", "value-era rules schema differs"),
        ("p7_source", "typed qualification and value-era source differ"),
        ("rules_typed_ref", "do not bind exact-main typed receipt"),
        ("date_profile", "date profile must remain unselected"),
        ("run_receipt_schema", "exact-main run receipt schema differs"),
        ("run_commit", "exact-main qualification identity differs"),
        ("artifact_member", "exact-main artifact identity differs"),
        (
            "calendar_profile_hash",
            "calendar profile does not bind the exact source",
        ),
        (
            "date_field_counts",
            "unique date fields differ from typed qualification",
        ),
        (
            "date_rule_counts",
            "date profile counts differ from the value-era rules",
        ),
        ("hashes", "exact input receipt digests are required"),
        ("p7_status_total", "statuses differ from cell denominator"),
        ("p7_formula_count", "formula diagnostic denominators differ"),
        ("p7_error_count", "error diagnostic denominators differ"),
        ("date_compatibility", "date compatibility counts differ"),
        ("workflow_reference", "P7 exact-main qualification identity differs"),
        ("date_profile_identity", "P7 calendar profile identity differs"),
        ("run_receipt_reference", "do not bind the exact-main run"),
        ("date_receipt_reference", "do not bind the calendar profile"),
        ("date_receipt_path", "calendar path differs"),
        ("p7_state_totals", "exact-main cell-state totals differ"),
    ],
)
# ruff: ignore[too-many-branches, too-many-statements]
# Keep all adversarial receipt mutations in one table-driven audit.
def test_receipt_validation_fails_closed(case: str, message: str) -> None:
    package, headers, typed, rules, hashes = _inputs()
    if case == "package_schema":
        package["schema_id"] = "wrong"
    elif case == "header_schema":
        headers["schema_id"] = "wrong"
    elif case == "identity_container":
        package["candidate_outputs_by_group"] = None
    elif case == "candidate_denominator":
        package["candidate_outputs_by_group"].pop("0")
        headers["workbook_assignments"].pop()
    elif case == "candidate_duplicate":
        for key in ("source_sha256", "member_path_sha256", "member_sha256"):
            package["candidate_outputs_by_group"]["1"][key] = package[
                "candidate_outputs_by_group"
            ]["0"][key]
    elif case == "candidate_promoted":
        package["candidate_outputs_by_group"]["0"]["field_state"] = (
            "interpreted"
        )
    elif case == "cohort_summary":
        package["unique_member_identities"] = 90
    elif case == "profile_shape":
        headers["header_profiles"][0]["header_profile_sha256"] = 3
    elif case == "profile_digest_mismatch":
        headers["header_profiles"][0]["profile"]["sheets"][0]["ordinal"] = 1
    elif case == "profile_sheets":
        headers["header_profiles"][0]["profile"]["sheets"] = None
        _rehash_headers(headers)
    elif case == "profile_duplicate":
        headers["header_profiles"].append(
            copy.deepcopy(headers["header_profiles"][0])
        )
        headers["profile_count"] = 2
    elif case == "profile_member_count":
        headers["header_profiles"][0]["member_count"] = 90
    elif case == "profile_reference":
        headers["workbook_assignments"][0]["header_profile_sha256"] = _hash(999)
    elif case == "assignment_digest":
        headers["workbook_assignments"][0]["header_profile_sha256"] = None
    elif case == "interpreted_total":
        headers["interpreted_header_column_binding_count"] = 727
    elif case == "unresolved_total":
        headers["unresolved_header_label_count"] = 1
    elif case == "unresolved_candidate":
        headers["unresolved_header_candidate_count"] = 1
    elif case == "unsupported_semantics":
        package["silver_field_state_coverage"][
            "source_column_meaning_inferred"
        ] = True
    elif case == "p7_kind":
        typed["kind"] = "wrong"
    elif case == "p7_denominator":
        typed["typed_candidate_package"]["coverage"]["unresolved_cells"] = 1
    elif case == "p7_field_count":
        typed["workbook_field_lineage"]["fields"][0]["cell_count"] = 13_741
    elif case == "p7_statuses_not_list":
        typed["workbook_field_lineage"]["fields"][0]["statuses"] = None
    elif case == "rules_schema":
        rules["schema_id"] = "wrong"
    elif case == "p7_source":
        rules["source"]["sha256"] = _hash(888)
    elif case == "rules_typed_ref":
        rules["evidence"]["exact_main_storage_qualification"]["sha256"] = _hash(
            889
        )
    elif case == "date_profile":
        rules["rules"]["dates"]["selected_profile"] = "dmy"
    elif case == "run_receipt_schema":
        typed["_run_receipt"]["schema_id"] = "wrong"
    elif case == "run_commit":
        typed["_run_receipt"]["workflow"]["exact_commit"] = _hash(999)
    elif case == "artifact_member":
        typed["_run_receipt"]["artifact"]["member_sha256"] = _hash(998)
    elif case == "calendar_profile_hash":
        typed["_run_receipt"]["calendar_profile"]["sha256"] = _hash(997)
    elif case == "date_field_counts":
        typed["_p7_date_profile"]["profile"]["by_field"]["BenefitStartDate"][
            "unique_calendar_date"
        ] = 11
    elif case == "date_rule_counts":
        rules["rules"]["dates"]["ambiguous_date_shaped_cells"] = 1193
    elif case == "hashes":
        hashes["extra"] = _hash(900)
    elif case == "p7_status_total":
        typed["domain_value_profile"]["statuses"]["converted"] -= 1
    elif case == "p7_formula_count":
        typed["sheets"][0]["formula_cells"] = 0
    elif case == "p7_error_count":
        typed["sheets"][0]["error_cells"] = 0
    elif case == "date_compatibility":
        rules["rules"]["dates"]["calendar_compatibility"]["dmy_only"] = 3
    elif case == "workflow_reference":
        typed["workflow_commit"] = _hash(901)
    elif case == "date_profile_identity":
        typed["_p7_date_profile"]["profile"]["source_values_emitted"] = True
    elif case == "run_receipt_reference":
        rules["evidence"]["exact_main_run_receipt"]["sha256"] = _hash(902)
    elif case == "date_receipt_reference":
        rules["evidence"]["calendar_profile"]["sha256"] = _hash(903)
    elif case == "date_receipt_path":
        rules["evidence"]["calendar_profile"]["path"] = "other.json"
    elif case == "p7_state_totals":
        typed["typed_candidate_package"]["coverage"]["interpreted_cells"] = 87
        typed["typed_candidate_package"]["coverage"]["unresolved_cells"] = (
            13_655
        )
    with pytest.raises((TypeError, ValueError), match=message):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_p7_field_rows_reject_malformed_status_pairs() -> None:
    package, headers, typed, rules, hashes = _inputs()
    typed["workbook_field_lineage"]["fields"][0]["statuses"] = [["preserved"]]
    with pytest.raises(ValueError, match="conversion status is malformed"):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)


def test_p7_field_rows_reject_empty_status_name() -> None:
    package, headers, typed, rules, hashes = _inputs()
    typed["workbook_field_lineage"]["fields"][0]["statuses"] = [["", 13_742]]
    with pytest.raises(ValueError, match="conversion status is malformed"):
        reconcile_workbook_field_states(package, headers, typed, rules, hashes)
