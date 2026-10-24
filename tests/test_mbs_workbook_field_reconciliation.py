from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import pytest

from global_medicines_atlas.mbs_workbook_field_reconciliation import (
    canonical_json,
    reconcile_workbook_field_states,
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
                "candidate_rows": [
                    {
                        "column_bindings": bindings,
                        "contract_id": "mbs-demographic-workbook-v1",
                        "disposition": "exact_contract_match",
                    }
                ]
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
    p7_typed = {
        "kind": "p7-workbook",
        "domain_value_profile": {
            "cells": 13_742,
            "source_sha256": _hash(777),
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
                "unresolved_cells": 13_742,
                "formula_cells": 4,
                "error_cells": 2,
            }
        },
        "sheets": [
            {"formula_cells": 2, "error_cells": 1},
            {"formula_cells": 2, "error_cells": 1},
        ],
    }
    hashes = {
        key: _hash(index + 500)
        for index, key in enumerate((
            "package_cohort",
            "header_cohort",
            "p7_typed",
            "p7_value_era_rules",
        ))
    }
    p7_rules = {
        "schema_id": "global-medicines-atlas.mbs-p7-value-era-rules",
        "source": {"sha256": _hash(777)},
        "evidence": {
            "typed_candidate_qualification": {"sha256": hashes["p7_typed"]}
        },
        "rules": {
            "dates": {
                "selected_profile": None,
                "semantic_promotion": False,
                "lexical_date_cells": 1280,
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


def test_p7_diagnostics_are_orthogonal_and_date_order_stays_unselected() -> (
    None
):
    report = reconcile_workbook_field_states(*_inputs())
    p7 = report["p7_workbook"]
    assert p7["cell_values"] == {
        "denominator": 13_742,
        "interpreted": 0,
        "unresolved": 13_742,
        "unavailable": 0,
        "denominator_relation": "independent_source_cell_denominator_not_added_to_historical_cohort",
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
