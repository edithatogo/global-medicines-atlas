"""Explicit, lossless numeric token parsing policies for MBS candidates.

This module provides a pure parser for synthetic tests and future reviewed
profiles. It does not select policy for a source, transform source rows, admit
records, or publish Silver data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

SUPPORTED_GROUPING_SIZE = 3

_ASCII_DIGITS = re.compile(r"[0-9]+\Z")


class NumericTokenError(ValueError):
    """A token violates its explicit numeric representation policy."""


@dataclass(frozen=True)
class ExactNumericPolicy:
    """An explicit decimal and optional digit-grouping representation."""

    decimal_separator: str = "."
    grouping_separator: str | None = None
    grouping_size: int = 3
    allow_signed_values: bool = True
    max_token_chars: int = 256

    def __post_init__(self) -> None:
        if self.decimal_separator not in {".", ","}:
            raise ValueError("decimal separator policy is unsupported")
        if self.grouping_separator is not None and (
            self.grouping_separator not in {",", "_", "'", "."}
            or self.grouping_separator == self.decimal_separator
        ):
            raise ValueError("grouping separator policy is ambiguous")
        if self.grouping_size != SUPPORTED_GROUPING_SIZE:
            raise ValueError("only three-digit grouping is supported")
        if self.max_token_chars <= 0:
            raise ValueError("numeric token bound must be positive")


def parse_exact_numeric_token(
    token: str, *, policy: ExactNumericPolicy
) -> Decimal:
    """Parse one token without floating point or implicit separator removal.

    The caller must provide a policy. Group separators are rejected unless the
    policy names one, and then only valid three-digit groups are accepted.
    Errors use fixed messages and never include the input token.
    """
    if not token or len(token) > policy.max_token_chars:
        raise NumericTokenError("numeric token violates explicit policy")
    if any(character.isspace() for character in token):
        raise NumericTokenError("numeric token violates explicit policy")

    sign = ""
    unsigned = token
    if unsigned[0] in {"+", "-"}:
        if not policy.allow_signed_values:
            raise NumericTokenError("numeric token violates explicit policy")
        sign, unsigned = unsigned[0], unsigned[1:]
    if not unsigned:
        raise NumericTokenError("numeric token violates explicit policy")

    if unsigned.count(policy.decimal_separator) > 1:
        raise NumericTokenError("numeric token violates explicit policy")
    if policy.decimal_separator in unsigned:
        integer_part, fractional_part = unsigned.split(
            policy.decimal_separator, maxsplit=1
        )
        if not fractional_part or not _ASCII_DIGITS.fullmatch(fractional_part):
            raise NumericTokenError("numeric token violates explicit policy")
    else:
        integer_part, fractional_part = unsigned, None

    normalized_integer = _normalize_integer(integer_part, policy)
    normalized = sign + normalized_integer
    if fractional_part is not None:
        normalized += "." + fractional_part
    return Decimal(normalized)


def _normalize_integer(integer_part: str, policy: ExactNumericPolicy) -> str:
    if not integer_part:
        return "0"
    separator = policy.grouping_separator
    if separator is None or separator not in integer_part:
        if not _ASCII_DIGITS.fullmatch(integer_part):
            raise NumericTokenError("numeric token violates explicit policy")
        return integer_part

    groups = integer_part.split(separator)
    if (
        not 1 <= len(groups[0]) <= policy.grouping_size
        or not _ASCII_DIGITS.fullmatch(groups[0])
        or any(
            len(group) != policy.grouping_size
            or not _ASCII_DIGITS.fullmatch(group)
            for group in groups[1:]
        )
    ):
        raise NumericTokenError("numeric token violates explicit policy")
    return "".join(groups)
