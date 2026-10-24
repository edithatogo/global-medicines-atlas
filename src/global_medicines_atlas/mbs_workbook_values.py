"""Loss-aware domain values alongside every native legacy workbook cell."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Any

import pyarrow as pa

from .australian_source_contracts import MbsFieldContract, mbs_field_contracts
from .mbs_p7_date_consistency import (
    P7_DATE_FIELDS,
    validate_p7_date_consistency_inference,
)
from .mbs_typed_values import (
    CONVERSION_VERSION,
    DATE_FORMATS,
    convert_mbs_value,
)
from .mbs_workbook_domain import iter_workbook_domain_batches
from .receipts import SourceReceipt
from .silver_field_semantics import SilverFieldSemantics, qualified_date

_FIELDS = {field.native_name: field for field in mbs_field_contracts()}
_NUMERIC_TYPES = frozenset({"aud_decimal", "decimal", "percentage"})
_TEXT_STORAGE = frozenset({"s", "str", "inlineStr", "d"})
_DECIMAL = pa.decimal128(38, 9)
_ADDITIONS = (
    pa.field("interpretation_state", pa.string(), nullable=False),
    pa.field("interpretation_reason", pa.string(), nullable=False),
    pa.field("semantic_evidence_sha256", pa.string()),
    pa.field("semantic_definition", pa.string()),
    pa.field("domain_value_type", pa.string()),
    pa.field("domain_value_state", pa.string(), nullable=False),
    pa.field("domain_status", pa.string(), nullable=False),
    pa.field("domain_currency", pa.string()),
    pa.field("domain_text", pa.string()),
    pa.field("domain_date", pa.date32()),
    pa.field("domain_decimal", _DECIMAL),
)
_P7_SOURCE_SHA256 = (
    "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
)
_P7_DATE_PROFILE_SHA256 = (
    "c9b49f60a9a608bc77674a2094b8fd4439115fc17bb200b04fc202c6b463d1bf"
)
_P7_DATE_INFERENCE_SHA256 = (
    "a9df045f3893c0f2774d80a2a0d806ad19c17c4d7173da64bde57d1169e06486"
)
_DATE_PROFILE_SCHEMA_VERSION = 2
_MAX_DATE_COMPONENT = 12
_P7_DATE_DEFINITION = (
    "A dotted text date cell is interpreted only when evaluating the DMY and "
    "MDY candidates yields exactly one distinct valid calendar date. A single "
    "valid order or equal-component candidates qualify; no workbook order is "
    "selected."
)


def _validated_p7_date_profile(
    receipt: SourceReceipt,
    evidence: bytes | None,
    expected_sha256: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if evidence is None:
        if expected_sha256 is not None:
            raise ValueError("P7 date profile digest has no evidence")
        return None, None
    actual_sha256 = sha256(evidence).hexdigest()
    if (
        expected_sha256 != _P7_DATE_PROFILE_SHA256
        or actual_sha256 != _P7_DATE_PROFILE_SHA256
    ):
        raise ValueError("P7 date profile evidence digest differs")
    if receipt.payload.sha256 != _P7_SOURCE_SHA256:
        raise ValueError("P7 date profile source identity differs")
    try:
        document = json.loads(evidence)
        profile = document["profile"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("P7 date profile evidence is invalid") from exc
    expected = {
        "schema_version": _DATE_PROFILE_SCHEMA_VERSION,
        "source_sha256": _P7_SOURCE_SHA256,
        "source_byte_count": receipt.payload.byte_count,
        "date_order_selected": False,
        "source_values_emitted": False,
        "rule": "unique_valid_calendar_date_per_value_no_order_selected",
    }
    if document.get("kind") != "mbs_p7_unique_calendar_date_profile" or any(
        profile.get(key) != value for key, value in expected.items()
    ):
        raise ValueError(
            "P7 date profile evidence does not qualify this source"
        )
    return profile, actual_sha256


def _unique_calendar_date(value: str) -> date | None:
    if not re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", value):
        return None
    first, second, year = (int(part) for part in value.split("."))
    candidates: set[date] = set()
    for month, day in ((second, first), (first, second)):
        try:
            candidates.add(date(year, month, day))
        except ValueError:
            continue
    return next(iter(candidates)) if len(candidates) == 1 else None


def _calendar_profile_status(value: str) -> str:
    parsed = _unique_calendar_date(value)
    if parsed is not None:
        first, second, _ = (int(part) for part in value.split("."))
        if first == second:
            return "unique_calendar_date"
        return (
            "unique_dmy_calendar_date"
            if first > _MAX_DATE_COMPONENT
            else "unique_mdy_calendar_date"
        )
    if not re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", value):
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
    return "ambiguous_calendar_order" if valid_dmy and valid_mdy else "invalid"


def _profile_counts_match(
    payload: bytes, receipt: SourceReceipt, profile: dict[str, Any]
) -> bool:
    observed: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for batch in iter_workbook_domain_batches(payload, receipt):
        for row in batch.to_pylist():
            name = row["mapping_field"]
            if row["row_kind"] == "header" or _FIELDS.get(name) is None:
                continue
            if _FIELDS[name].value_type != "source_date":
                continue
            value = row["display_value"]
            if value is None:
                state = (
                    "null"
                    if "display_value" in row["present_properties"]
                    else "missing_value"
                )
            elif row["cell_type"] == "e":
                state = "source_error"
            elif row["cell_type"] in {None, "n"}:
                state = "unsupported_serial_date"
            else:
                state = _calendar_profile_status(value)
            observed[name][state] += 1
    expected = {
        name: dict(sorted(counts.items()))
        for name, counts in sorted(observed.items())
    }
    return profile.get("by_field") == expected


def _values(  # ruff: ignore[too-many-return-statements]
    row: dict[str, Any],
    date_format: str | None,
    calendar_profile_sha256: str | None = None,
    date_inference_sha256: str | None = None,
) -> dict[str, Any]:
    value = row["display_value"]
    state = (
        "value"
        if value is not None
        else "null"
        if "display_value" in row["present_properties"]
        else "missing_value"
    )
    result: dict[str, Any] = {
        "interpretation_state": "native_unresolved",
        "interpretation_reason": "Legacy workbook field meaning is not qualified",
        "semantic_evidence_sha256": None,
        "semantic_definition": None,
        "domain_value_type": None,
        "domain_value_state": state,
        "domain_status": "unmapped",
        "domain_currency": None,
        "domain_text": None,
        "domain_date": None,
        "domain_decimal": None,
    }
    if row["row_kind"] == "header":
        return {**result, "domain_status": "header"}
    if row["mapping_field"] is None:
        return result
    field = _FIELDS.get(row["mapping_field"])
    result["domain_value_type"] = (
        field.value_type if field else "legacy_annotation"
    )
    result["domain_currency"] = (
        "AUD" if field and field.value_type == "aud_decimal" else None
    )
    if value is None or row["cell_type"] == "e":
        return {
            **result,
            "domain_status": state if value is None else "source_error",
        }
    if field is None:
        return {**result, "domain_text": value, "domain_status": "preserved"}
    if (
        field.value_type == "source_date"
        and calendar_profile_sha256 is not None
        and row["source_sha256"] == _P7_SOURCE_SHA256
    ):
        qualified = _qualified_profile_date(
            row, result, calendar_profile_sha256
        )
        if qualified["interpretation_state"] == "interpreted":
            return qualified
        date_format = None
    if (
        field.value_type == "source_date"
        and date_inference_sha256 is not None
        and row["source_sha256"] == _P7_SOURCE_SHA256
        and row["mapping_field"] in P7_DATE_FIELDS
    ):
        inferred = _qualified_file_consistency_date(
            row, result, date_inference_sha256
        )
        if inferred["interpretation_state"] == "interpreted":
            return inferred
    return _convert_field(row, field, date_format, result)


def _qualified_file_consistency_date(
    row: dict[str, Any], result: dict[str, Any], evidence_sha256: str
) -> dict[str, Any]:
    """Apply the selected internal DMY convention to exact P7 literal dates."""
    if (
        row["cell_type"] not in _TEXT_STORAGE
        or row["cell_type"] == "e"
        or row["formula_state"] != "missing_field"
    ):
        return result
    value = row["display_value"]
    if (
        value is None
        or re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", value) is None
    ):
        return result
    day, month, year = (int(part) for part in value.split("."))
    try:
        parsed = date(year, month, day)
    except ValueError:
        return result
    return {
        **result,
        "interpretation_state": "interpreted",
        "interpretation_reason": (
            "Exact P7 internal file-consistency inference selects DMY for "
            "this literal date; Department provenance and broader domain "
            "meaning are not established"
        ),
        "semantic_evidence_sha256": evidence_sha256,
        "semantic_definition": (
            "Valid DD.MM.YYYY literal date interpreted under the selected "
            "internal exact-file consistency inference for the pinned July "
            "2024 P7 workbook only"
        ),
        "domain_date": parsed,
        "domain_status": "qualified_file_consistency_dmy",
    }


def _qualified_profile_date(
    row: dict[str, Any], result: dict[str, Any], evidence_sha256: str
) -> dict[str, Any]:
    if (
        row["cell_type"] not in _TEXT_STORAGE
        or row["cell_type"] == "e"
        or row["formula_state"] != "missing_field"
    ):
        return result
    value = row["display_value"]
    if value is None:
        return result
    parsed = _unique_calendar_date(value)
    if parsed is None:
        return result
    return {
        **result,
        "interpretation_state": "interpreted",
        "interpretation_reason": "Exact P7 calendar profile uniquely determines this cell date without selecting an order",
        "semantic_evidence_sha256": evidence_sha256,
        "semantic_definition": _P7_DATE_DEFINITION,
        "domain_date": parsed,
        "domain_status": "qualified_unique_calendar_date",
    }


def _convert_field(
    row: dict[str, Any],
    field: MbsFieldContract,
    date_format: str | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    numeric_storage = row["cell_type"] in {None, "n"}
    if not numeric_storage and row["cell_type"] not in _TEXT_STORAGE:
        return {**result, "domain_status": "unsupported_storage_type"}
    if numeric_storage and field.value_type == "source_date":
        return {**result, "domain_status": "unsupported_serial_date"}
    if numeric_storage and field.value_type in _NUMERIC_TYPES:
        # OOXML numeric cells admit exponent notation; reuse their bounded
        # exact conversion, without changing the stricter XML text grammar.
        return {
            **result,
            "domain_decimal": row["decimal_value"],
            "domain_status": row["conversion_status"],
        }
    converted = convert_mbs_value(
        field.native_name,
        row["display_value"],
        "value",
        date_format=date_format,
    )
    typed = converted.typed_value
    result["domain_status"] = converted.status
    if isinstance(typed, Decimal):
        try:
            pa.scalar(typed, type=_DECIMAL)
        except pa.ArrowInvalid:
            result["domain_status"] = "unrepresentable"
        else:
            result["domain_decimal"] = typed
    elif isinstance(typed, date):
        result["domain_date"] = typed
    elif isinstance(typed, str):
        result["domain_text"] = typed
    return result


def iter_workbook_value_batches(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    date_format: str | None = None,
    calendar_profile_evidence: bytes | None = None,
    calendar_profile_sha256: str | None = None,
    date_inference_evidence: bytes | None = None,
    date_inference_sha256: str | None = None,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Type known fields without discarding native cells or cache provenance.

    Dates require an explicit text profile. Numeric Excel serials are never
    converted to dates. Legacy annotations remain literal strings, not flags
    or clinical/status conclusions. Decimal overflow/scale loss is explicit.
    """
    if date_format is not None and date_format not in DATE_FORMATS:
        raise ValueError("unsupported date format profile")
    profile, profile_sha256 = _validated_p7_date_profile(
        receipt, calendar_profile_evidence, calendar_profile_sha256
    )
    inference, inference_sha256 = validate_p7_date_consistency_inference(
        date_inference_evidence,
        expected_sha256=date_inference_sha256,
        source_sha256=receipt.payload.sha256,
        source_byte_count=receipt.payload.byte_count,
    )
    if (
        inference is not None
        and date_inference_sha256 != _P7_DATE_INFERENCE_SHA256
    ):
        raise ValueError("P7 date inference digest is not the pinned receipt")
    if calendar_profile_evidence is not None:
        if profile is None:
            raise ValueError("P7 date profile evidence is missing")
        if not _profile_counts_match(payload, receipt, profile):
            raise ValueError("P7 date profile counts differ from source")
    for batch in iter_workbook_domain_batches(
        payload, receipt, rows_per_batch=rows_per_batch
    ):
        metadata = dict(batch.schema.metadata or {})
        metadata.update({
            b"schema_name": b"global-medicines-atlas.mbs-workbook-values.cells",
            b"schema_version": b"1.1",
            b"semantic_usage": b"native_observations_only_until_qualified",
            b"conversion_version": CONVERSION_VERSION.encode(),
            b"date_profile": (date_format or "unselected").encode(),
            b"date_profile_evidence_sha256": (
                profile_sha256 or "unselected"
            ).encode(),
            b"date_inference": (
                "selected_internal_file_consistency_inference"
                if inference is not None
                else "unselected"
            ).encode(),
            b"date_inference_evidence_sha256": (
                inference_sha256 or "unselected"
            ).encode(),
            b"date_interpretation": b"per_cell_unique_calendar_only_no_serial_or_formula_dates",
            b"currency_interpretation": b"per_domain_field",
            b"decimal_type": b"decimal128(38,9)",
        })
        schema = batch.schema
        for field in _ADDITIONS:
            schema = schema.append(field)  # pyright: ignore[reportUnknownMemberType]
        schema = schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]
        yield pa.RecordBatch.from_pylist(
            [
                {
                    **row,
                    **_values(
                        row,
                        date_format,
                        profile_sha256,
                        inference_sha256,
                    ),
                }
                for row in batch.to_pylist()
            ],
            schema=schema,
        )


def profile_workbook_values(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    date_format: str | None = None,
) -> dict[str, Any]:
    """Report conversion denominators without promoting semantic validity."""
    statuses: Counter[str] = Counter()
    by_field: defaultdict[str, Counter[str]] = defaultdict(Counter)
    source_errors = 0
    date_encodings: Counter[str] = Counter()
    date_fields: defaultdict[str, Counter[str]] = defaultdict(Counter)
    date_order_compatibility: Counter[str] = Counter()
    date_order_by_field: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for batch in iter_workbook_value_batches(
        payload, receipt, date_format=date_format
    ):
        for row in batch.to_pylist():
            status = row["domain_status"]
            statuses[status] += 1
            by_field[row["mapping_field"] or "(unmapped)"][status] += 1
            source_errors += row["error_code"] is not None
            field = _FIELDS.get(row["mapping_field"])
            if field is not None and field.value_type == "source_date":
                encoding = _date_encoding(row)
                date_encodings[encoding] += 1
                date_fields[field.native_name][encoding] += 1
                if encoding == "two_two_four_dot":
                    compatibility = _date_order_compatibility(
                        row["display_value"]
                    )
                    date_order_compatibility[compatibility] += 1
                    date_order_by_field[field.native_name][compatibility] += 1
    return {
        "schema_version": 1,
        "conversion_version": CONVERSION_VERSION,
        "date_profile": date_format,
        "source_sha256": receipt.payload.sha256,
        "cells": sum(statuses.values()),
        "statuses": dict(sorted(statuses.items())),
        "by_field": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_field.items())
        },
        "source_error_cells": source_errors,
        "date_encoding_profile_version": 1,
        "date_encoding_interpretation": "lexical_shape_only_not_calendar_or_order",
        "date_encoding_counts": dict(sorted(date_encodings.items())),
        "date_encodings_by_field": {
            key: dict(sorted(value.items()))
            for key, value in sorted(date_fields.items())
        },
        "date_order_compatibility_profile_version": 1,
        "date_order_compatibility_interpretation": (
            "calendar_validity_only_no_date_convention_selected"
        ),
        "date_order_compatibility_counts": dict(
            sorted(date_order_compatibility.items())
        ),
        "date_order_compatibility_by_field": {
            key: dict(sorted(value.items()))
            for key, value in sorted(date_order_by_field.items())
        },
        "semantic_promotion": False,
    }


def _date_encoding(row: dict[str, Any]) -> str:
    """Observe native storage/text shapes without choosing a date convention."""
    if row["row_kind"] == "header":
        return "header"
    if row["cell_type"] == "e":
        return "source_error"
    value = row["display_value"]
    if value is None:
        return row["domain_value_state"]
    storage_categories = {
        None: "numeric_storage_uninterpreted",
        "n": "numeric_storage_uninterpreted",
        "d": "native_date_storage_uninterpreted",
    }
    if row["cell_type"] in storage_categories:
        return storage_categories[row["cell_type"]]
    if row["cell_type"] not in _TEXT_STORAGE:
        return "unsupported_storage"
    return _text_date_shape(value)


def _text_date_shape(value: str) -> str:
    if not value:
        return "empty_text"
    for pattern, label in (
        (r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", "two_two_four_dot"),
        (r"[0-9]{2}/[0-9]{2}/[0-9]{4}", "two_two_four_slash"),
        (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "four_two_two_hyphen"),
    ):
        if re.fullmatch(pattern, value):
            return label
    return "other_text"


def _date_order_compatibility(value: str) -> str:
    """Classify which day/month order forms a real calendar date.

    This value-free aggregate does not select a workbook convention. It only
    records whether the lexical components are calendar-valid as DMY, MDY,
    both, or neither.
    """
    first, second, year = (int(part) for part in value.split("."))
    valid_orders: set[str] = set()
    for order, month, day in (
        ("dmy", second, first),
        ("mdy", first, second),
    ):
        try:
            date(year, month, day)
        except ValueError:
            continue
        valid_orders.add(order)
    if valid_orders == {"dmy", "mdy"}:
        return "both"
    if valid_orders == {"dmy"}:
        return "dmy_only"
    if valid_orders == {"mdy"}:
        return "mdy_only"
    return "neither"


def workbook_date_for_comparison(row: dict[str, Any]) -> date:
    """Gate actual P7 temporal consumers independently of lexical parsing."""
    if row["domain_value_type"] != "source_date":
        raise ValueError("workbook field is not a source date")
    semantics = SilverFieldSemantics(
        source_sha256=row["source_sha256"],
        native_name=row["mapping_field"],
        value_kind="date",
        state=row["interpretation_state"],
        reason=row["interpretation_reason"],
        evidence_sha256=row["semantic_evidence_sha256"],
        semantic_definition=row.get("semantic_definition"),
        temporal_use_qualified=(
            row.get("domain_status") != "qualified_file_consistency_dmy"
        ),
    )
    return qualified_date(semantics, row["domain_date"])
