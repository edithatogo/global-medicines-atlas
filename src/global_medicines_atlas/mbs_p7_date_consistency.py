"""Value-free, exact-copy calendar consistency evidence for MBS P7."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from typing import Any, cast

from .australian_source_contracts import mbs_field_contracts
from .mbs_workbook_domain import iter_workbook_domain_batches
from .receipts import SourceReceipt

_DATE_FIELDS = frozenset({
    "BenefitStartDate",
    "DescriptionStartDate",
    "FeeStartDate",
    "ItemStartDate",
}).intersection(
    field.native_name
    for field in mbs_field_contracts()
    if field.value_type == "source_date"
)
_DOTTED_DMY = re.compile(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}\Z")
_SOURCE_SHA256 = (
    "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
)
_SOURCE_BYTES = 87727
# The pinned workbook has four contracted date fields with 320 non-header
# cells each. Requiring this complete inventory prevents a partial extraction
# from qualifying an era-wide file-consistency inference.
_EXPECTED_PROFILED_CELLS_PER_FIELD = 320
_EXPECTED_SCHEMA_VERSION = 1
P7_DATE_FIELDS = _DATE_FIELDS
_EXPECTED_INFERENCE_SHA256 = (
    "a9df045f3893c0f2774d80a2a0d806ad19c17c4d7173da64bde57d1169e06486"
)
_EXPECTED_INFERENCE_RUN = (
    "https://github.com/edithatogo/global-medicines-atlas/actions/runs/"
    "40139026116"
)
_EXPECTED_INFERENCE_COMMIT = "cc5c6615be033b60a2e1bf6c50dc64d2cae9763c"


def validate_p7_date_consistency_inference(
    evidence: bytes | None,
    *,
    expected_sha256: str | None,
    source_sha256: str,
    source_byte_count: int,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate the retained exact-main, value-free P7 inference receipt."""
    if evidence is None:
        if expected_sha256 is not None:
            raise ValueError("P7 date inference digest has no evidence")
        return None, None
    actual_sha256 = hashlib.sha256(evidence).hexdigest()
    if (
        expected_sha256 != _EXPECTED_INFERENCE_SHA256
        or actual_sha256 != _EXPECTED_INFERENCE_SHA256
    ):
        raise ValueError("P7 date inference evidence digest differs")
    if source_sha256 != _SOURCE_SHA256 or source_byte_count != _SOURCE_BYTES:
        raise ValueError("P7 date inference source identity differs")
    try:
        report = json.loads(evidence)
        profile = report["profile"]
        decision = report["decision"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("P7 date inference evidence is invalid") from exc
    fields = sorted(_DATE_FIELDS)
    expected_by_field = {
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
    }
    expected_statuses = {
        "ambiguous_calendar_order": 1194,
        "unique_calendar_date": 82,
        "unique_dmy_calendar_date": 4,
    }
    normalized_statuses = {
        status: sum(
            int(profile["by_field"][field].get(status, 0)) for field in fields
        )
        for status in expected_statuses
    }
    expected_evidence_counts = {
        "ambiguous_calendar_order": 1194,
        "formula_unresolved": 0,
        "invalid": 0,
        "source_error": 0,
        "unique_dmy_calendar_date": 4,
        "unique_mdy_calendar_date": 0,
        "unsupported_serial_date": 0,
    }
    checks = [
        report.get("schema_id")
        == "global-medicines-atlas.mbs-p7-date-consistency-inference",
        report.get("schema_version") == _EXPECTED_SCHEMA_VERSION,
        profile.get("schema_version") == _EXPECTED_SCHEMA_VERSION,
        profile.get("expected_profiled_cells_per_field")
        == _EXPECTED_PROFILED_CELLS_PER_FIELD,
        profile.get("source_sha256") == _SOURCE_SHA256,
        profile.get("source_byte_count") == _SOURCE_BYTES,
        profile.get("source_values_emitted") is False,
        profile.get("date_order_selected") is False,
        decision.get("source_sha256") == _SOURCE_SHA256,
        decision.get("source_values_emitted") is False,
        decision.get("selection_status")
        == "selected_internal_file_consistency_inference",
        decision.get("selected_profile") == "mbs-dmy",
        decision.get("workflow_run") == _EXPECTED_INFERENCE_RUN,
        decision.get("workflow_commit") == _EXPECTED_INFERENCE_COMMIT,
        decision.get("department_provenance_or_attestation")
        == "not_established",
        decision.get("inference_basis")
        == "internal exact-copy file-consistency inference from value-free calendar and lexical counts",
        decision.get("lexical_profile") == "dd_mm_yyyy_dotted",
        decision.get("expected_date_fields") == fields,
        decision.get("date_fields_with_populated_values") == fields,
        decision.get("profile_completeness")
        == {
            field: {
                "expected_cells": _EXPECTED_PROFILED_CELLS_PER_FIELD,
                "observed_cells": _EXPECTED_PROFILED_CELLS_PER_FIELD,
            }
            for field in fields
        },
        decision.get("scope")
        == {
            "domain_meaning": False,
            "other_mbs_eras": False,
            "other_workbooks": False,
            "source_sha256": _SOURCE_SHA256,
        },
        profile.get("expected_date_fields") == fields,
        profile.get("profiled_cells_by_field")
        == dict.fromkeys(fields, _EXPECTED_PROFILED_CELLS_PER_FIELD),
        profile.get("by_field") == expected_by_field,
        profile.get("lexical_profile_by_field")
        == {
            field: {"dd_mm_yyyy_dotted": _EXPECTED_PROFILED_CELLS_PER_FIELD}
            for field in fields
        },
        all(
            sum(profile["by_field"][field].values())
            == _EXPECTED_PROFILED_CELLS_PER_FIELD
            for field in fields
        ),
        normalized_statuses == expected_statuses,
        all(
            not profile["by_field"][field].get(status, 0)
            for field in fields
            for status in (
                "unique_mdy_calendar_date",
                "invalid",
                "formula_unresolved",
                "source_error",
                "unsupported_serial_date",
            )
        ),
        decision.get("evidence_counts") == expected_evidence_counts,
    ]
    if not all(checks):
        raise ValueError(
            "P7 date inference evidence does not qualify this source"
        )
    return decision, actual_sha256


def _validated_counts(value: Any) -> dict[str, dict[str, int]] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, dict[str, int]] = {}
    for field, statuses in cast("dict[object, object]", value).items():
        if not isinstance(field, str) or not isinstance(statuses, dict):
            return None
        normalized: dict[str, int] = {}
        for status, count in cast("dict[object, object]", statuses).items():
            if (
                not isinstance(status, str)
                or not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
            ):
                return None
            normalized[status] = count
        result[field] = normalized
    return result


def _date_status(value: str) -> str:
    if not _DOTTED_DMY.fullmatch(value):
        return "invalid"
    first, second, year = (int(part) for part in value.split("."))
    valid_dmy = valid_mdy = False
    try:
        date(year, second, first)
        valid_dmy = True
    except ValueError:
        pass
    try:
        date(year, first, second)
        valid_mdy = True
    except ValueError:
        pass
    if valid_dmy and valid_mdy and first == second:
        return "unique_calendar_date"
    if valid_dmy and valid_mdy:
        return "ambiguous_calendar_order"
    if valid_dmy:
        return "unique_dmy_calendar_date"
    if valid_mdy:
        return "unique_mdy_calendar_date"
    return "invalid"


def classify_p7_cell_status(row: dict[str, Any]) -> str:
    """Classify cell state before its display value can hide it."""
    value = row["display_value"]
    if row["cell_type"] == "e":
        return "source_error"
    if row["formula_state"] != "missing_field":
        return "formula_unresolved"
    if value is None:
        return (
            "null"
            if "display_value" in row["present_properties"]
            else "missing_value"
        )
    if row["cell_type"] in {None, "n"}:
        return "unsupported_serial_date"
    return _date_status(value)


def profile_p7_date_consistency(
    payload: bytes, receipt: SourceReceipt
) -> dict[str, Any]:
    """Aggregate exact source date fields without returning source values."""
    if receipt.payload.sha256 != _SOURCE_SHA256:
        raise ValueError("P7 consistency profile requires the pinned source")
    by_field: defaultdict[str, Counter[str]] = defaultdict(Counter)
    lexical_by_field: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for batch in iter_workbook_domain_batches(payload, receipt):
        for row in batch.to_pylist():
            field_name = row["mapping_field"]
            if row["row_kind"] == "header" or field_name not in _DATE_FIELDS:
                continue
            value = row["display_value"]
            status = classify_p7_cell_status(row)
            if (
                value is not None
                and row["cell_type"] not in {None, "n"}
                and row["cell_type"] != "e"
                and row["formula_state"] == "missing_field"
            ):
                lexical_by_field[field_name][
                    "dd_mm_yyyy_dotted"
                    if _DOTTED_DMY.fullmatch(value)
                    else "other_text_profile"
                ] += 1
            by_field[field_name][status] += 1
    return {
        "schema_version": 1,
        "source_sha256": receipt.payload.sha256,
        "source_byte_count": receipt.payload.byte_count,
        "date_order_selected": False,
        "source_values_emitted": False,
        "expected_date_fields": sorted(_DATE_FIELDS),
        "expected_profiled_cells_per_field": _EXPECTED_PROFILED_CELLS_PER_FIELD,
        "profiled_cells_by_field": {
            field: sum(counts.values())
            for field, counts in sorted(by_field.items())
        },
        "by_field": {
            field: dict(sorted(counts.items()))
            for field, counts in sorted(by_field.items())
        },
        "lexical_profile_by_field": {
            field: dict(sorted(counts.items()))
            for field, counts in sorted(lexical_by_field.items())
        },
    }


def decide_p7_date_consistency(
    profile: dict[str, Any], *, expected_source_sha256: str
) -> dict[str, Any]:
    """Return a bounded DMY inference only when all exact-copy gates pass."""
    by_field = _validated_counts(profile.get("by_field"))
    lexical_by_field = _validated_counts(
        profile.get("lexical_profile_by_field")
    )
    structure_valid = (
        profile.get("schema_version") == 1
        and profile.get("source_sha256") == expected_source_sha256
        and profile.get("source_byte_count") == _SOURCE_BYTES
        and profile.get("date_order_selected") is False
        and profile.get("source_values_emitted") is False
        and by_field is not None
        and lexical_by_field is not None
        and frozenset(by_field) == _DATE_FIELDS
        and all(
            sum(by_field[field].values()) == _EXPECTED_PROFILED_CELLS_PER_FIELD
            for field in _DATE_FIELDS
        )
        and expected_source_sha256 == _SOURCE_SHA256
    )
    field_counts = by_field or {}
    lexical_counts = lexical_by_field or {}
    date_fields = sorted(
        field
        for field, counts in field_counts.items()
        if any(
            status not in {"missing_value", "null"} and count > 0
            for status, count in counts.items()
        )
    )
    allowed_statuses = {
        "ambiguous_calendar_order",
        "unique_calendar_date",
        "unique_dmy_calendar_date",
    }
    statuses_pass = bool(date_fields) and all(
        all(
            status in allowed_statuses or status in {"missing_value", "null"}
            for status, count in field_counts[field].items()
            if count
        )
        for field in field_counts
    )
    dmy_only = sum(
        counts.get("unique_dmy_calendar_date", 0)
        for counts in field_counts.values()
    )
    mdy_only = sum(
        counts.get("unique_mdy_calendar_date", 0)
        for counts in field_counts.values()
    )
    lexical_pass = bool(date_fields) and all(
        set(lexical_counts.get(field, {})) == {"dd_mm_yyyy_dotted"}
        and sum(lexical_counts[field].values())
        == sum(
            count
            for status, count in field_counts[field].items()
            if status
            in {
                "ambiguous_calendar_order",
                "unique_calendar_date",
                "unique_dmy_calendar_date",
                "unique_mdy_calendar_date",
                "invalid",
            }
        )
        for field in date_fields
    )
    selected = (
        structure_valid
        and statuses_pass
        and dmy_only > 0
        and mdy_only == 0
        and lexical_pass
    )
    counts = {
        status: sum(
            statuses.get(status, 0) for statuses in field_counts.values()
        )
        for status in (
            "ambiguous_calendar_order",
            "unique_dmy_calendar_date",
            "unique_mdy_calendar_date",
            "invalid",
            "formula_unresolved",
            "unsupported_serial_date",
            "source_error",
        )
    }
    return {
        "selected_profile": "mbs-dmy" if selected else None,
        "selection_status": "selected_internal_file_consistency_inference"
        if selected
        else "unresolved",
        "reason": "all_populated_date_cells_are_dmy_valid_and_at_least_one_is_dmy_only"
        if selected
        else "exact_copy_profile_does_not_meet_dmy_consistency_criteria",
        "source_sha256": profile.get("source_sha256"),
        "date_fields_with_populated_values": date_fields,
        "expected_date_fields": sorted(_DATE_FIELDS),
        "profile_completeness": {
            field: {
                "expected_cells": _EXPECTED_PROFILED_CELLS_PER_FIELD,
                "observed_cells": sum(field_counts.get(field, {}).values()),
            }
            for field in sorted(_DATE_FIELDS)
        },
        "lexical_profile": "dd_mm_yyyy_dotted" if selected else None,
        "evidence_counts": counts,
        "inference_basis": "internal exact-copy file-consistency inference from value-free calendar and lexical counts",
        "department_provenance_or_attestation": "not_established",
        "scope": {
            "source_sha256": expected_source_sha256,
            "other_workbooks": False,
            "other_mbs_eras": False,
            "domain_meaning": False,
        },
        "source_values_emitted": False,
    }
