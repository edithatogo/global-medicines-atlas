"""Lossless native-record adapters for expansion fixtures.

These parsers do not harmonise medicine identity, infer causality, or
project Silver/Gold status. They preserve source-native identifiers.
"""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO

import orjson

from ..source_expansion import binding_for

MAX_NATIVE_PAYLOAD_BYTES = 1_000_000


def parse_native_records(
    source_id: str,
    payload: bytes,
    *,
    media_hint: str | None = None,
) -> tuple[dict[str, str], ...]:
    """Parse source-faithful records without identity harmonisation."""

    binding_for(source_id)
    if len(payload) > MAX_NATIVE_PAYLOAD_BYTES:
        raise ValueError(f"{source_id} fixture exceeds native payload bound")
    hint = (media_hint or "").lower()
    if hint.endswith("json") or payload[:1] in {b"{", b"["}:
        return _json_records(payload)
    return _csv_records(payload)


def _csv_records(payload: bytes) -> tuple[dict[str, str], ...]:
    text = payload.decode("utf-8")
    return tuple(
        {key: value for key, value in row.items() if key is not None}
        for row in csv.DictReader(StringIO(text))
    )


def _json_records(payload: bytes) -> tuple[dict[str, str], ...]:
    loaded: object = orjson.loads(payload)
    if isinstance(loaded, dict):
        mapping = {str(key): value for key, value in loaded.items()}
        nested: object = mapping.get("results", mapping.get("records"))
        loaded = [mapping] if nested is None else nested
    if not isinstance(loaded, list):
        raise TypeError("JSON fixture must be a list of objects")
    records: list[dict[str, str]] = []
    for item in loaded:
        if not isinstance(item, Mapping):
            raise TypeError("JSON records must be objects")
        records.append({str(key): str(value) for key, value in item.items()})
    return tuple(records)
