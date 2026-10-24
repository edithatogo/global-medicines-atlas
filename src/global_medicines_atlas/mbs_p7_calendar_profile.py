"""Aggregate-only calendar uniqueness profile for legacy P7 date cells."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from .australian_source_contracts import mbs_field_contracts
from .mbs_workbook_domain import iter_workbook_domain_batches
from .receipts import SourceReceipt

_DATE_FIELDS = frozenset(
    field.native_name
    for field in mbs_field_contracts()
    if field.value_type == "source_date"
)
_DOTTED_DATE = re.compile(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}\Z")


def _calendar_unique_status(value: str) -> str:
    if not _DOTTED_DATE.fullmatch(value):
        return "invalid"
    first, second, year = (int(part) for part in value.split("."))
    candidates: set[date] = set()
    for month, day in ((second, first), (first, second)):
        try:
            candidates.add(date(year, month, day))
        except ValueError:
            continue
    if len(candidates) == 1:
        return "unique_calendar_date"
    if candidates:
        return "ambiguous_calendar_order"
    return "invalid"


def profile_p7_calendar_dates(
    payload: bytes, receipt: SourceReceipt
) -> dict[str, Any]:
    """Count date interpretations without emitting cell values or dates."""
    by_field: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for batch in iter_workbook_domain_batches(payload, receipt):
        for row in batch.to_pylist():
            field_name = row["mapping_field"]
            if row["row_kind"] == "header" or field_name not in _DATE_FIELDS:
                continue
            value = row["display_value"]
            if value is None:
                status = (
                    "null"
                    if "display_value" in row["present_properties"]
                    else "missing_value"
                )
            elif row["cell_type"] == "e":
                status = "source_error"
            elif row["cell_type"] in {None, "n"}:
                status = "unsupported_serial_date"
            else:
                status = _calendar_unique_status(value)
            by_field[field_name][status] += 1
    return {
        "schema_version": 1,
        "rule": "unique_valid_calendar_date_per_value_no_order_selected",
        "source_sha256": receipt.payload.sha256,
        "source_byte_count": receipt.payload.byte_count,
        "date_order_selected": False,
        "source_values_emitted": False,
        "by_field": {
            field: dict(sorted(counts.items()))
            for field, counts in sorted(by_field.items())
        },
    }
