"""Strict JSON helpers for evidence identities that must be unambiguous."""

from __future__ import annotations

from typing import Any


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object and reject repeated member names at every depth."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate contract JSON key")
        result[key] = value
    return result
