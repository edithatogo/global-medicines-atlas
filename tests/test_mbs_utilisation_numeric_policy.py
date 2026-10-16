"""Synthetic tests for explicit exact numeric representation policies."""

from decimal import Decimal
from typing import Any, cast

import pytest

from global_medicines_atlas.mbs_utilisation_numeric_policy import (
    ExactNumericPolicy,
    NumericTokenError,
    parse_exact_numeric_token,
)


def test_default_policy_parses_exact_decimals_and_preserves_scale() -> None:
    policy = ExactNumericPolicy()

    assert parse_exact_numeric_token("7", policy=policy) == Decimal(7)
    assert parse_exact_numeric_token("10.500", policy=policy) == Decimal(
        "10.500"
    )
    assert parse_exact_numeric_token("-0.00", policy=policy) == Decimal("-0.00")
    assert parse_exact_numeric_token("+.75", policy=policy) == Decimal("0.75")


def test_grouping_is_rejected_until_explicitly_configured() -> None:
    with pytest.raises(NumericTokenError):
        parse_exact_numeric_token("1,234.50", policy=ExactNumericPolicy())


def test_explicit_grouping_policy_preserves_sign_and_decimal_scale() -> None:
    policy = ExactNumericPolicy(grouping_separator=",")

    value = parse_exact_numeric_token("-1,234,567.00", policy=policy)

    assert value == Decimal("-1234567.00")
    assert value.as_tuple().exponent == -2


def test_explicit_alternate_decimal_separator_is_supported() -> None:
    policy = ExactNumericPolicy(decimal_separator=",", grouping_separator=".")

    assert parse_exact_numeric_token("1.234,50", policy=policy) == Decimal(
        "1234.50"
    )


@pytest.mark.parametrize(
    "token",
    [
        "",
        " ",
        " 1",
        "1 ",
        "+",
        "--1",
        "1e3",
        "NaN",
        "Infinity",
        "1.2.3",
        "1,234",
        "12,34",
        "1,234,56",
        "1,000_000",
        ".",
        "1.",
        "\uff11\uff12",
    ],
)
def test_default_policy_rejects_ambiguous_or_non_decimal_tokens(
    token: str,
) -> None:
    with pytest.raises(NumericTokenError) as error:
        parse_exact_numeric_token(token, policy=ExactNumericPolicy())
    assert str(error.value) == "numeric token violates explicit policy"


def test_malformed_explicit_groups_are_rejected() -> None:
    policy = ExactNumericPolicy(grouping_separator=",")

    for token in ("12,34", "1,234,56", "1234,567", "1,,000"):
        with pytest.raises(NumericTokenError):
            parse_exact_numeric_token(token, policy=policy)


def test_signed_values_can_be_disabled_by_explicit_policy() -> None:
    policy = ExactNumericPolicy(allow_signed_values=False)

    for token in ("+1", "-1"):
        with pytest.raises(NumericTokenError):
            parse_exact_numeric_token(token, policy=policy)


def test_policy_rejects_ambiguous_separator_configuration() -> None:
    for kwargs in (
        {"decimal_separator": ";"},
        {"decimal_separator": ",", "grouping_separator": ","},
        {"grouping_separator": " "},
        {"grouping_size": 2},
        {"max_token_chars": 0},
    ):
        with pytest.raises(ValueError, match=r".+"):
            ExactNumericPolicy(**cast("Any", kwargs))


def test_policy_token_bound_is_enforced() -> None:
    policy = ExactNumericPolicy(max_token_chars=3)

    with pytest.raises(NumericTokenError):
        parse_exact_numeric_token("1234", policy=policy)
