"""Offline v4 distribution denominator checks, not admission or publication.

The producer supplies its complete output inventory and independently governed
destination topology. Matching self-reported contracts never authenticates
receipts, establishes rights, or creates a reader admission allowlist.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from .federation import validate_federation_semantics
from .federation_reader import METADATA_BYTES, SCHEMA_SHA256


@dataclass(frozen=True)
class ProducedObject:
    """Producer inventory identity; path is the intended portable object path."""

    producer_repository: str
    source_id: str
    acquisition_id: str
    layer: str
    path: str
    sha256: str
    byte_count: int
    evidence_kind: str


@dataclass(frozen=True)
class DistributionBinding:
    """Consistent destination claim, with exact contract bytes identified."""

    object: ProducedObject
    dataset: str
    revision: str
    contract_sha256: str


def reconcile_distribution(
    produced: Sequence[ProducedObject],
    contracts: Sequence[bytes],
    *,
    schema: bytes,
    destinations: Mapping[str, str],
) -> tuple[DistributionBinding, ...]:
    """Require a bijection between producer outputs and primary v4 projections.

    Args:
        produced: Complete caller-owned denominator, not inferred from contracts.
        contracts: Exact v4 JSON bytes, one primary location for every output.
        schema: Unmodified byte-pinned v4 schema.
        destinations: Caller-governed layer-to-public-dataset topology.

    Returns:
        Bindings in producer inventory order; no network or filesystem I/O.

    Raises:
        ValueError: Invalid, missing, extra, duplicate or contradictory evidence.
    """
    if hashlib.sha256(schema).hexdigest() != SCHEMA_SHA256:
        raise ValueError("federation schema digest mismatch")
    if not produced:
        raise ValueError("empty produced inventory")
    if any(type(obj.byte_count) is not int for obj in produced):
        raise ValueError("object byte count must be an integer")
    formats = FormatChecker()
    if not {"date", "date-time", "uri"} <= formats.checkers.keys():
        raise ValueError("required federation format validators are missing")
    validator = Draft202012Validator(json.loads(schema), format_checker=formats)
    expected = {_key(obj): obj for obj in produced}
    if len(expected) != len(produced):
        raise ValueError("duplicate produced object identity")
    found: dict[tuple[str, ...], DistributionBinding] = {}
    locations: set[tuple[str, str, str]] = set()
    for raw in contracts:
        document = _document(raw, validator)
        source = document["source"]
        location = document["location"]
        if (
            source["representation"] != "projection"
            or document["recovery"]["role"] != "primary"
        ):
            raise ValueError(
                "distribution requires primary derived projections"
            )
        if destinations.get(source["layer"]) != location["dataset"]:
            raise ValueError("distribution destination mismatch")
        obj = ProducedObject(
            producer_repository=document["authority"]["producer_repository"],
            source_id=source["source_id"],
            acquisition_id=source["acquisition_id"],
            layer=source["layer"],
            path=location["path"],
            sha256=location["sha256"],
            byte_count=location["bytes"],
            evidence_kind=document["evidence_kind"],
        )
        key = _key(obj)
        remote = (location["dataset"], location["revision"], location["path"])
        if key in found or remote in locations:
            raise ValueError("duplicate distribution identity")
        if expected.get(key) != obj:
            raise ValueError("extra or mismatched distribution object")
        locations.add(remote)
        found[key] = DistributionBinding(
            obj,
            location["dataset"],
            location["revision"],
            hashlib.sha256(raw).hexdigest(),
        )
    if found.keys() != expected.keys():
        raise ValueError("missing distribution object")
    return tuple(found[_key(obj)] for obj in produced)


def _key(obj: ProducedObject) -> tuple[str, ...]:
    return (
        obj.producer_repository,
        obj.source_id,
        obj.acquisition_id,
        obj.layer,
        obj.path,
    )


def _document(raw: bytes, validator: Any) -> dict[str, Any]:
    if len(raw) > METADATA_BYTES:
        raise ValueError("contract exceeds metadata budget")
    try:
        document: dict[str, Any] = json.loads(raw)
        validator.validate(document)
        validate_federation_semantics(document)
    except ValueError, TypeError, KeyError, ValidationError:
        raise ValueError("invalid federation contract") from None
    if document["authority"]["schema_sha256"] != SCHEMA_SHA256:
        raise ValueError("invalid federation contract schema pin")
    return document
