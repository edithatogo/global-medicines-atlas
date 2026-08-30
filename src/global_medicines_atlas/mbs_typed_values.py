"""Loss-aware MBS scalar conversion; not table promotion or source lineage."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from .australian_source_contracts import ValueType, mbs_field_contracts

ConversionStatus = Literal[
    "missing_field",
    "null",
    "blank",
    "preserved",
    "converted",
    "invalid",
    "unsupported_format",
]
TypedValue = str | Decimal | date | None
_FIELDS = {field.native_name: field for field in mbs_field_contracts()}
_DECIMAL = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


@dataclass(frozen=True)
class MbsTypedValue:
    """Conversion result retaining native text and absence independently."""

    native_name: str
    native_value: str | None
    native_state: str
    typed_value: TypedValue
    status: ConversionStatus
    currency: Literal["AUD"] | None
    date_format: str | None
    conversion_version: Literal["mbs-scalar-v1"] = "mbs-scalar-v1"


def convert_mbs_value(
    native_name: str,
    value: str | None,
    state: str,
    *,
    date_format: str | None = None,
) -> MbsTypedValue:
    """Convert one known field without rounding, guessing dates or evaluation.

    Args:
        native_name: Field in the versioned MBS native-field denominator.
        value: Unmodified native text, or None for missing/null fields.
        state: Explicit native presence state, independent of conversion.
        date_format: None leaves dates unconverted; 'iso' explicitly selects
            the strict YYYY-MM-DD profile. Callers must bind this choice to
            their source era; this function makes no production-era claim.

    Returns:
        An immutable result. Decimal precision is unlimited here; Arrow
        writers must separately check representability without rounding.
        Percentages retain their source magnitude, not a divided fraction.

    Raises:
        ValueError: Unknown field/profile or contradictory presence state.
    """
    if native_name not in _FIELDS:
        raise ValueError("unknown MBS native field")
    if date_format not in {None, "iso"}:
        raise ValueError("unsupported date format profile")
    if (
        state not in {"missing_field", "null", "value"}
        or ((state == "value") != isinstance(value, str))
        or (state != "value" and value is not None)
    ):
        raise ValueError("native value and state disagree")
    field = _FIELDS[native_name]
    currency: Literal["AUD"] | None = (
        "AUD" if field.value_type == "aud_decimal" else None
    )
    typed: TypedValue = None
    status: ConversionStatus
    if value is None:
        status = "missing_field" if state == "missing_field" else "null"
    else:
        typed, status = _convert_present(value, field.value_type, date_format)
    return MbsTypedValue(
        native_name=native_name,
        native_value=value,
        native_state=state,
        typed_value=typed,
        status=status,
        currency=currency,
        date_format=date_format,
    )


def _convert_present(
    value: str,
    value_type: ValueType,
    date_format: str | None,
) -> tuple[TypedValue, ConversionStatus]:
    typed: TypedValue = None
    status: ConversionStatus
    if value_type in {"identifier", "source_code", "source_text"}:
        typed, status = value, "preserved"
    elif not value.strip():
        status = "blank"
    elif value_type == "source_date":
        if date_format is None:
            status = "unsupported_format"
        elif not _ISO_DATE.fullmatch(value):
            status = "invalid"
        else:
            try:
                typed, status = date.fromisoformat(value), "converted"
            except ValueError:
                status = "invalid"
    elif _DECIMAL.fullmatch(value):
        typed, status = Decimal(value), "converted"
    else:
        status = "invalid"
    return typed, status
