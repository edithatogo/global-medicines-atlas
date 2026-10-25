"""Bounded value-shape counts for the frozen MBS workbook contract.

This module classifies native storage and lexical shapes only. It never emits
cell values and does not infer dates, currency, meaning, or cross-era rules.
"""

from __future__ import annotations

import operator
import re
from collections import Counter
from collections.abc import Iterable
from typing import Any, cast

CONTRACT_ID = "mbs-demographic-workbook-v1"
EXPECTED_FIELDS = (
    "calendar_year_label",
    "processing_month_label",
    "schedule_item_identifier",
    "state_label",
    "age_range_label",
    "gender_label",
    "service_count_label",
    "benefit_amount_label_currency_unresolved",
)
EXPECTED_HEADERS = (
    "Year",
    "Month",
    "Item_Number",
    "State",
    "Age_Range",
    "Gender",
    "Services",
    "Benefits ($)",
)


def _object(value: object, message: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(message)
    return cast("dict[str, Any]", value)


_INTEGER = re.compile(r"[+-]?[0-9]+\Z")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+\.[0-9]+|\.[0-9]+)\Z")
_EXPONENT = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)[eE][+-]?[0-9]+\Z"
)
_DELIMITED_COMPONENTS = re.compile(r"[0-9]+(?:[./-][0-9]+)+\Z")


def _column_number(label: str) -> int:
    if not label or not label.isascii() or not label.isalpha():
        raise ValueError("MBS header column label is malformed")
    result = 0
    for char in label:
        if not "A" <= char <= "Z":
            raise ValueError("MBS header column label is malformed")
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def _header_bindings(  # ruff: ignore[too-many-branches, too-many-locals, too-many-statements] -- validate exact eight-field contract bindings
    profile: dict[str, Any],
) -> dict[str, dict[int, dict[str, Any]]]:
    raw_sheets = profile.get("sheets")
    if not isinstance(raw_sheets, list) or not raw_sheets:
        raise ValueError("MBS workbook profile sheets are malformed")
    sheets: dict[str, dict[int, dict[str, Any]]] = {}
    seen_fields: set[str] = set()
    for raw_sheet in cast("list[object]", raw_sheets):
        sheet = _object(raw_sheet, "MBS workbook profile sheet is malformed")
        name = sheet.get("name")
        if not isinstance(name, str) or name in sheets:
            raise ValueError("MBS workbook profile sheet identity differs")
        targets: dict[int, dict[str, Any]] = {}
        candidates = sheet.get("candidate_rows", [])
        if not isinstance(candidates, list):
            raise TypeError("MBS workbook candidate rows are malformed")
        for raw_candidate in cast("list[object]", candidates):
            candidate = _object(
                raw_candidate, "MBS workbook header candidate is malformed"
            )
            disposition = candidate.get("disposition")
            if disposition != "exact_contract_match":
                raise ValueError(
                    "MBS workbook has an unresolved header candidate"
                )
            if candidate.get("contract_id") != CONTRACT_ID:
                raise ValueError("MBS workbook header contract differs")
            row_index = candidate.get("row_index")
            if type(row_index) is not int or row_index < 1:
                raise ValueError("MBS workbook header row identity differs")
            bindings = candidate.get("column_bindings")
            if not isinstance(bindings, list):
                raise TypeError("MBS workbook field bindings are malformed")
            bindings = cast("list[object]", bindings)
            if len(bindings) != len(EXPECTED_FIELDS):
                raise ValueError("MBS workbook header field count differs")
            labels_raw = candidate.get("labels", [])
            if not isinstance(labels_raw, list):
                raise TypeError("MBS workbook header labels are malformed")
            labels_raw = cast("list[object]", labels_raw)
            labels: dict[str, str] = {}
            for raw_label in labels_raw:
                label = _object(
                    raw_label, "MBS workbook header label is malformed"
                )
                label_column = label.get("column")
                label_text = label.get("text")
                if not isinstance(label_column, str) or not isinstance(
                    label_text, str
                ):
                    raise TypeError("MBS workbook header label is malformed")
                labels[label_column] = label_text
            for index, (raw_binding, expected_field, expected_header) in enumerate(
                zip(bindings, EXPECTED_FIELDS, EXPECTED_HEADERS, strict=True),
                start=1,
            ):
                binding = _object(
                    raw_binding, "MBS workbook field binding is malformed"
                )
                column = binding.get("column")
                field = binding.get("field")
                if not isinstance(field, str):
                    raise TypeError("MBS workbook field identity is malformed")
                if (
                    not isinstance(column, str)  # ruff: ignore[too-many-boolean-expressions] -- every contract binding property must match
                    or binding.get("status") != "interpreted"
                    or field != expected_field
                    or binding.get("native_header") != expected_header
                    or labels.get(column) != expected_header
                    or _column_number(column) != index
                    or field in seen_fields
                    or index in targets
                ):
                    raise ValueError("MBS workbook header binding differs")
                targets[index] = {
                    "field": field,
                    "header": expected_header,
                    "row_index": row_index,
                }
                seen_fields.add(field)
        sheets[name] = targets
    if seen_fields != set(EXPECTED_FIELDS):
        raise ValueError("MBS workbook profile does not bind all eight fields")
    if sum(bool(targets) for targets in sheets.values()) != 1:
        raise ValueError("MBS workbook must have one demographic data sheet")
    return sheets


def _lexical_shape(value: str, *, native_numeric: bool) -> str:  # ruff: ignore[too-many-return-statements] -- explicit disjoint lexeme categories
    if not value:
        return "empty_text"
    if native_numeric:
        if _INTEGER.fullmatch(value):
            return "numeric_integer_lexeme"
        if _DECIMAL.fullmatch(value):
            return "numeric_decimal_lexeme"
        if _EXPONENT.fullmatch(value):
            return "numeric_exponent_lexeme"
        return "numeric_other_lexeme"
    if _INTEGER.fullmatch(value):
        return "text_integer_lexeme"
    if _DECIMAL.fullmatch(value):
        return "text_decimal_lexeme"
    if _EXPONENT.fullmatch(value):
        return "text_exponent_lexeme"
    if _DELIMITED_COMPONENTS.fullmatch(value):
        separator = next(char for char in value if char in ".-/")
        return {
            ".": "text_dot_delimited_components",
            "/": "text_slash_delimited_components",
            "-": "text_hyphen_delimited_components",
        }[separator]
    if any(char.isalpha() for char in value) and any(
        char.isdigit() for char in value
    ):
        return "text_alphanumeric"
    return "text_other"


def _cell_shape(cell: dict[str, Any]) -> tuple[str, str, str, bool, bool]:
    properties = _object(
        cell.get("native_properties", {}),
        "MBS native cell properties are malformed",
    )
    cell_type = properties.get("cell_type")
    cell_type_key = cell_type if isinstance(cell_type, str) else "unspecified"
    state = cell.get("state")
    state_key = state if isinstance(state, str) else "unspecified"
    formula_present = properties.get("formula_present") is True
    raw_value = properties.get("raw_value")
    value = cell.get("value")
    error_present = state_key == "source_error" or cell_type_key == "e"
    if formula_present:
        shape = (
            "formula_with_cached_value"
            if raw_value is not None or value is not None
            else "formula_without_cached_value"
        )
    elif error_present:
        shape = "source_error"
    elif state == "null" or value is None:
        shape = "missing_value"
    elif cell_type == "b":
        shape = "boolean_literal"
    elif cell_type in {None, "n"}:
        shape = _lexical_shape(str(raw_value), native_numeric=True)
    elif cell_type in {"s", "inlineStr", "str", "d"}:
        shape = _lexical_shape(str(value), native_numeric=False)
    else:
        shape = "unsupported_native_type"
    return (
        shape,
        cell_type_key,
        state_key,
        formula_present,
        error_present,
    )


def _empty_field() -> dict[str, Any]:
    return {
        "cell_count": 0,
        "value_shapes": Counter(),
        "native_cell_types": Counter(),
        "native_states": Counter(),
        "formula_cells": 0,
        "formula_cells_with_cache": 0,
        "source_error_cells": 0,
        "native_missing_value_cells": 0,
        "missing_physical_cell_positions": 0,
    }


def _serial_field(field: dict[str, Any]) -> dict[str, Any]:
    return {
        "cell_count": field["cell_count"],
        "value_shapes": dict(sorted(field["value_shapes"].items())),
        "native_cell_types": dict(sorted(field["native_cell_types"].items())),
        "native_states": dict(sorted(field["native_states"].items())),
        "formula_cells": field["formula_cells"],
        "formula_cells_with_cache": field["formula_cells_with_cache"],
        "source_error_cells": field["source_error_cells"],
        "native_missing_value_cells": field["native_missing_value_cells"],
        "missing_physical_cell_positions": field[
            "missing_physical_cell_positions"
        ],
    }


def profile_workbook_records(  # ruff: ignore[too-many-branches, too-many-statements, too-many-locals] -- bounded native workbook event accounting
    records: Iterable[dict[str, Any]], profile: dict[str, Any]
) -> dict[str, Any]:
    """Count source-native shapes for the eight bound fields without values."""
    bindings = _header_bindings(profile)
    fields = {field: _empty_field() for field in EXPECTED_FIELDS}
    data_sheets = {
        name: targets for name, targets in bindings.items() if targets
    }
    header_seen: Counter[str] = Counter()
    header_cells = 0
    pre_header_cells = 0
    other_sheet_cells = 0
    out_of_contract_data_cells = 0
    source_cell_records = 0
    data_rows = 0
    row_count_by_field: Counter[str] = Counter()
    pending_key: tuple[str, int] | None = None
    pending_columns: set[int] = set()

    for record in records:  # ruff: ignore[too-many-nested-blocks] -- preserve streaming row/cell state without buffering source values
        kind = record.get("kind")
        if kind == "cell":
            source_cell_records += 1
            sheet_name = record.get("sheet_name")
            row_index = record.get("row_index")
            column_index = record.get("column_index")
            if (
                not isinstance(sheet_name, str)
                or type(row_index) is not int
                or type(column_index) is not int
            ):
                raise TypeError("MBS workbook native cell address is malformed")
            key = (sheet_name, row_index)
            if pending_key not in {None, key}:
                raise ValueError("MBS workbook records are not row ordered")
            pending_key = key
            pending_columns.add(column_index)
            targets = data_sheets.get(sheet_name)
            if targets is None:
                other_sheet_cells += 1
                continue
            candidate_row = next(iter(targets.values()))["row_index"]
            target = targets.get(column_index)
            if row_index < candidate_row:
                pre_header_cells += 1
                continue
            cell = record.get("cell")
            cell = _object(cell, "MBS workbook cell payload is malformed")
            if row_index == candidate_row:
                if target is None:
                    out_of_contract_data_cells += 1
                    continue
                if (
                    cell.get("state") != "value"
                    or cell.get("value") != target["header"]
                ):
                    raise ValueError(
                        "MBS workbook header cell readback differs"
                    )
                header_seen[target["field"]] += 1
                header_cells += 1
                continue
            if target is None:
                out_of_contract_data_cells += 1
                continue
            field = fields[target["field"]]
            shape, cell_type, state, formula, error = _cell_shape(cell)
            field["cell_count"] += 1
            field["value_shapes"][shape] += 1
            field["native_cell_types"][cell_type] += 1
            field["native_states"][state] += 1
            field["formula_cells"] += formula
            field["formula_cells_with_cache"] += formula and (
                cell.get("native_properties", {}).get("raw_value") is not None
                or cell.get("value") is not None
            )
            field["source_error_cells"] += error
            field["native_missing_value_cells"] += state == "null"
            continue
        if kind == "row":
            sheet_name = record.get("sheet_name")
            row_index = record.get("row_index")
            if not isinstance(sheet_name, str) or type(row_index) is not int:
                raise TypeError("MBS workbook native row address is malformed")
            key = (sheet_name, row_index)
            if pending_key not in {None, key}:
                raise ValueError("MBS workbook row/cell order differs")
            targets = data_sheets.get(sheet_name)
            if targets:
                candidate_row = next(iter(targets.values()))["row_index"]
                if row_index > candidate_row:
                    data_rows += 1
                    for column, target in targets.items():
                        row_count_by_field[target["field"]] += 1
                        if column not in pending_columns:
                            fields[target["field"]][
                                "missing_physical_cell_positions"
                            ] += 1
            pending_key = None
            pending_columns.clear()

    if pending_key is not None:
        raise ValueError("MBS workbook ended before row accounting")
    if header_seen != Counter(dict.fromkeys(EXPECTED_FIELDS, 1)):
        raise ValueError("MBS workbook header cell denominator differs")
    if (
        set(row_count_by_field) != set(EXPECTED_FIELDS)
        or len(set(row_count_by_field.values())) != 1
    ):
        raise ValueError("MBS workbook data row denominators differ by field")
    return {
        "source_cell_records": source_cell_records,
        "header_cells": header_cells,
        "pre_header_cells": pre_header_cells,
        "other_sheet_cells": other_sheet_cells,
        "out_of_contract_data_cells": out_of_contract_data_cells,
        "data_rows": data_rows,
        "field_row_counts": dict(sorted(row_count_by_field.items())),
        "fields": {
            field: _serial_field(counts)
            for field, counts in sorted(fields.items())
        },
        "source_values_emitted": False,
        "source_column_meanings_qualified": False,
        "currency_interpreted": False,
        "date_interpreted": False,
        "p7_workbook_in_scope": False,
        "p7_date_inference_applied": False,
        "p7_domain_date_semantics_qualified": False,
    }


def merge_archive_profiles(
    reports: list[dict[str, Any]], expected_archive_count: int
) -> dict[str, Any]:
    """Merge six archive counters while preserving per-archive shape strata."""
    if len(reports) != expected_archive_count:
        raise ValueError("MBS value-shape archive report denominator differs")
    seen: set[int] = set()
    merged = {field: _empty_field() for field in EXPECTED_FIELDS}
    archive_rows: list[dict[str, Any]] = []
    source_cells = header_cells = pre_header_cells = other_sheet_cells = 0
    outside_cells = data_rows = workbook_count = 0
    field_row_counts: Counter[str] = Counter()
    bindings: list[dict[str, Any]] = []
    for report in sorted(
        reports, key=lambda item: item.get("archive_index", -1)
    ):
        index = report.get("archive_index")
        if (
            type(index) is not int
            or index in seen
            or not 0 <= index < expected_archive_count
        ):
            raise ValueError("MBS value-shape archive index differs")
        seen.add(index)
        source_cells += report["source_cell_records"]
        header_cells += report["header_cells"]
        pre_header_cells += report["pre_header_cells"]
        other_sheet_cells += report["other_sheet_cells"]
        outside_cells += report["out_of_contract_data_cells"]
        data_rows += report["data_rows"]
        workbook_count += report["workbook_count"]
        if len(report["workbook_bindings"]) != report["workbook_count"]:
            raise ValueError(
                "MBS value-shape workbook binding denominator differs"
            )
        field_row_counts.update(report.get("field_row_counts", {}))
        bindings.extend(report["workbook_bindings"])
        archive_rows.append({
            "archive_index": index,
            "source_path": report["source"]["source_path"],
            "source_sha256": report["source"]["source_sha256"],
            "workbook_count": report["workbook_count"],
            "source_cell_records": report["source_cell_records"],
            "header_cells": report["header_cells"],
            "pre_header_cells": report["pre_header_cells"],
            "other_sheet_cells": report["other_sheet_cells"],
            "out_of_contract_data_cells": report["out_of_contract_data_cells"],
            "data_rows": report["data_rows"],
            "fields": report["fields"],
        })
        for field_name in EXPECTED_FIELDS:
            source = report["fields"][field_name]
            target = merged[field_name]
            for key in (
                "cell_count",
                "formula_cells",
                "formula_cells_with_cache",
                "source_error_cells",
                "native_missing_value_cells",
                "missing_physical_cell_positions",
            ):
                target[key] += source[key]
            for counter_name in (
                "value_shapes",
                "native_cell_types",
                "native_states",
            ):
                target[counter_name].update(source[counter_name])
    if seen != set(range(expected_archive_count)):
        raise ValueError("MBS value-shape archive indices are incomplete")
    if len(bindings) != len({row["candidate_output_id"] for row in bindings}):
        raise ValueError(
            "MBS value-shape candidate output identity is duplicated"
        )
    if len(bindings) != len({row["candidate_group"] for row in bindings}):
        raise ValueError(
            "MBS value-shape candidate group identity is duplicated"
        )
    if sum(row["cell_count"] for row in merged.values()) != sum(
        row["cell_count"]
        for report in reports
        for row in report["fields"].values()
    ):
        raise ValueError("MBS value-shape field counts do not conserve")
    return {
        "archive_count": expected_archive_count,
        "workbook_count": workbook_count,
        "source_cell_records": source_cells,
        "header_cells": header_cells,
        "pre_header_cells": pre_header_cells,
        "other_sheet_cells": other_sheet_cells,
        "out_of_contract_data_cells": outside_cells,
        "data_rows": data_rows,
        "field_row_counts": dict(sorted(field_row_counts.items())),
        "archives": archive_rows,
        "workbook_bindings": sorted(
            bindings, key=operator.itemgetter("candidate_group")
        ),
        "fields": {
            field: _serial_field(counts)
            for field, counts in sorted(merged.items())
        },
        "source_values_emitted": False,
        "source_column_meanings_qualified": False,
        "currency_interpreted": False,
        "date_interpreted": False,
        "p7_workbook_in_scope": False,
        "p7_date_inference_applied": False,
        "p7_domain_date_semantics_qualified": False,
    }
