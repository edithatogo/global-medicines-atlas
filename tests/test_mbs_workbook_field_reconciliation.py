from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import pytest

from global_medicines_atlas.mbs_workbook_field_reconciliation import (
    _candidate_identity,  # ruff: ignore[import-private-name]
    _dict,  # ruff: ignore[import-private-name]
    _dict_list,  # ruff: ignore[import-private-name]
    _int,  # ruff: ignore[import-private-name]
    _read_json,  # ruff: ignore[import-private-name]
    _sha256,  # ruff: ignore[import-private-name]
    canonical_json,
    reconcile_from_paths,
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
        "workbook_field_lineage": {
            "source_sha256": _hash(777),
            "fields": [
                {
                    "sheet_name": "Sheet1",
                    "column": "A",
                    "mapping_field": "ItemNum",
                    "mapping_target": "services",
                    "cell_count": 13_742,
                    "statuses": [["preserved", 13_742]],
                }
            ],
        },
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


def test_report_lists_each_field_role_and_source_value_state() -> None:
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
    assert p7_fields == [
        {
            "sheet_name": "Sheet1",
            "column": "A",
            "field": "ItemNum",
            "mapping_target": "services",
            "header_state": "interpreted",
            "source_value_state": "native_unresolved",
            "cell_count": 13_742,
            "conversion_statuses": [{"state": "preserved", "count": 13_742}],
        }
    ]


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
    documents = {
        "package_cohort": package,
        "header_cohort": headers,
        "p7_typed": typed,
        "p7_value_era_rules": rules,
    }
    paths: dict[str, Any] = {}
    for name, value in documents.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = path
    typed_digest = hashlib.sha256(paths["p7_typed"].read_bytes()).hexdigest()
    rules["evidence"]["typed_candidate_qualification"]["sha256"] = typed_digest
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
        ("rules_typed_ref", "do not bind the typed receipt"),
        ("date_profile", "date profile must remain unselected"),
        ("hashes", "exact input receipt digests are required"),
        ("p7_status_total", "statuses differ from cell denominator"),
        ("p7_formula_count", "formula diagnostic denominators differ"),
        ("p7_error_count", "error diagnostic denominators differ"),
        ("date_compatibility", "date compatibility counts differ"),
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
        rules["evidence"]["typed_candidate_qualification"]["sha256"] = _hash(
            889
        )
    elif case == "date_profile":
        rules["rules"]["dates"]["selected_profile"] = "dmy"
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
