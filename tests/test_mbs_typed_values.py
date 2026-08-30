"""Loss-aware scalar conversion before Australian Silver table generation."""

from datetime import date
from decimal import Decimal, localcontext

import pytest
from hypothesis import given
from hypothesis import strategies as st

from global_medicines_atlas.mbs_typed_values import convert_mbs_value


@pytest.mark.parametrize("field", ["ItemNum", "SubItemNum", "Group"])
def test_identifiers_and_codes_are_never_numbers(field: str) -> None:
    result = convert_mbs_value(field, "00012", "value")
    assert result.typed_value == "00012"
    assert result.status == "preserved"
    assert result.native_value == "00012"


@pytest.mark.parametrize(
    ("value", "state", "status"),
    [
        (None, "missing_field", "missing_field"),
        (None, "null", "null"),
        ("", "value", "blank"),
        ("  ", "value", "blank"),
    ],
)
def test_absence_and_blanks_remain_distinct(
    value: str | None,
    state: str,
    status: str,
) -> None:
    result = convert_mbs_value("ScheduleFee", value, state)
    assert result.status == status
    assert result.native_value == value
    assert result.native_state == state
    assert result.typed_value is None
    assert result.currency == "AUD"


def test_decimals_are_exact_and_independent_of_context() -> None:
    value = "123456789012345678901234567890.123456789"
    with localcontext() as context:
        context.prec = 2
        result = convert_mbs_value("ScheduleFee", value, "value")
    assert str(result.typed_value) == value
    assert result.status == "converted"
    assert result.currency == "AUD"
    assert convert_mbs_value("BasicUnits", "1.25", "value").currency is None
    assert convert_mbs_value(
        "EMSNPercentageCap", "85", "value"
    ).typed_value == Decimal(85)


@pytest.mark.parametrize(
    "value",
    [
        "NaN",
        "Infinity",
        "1e2",
        "$42",
        "1,000",
        "\uff11\uff12",
        " 42",
        "42 ",
        "#VALUE!",
    ],
)
def test_invalid_numbers_are_retained_not_coerced(value: str) -> None:
    result = convert_mbs_value("ScheduleFee", value, "value")
    assert result.status == "invalid"
    assert result.typed_value is None
    assert result.native_value == value


def test_dates_require_an_explicit_format_and_never_guess() -> None:
    assert (
        convert_mbs_value("ItemStartDate", "2026-08-30", "value").status
        == "unsupported_format"
    )
    result = convert_mbs_value(
        "ItemStartDate", "2026-08-30", "value", date_format="iso"
    )
    assert result.typed_value == date(2026, 8, 30)
    assert (
        convert_mbs_value(
            "ItemStartDate", "30/08/2026", "value", date_format="iso"
        ).status
        == "invalid"
    )
    assert (
        convert_mbs_value(
            "ItemEndDate", "2026-02-30", "value", date_format="iso"
        ).status
        == "invalid"
    )
    assert (
        convert_mbs_value(
            "ItemStartDate", "20260830", "value", date_format="iso"
        ).status
        == "invalid"
    )


def test_derived_fees_and_text_are_not_evaluated() -> None:
    for value in ("", "  ", "#VALUE!", "85% of item 00123"):
        result = convert_mbs_value("DerivedFee", value, "value")
        assert result.typed_value == value
        assert result.status == "preserved"


@pytest.mark.parametrize(
    ("value", "state"),
    [(None, "value"), ("1", "null"), ("1", "missing_field"), ("1", "unknown")],
)
def test_invalid_state_value_pairs_fail(value: str | None, state: str) -> None:
    with pytest.raises(ValueError, match="state"):
        convert_mbs_value("ItemNum", value, state)


def test_unknown_fields_and_formats_fail_closed() -> None:
    with pytest.raises(ValueError, match="field"):
        convert_mbs_value("Unknown", "1", "value")
    with pytest.raises(ValueError, match="format"):
        convert_mbs_value("ItemStartDate", "1", "value", date_format="guess")


@given(st.integers(min_value=-(10**30), max_value=10**30))
def test_exact_decimal_property(value: int) -> None:
    native = f"{value}.012300"
    result = convert_mbs_value("Benefit75", native, "value")
    assert result.typed_value == Decimal(native)
    assert result.native_value == native
    assert result == convert_mbs_value("Benefit75", native, "value")
