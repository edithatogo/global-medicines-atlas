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
_MBS_DMY_DATE = re.compile(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}\Z")
DATE_FORMATS = frozenset({"iso", "mbs-dmy"})
CONVERSION_VERSION: Literal["mbs-scalar-v2"] = "mbs-scalar-v2"


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
    conversion_version: Literal["mbs-scalar-v2"] = CONVERSION_VERSION


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
            strict YYYY-MM-DD; 'mbs-dmy' selects the officially documented
            DD.MM.YYYY XML profile. Callers must bind the explicit choice to
            their source era; parsing is not real-corpus qualification.

    Returns:
        An immutable result. Decimal precision is unlimited here; Arrow
        writers must separately check representability without rounding.
        Percentages retain their source magnitude, not a divided fraction.

    Raises:
        ValueError: Unknown field/profile or contradictory presence state.
    """
    if native_name not in _FIELDS:
        raise ValueError("unknown MBS native field")
    if date_format is not None and date_format not in DATE_FORMATS:
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
        typed, status = _convert_date(value, date_format)
    elif _DECIMAL.fullmatch(value):
        typed, status = Decimal(value), "converted"
    else:
        status = "invalid"
    return typed, status


def _convert_date(
    value: str,
    date_format: str | None,
) -> tuple[date | None, ConversionStatus]:
    if date_format is None:
        return None, "unsupported_format"
    pattern = _ISO_DATE if date_format == "iso" else _MBS_DMY_DATE
    if not pattern.fullmatch(value):
        return None, "invalid"
    try:
        if date_format == "iso":
            return date.fromisoformat(value), "converted"
        day, month, year = value.split(".")
        return date(int(year), int(month), int(day)), "converted"
    except ValueError:
        return None, "invalid"
