"""Offline v4 distribution denominator checks, not admission or publication.

The producer supplies its complete output inventory and independently governed
destination topology. Matching self-reported contracts never authenticates
receipts, establishes rights, or creates a reader admission allowlist.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from pydantic import (
    ConfigDict,
    Field,
    model_validator,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)

from .federation import validate_federation_semantics
from .federation_reader import METADATA_BYTES, SCHEMA_SHA256
from .models import FrozenModel
from .strict_json import unique_json_object

_REPOSITORY = re.compile(r"[^/\s]+/[^/\s]+")


@dataclass(frozen=True)
class ProducedObject:
    """Producer inventory identity; path is the intended portable object path."""

    producer_repository: str
    source_id: str
    acquisition_id: str
    layer: str
    bronze_stratum: str | None
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


class _SyntheticInventoryObject(FrozenModel):
    """One synthetic object row from the complete producer fixture."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_id: str = Field(min_length=1, max_length=2048)
    acquisition_id: str = Field(min_length=1, max_length=2048)
    layer: Literal["bronze", "silver", "gold", "platinum"]
    bronze_stratum: Literal["B0", "B1", "B2"] | None
    path: str = Field(min_length=1, max_length=2048)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def validate_layer_and_path(self) -> _SyntheticInventoryObject:
        if (self.layer == "bronze") != (self.bronze_stratum is not None):
            raise ValueError("Bronze stratum must exist only for Bronze")
        parts = self.path.split("/")
        if (
            not self.path.startswith(f"{self.layer}/")
            or "\\" in self.path
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ValueError("producer object path is invalid")
        return self


class _SyntheticInventoryDocument(FrozenModel):
    """Strict local-only shape of the synthetic producer denominator."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_id: Literal["global-medicines-atlas.synthetic-producer-inventory"]
    schema_version: Literal[1]
    producer_repository: str = Field(min_length=1, max_length=512)
    dataset: str = Field(min_length=1, max_length=512)
    evidence_kind: Literal["synthetic"]
    publishable: Literal[False]
    objects: tuple[_SyntheticInventoryObject, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identities(self) -> _SyntheticInventoryDocument:
        if (
            _REPOSITORY.fullmatch(self.producer_repository) is None
            or _REPOSITORY.fullmatch(self.dataset) is None
        ):
            raise ValueError("producer repository or dataset is invalid")
        keys = {
            (
                obj.source_id,
                obj.acquisition_id,
                obj.layer,
                obj.path,
            )
            for obj in self.objects
        }
        if len(keys) != len(self.objects):
            raise ValueError("duplicate producer object identity")
        paths = {obj.path for obj in self.objects}
        if len(paths) != len(self.objects):
            raise ValueError("duplicate producer object path")
        return self


@dataclass(frozen=True)
class SyntheticProducerInventory:
    """Complete non-publishable synthetic producer denominator."""

    producer_repository: str
    dataset: str
    objects: tuple[ProducedObject, ...]
    publishable: Literal[False] = False


def load_synthetic_producer_inventory(raw: bytes) -> SyntheticProducerInventory:
    """Parse the bounded, strict synthetic producer inventory without I/O."""
    if type(raw) is not bytes or not raw or len(raw) > METADATA_BYTES:
        raise ValueError("synthetic producer inventory exceeds metadata budget")
    try:
        value: Any = json.loads(raw, object_pairs_hook=unique_json_object)
    except ValueError, TypeError:
        raise ValueError("invalid synthetic producer inventory") from None
    if isinstance(value, dict):
        document_value = cast("dict[str, Any]", value)
        objects = document_value.get("objects")
        if isinstance(objects, list):
            object_rows = cast("list[Any]", objects)
            value = cast(
                "Any", {**document_value, "objects": tuple(object_rows)}
            )
    try:
        document = _SyntheticInventoryDocument.model_validate(value)
    except PydanticValidationError:
        raise ValueError("invalid synthetic producer inventory") from None
    objects = tuple(
        ProducedObject(
            producer_repository=document.producer_repository,
            source_id=item.source_id,
            acquisition_id=item.acquisition_id,
            layer=item.layer,
            bronze_stratum=item.bronze_stratum,
            path=item.path,
            sha256=item.sha256,
            byte_count=item.byte_count,
            evidence_kind=document.evidence_kind,
        )
        for item in document.objects
    )
    return SyntheticProducerInventory(
        producer_repository=document.producer_repository,
        dataset=document.dataset,
        objects=objects,
    )


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
            bronze_stratum=source["bronze_stratum"],
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
        document: dict[str, Any] = json.loads(
            raw, object_pairs_hook=unique_json_object
        )
        validator.validate(document)
        validate_federation_semantics(document)
    except ValueError, TypeError, KeyError, ValidationError:
        raise ValueError("invalid federation contract") from None
    if document["authority"]["schema_sha256"] != SCHEMA_SHA256:
        raise ValueError("invalid federation contract schema pin")
    return document
