"""Dependency-light compatibility bindings for federated consumers.

The adapter translates an already schema-validated v4 contract into a
consumer-facing identity.  It never admits a contract, reads bytes, follows a
successor, or creates a second authority.  Successor links are explicit
metadata supplied by the caller and are checked for exact, immutable pins.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal, cast

from .federation_reader import SCHEMA_SHA256
from .strict_json import unique_json_object

_REPOSITORY = re.compile(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class SuccessorLink:
    """Pinned public successor for a legacy consumer or donor surface."""

    legacy_repository: str
    successor_repository: str
    successor_commit: str
    notice_digest: str


@dataclass(frozen=True)
class ConsumerBinding:
    """Exact contract identity consumable by a downstream repository."""

    consumer_repository: str
    consumer_commit: str
    contract_sha256: str
    producer_repository: str
    contract_repository: str
    contract_commit: str
    schema_sha256: str
    evidence_kind: Literal["synthetic", "live"]
    dataset: str
    revision: str
    path: str
    object_sha256: str
    byte_count: int
    layer: Literal["bronze", "silver", "gold", "platinum"]
    bronze_stratum: Literal["B0", "B1", "B2"] | None
    representation: Literal["index", "metadata", "raw", "projection"]
    source_id: str
    acquisition_id: str
    schema_era: str
    comparison_cohort: Literal["legacy", "current", "synthetic"]
    effective_date: str | None
    retrieved_at: str
    successor: SuccessorLink | None


@dataclass(frozen=True)
class _ValidatedIdentity:
    producer: str
    contract_repository: str
    contract_commit: str
    evidence_kind: Literal["synthetic", "live"]
    dataset: str
    revision: str
    path: str
    object_sha256: str
    byte_count: int
    layer: Literal["bronze", "silver", "gold", "platinum"]
    bronze_stratum: Literal["B0", "B1", "B2"] | None
    representation: Literal["index", "metadata", "raw", "projection"]
    source_id: str
    acquisition_id: str
    schema_era: str
    comparison_cohort: Literal["legacy", "current", "synthetic"]
    effective_date: str | None
    retrieved_at: str


def bind_consumer_contract(
    contract: bytes,
    *,
    consumer_repository: str,
    consumer_commit: str,
    successor: SuccessorLink | None = None,
) -> ConsumerBinding:
    """Create a pinned consumer binding from an exact v4 contract.

    This is deliberately not a validator or admission engine: callers must
    perform schema, rights, receipt, and source verification independently.
    The adapter only rejects malformed identity claims and prevents a
    successor link from replacing the producer authority.
    """
    consumer_repository = _repo(consumer_repository, "consumer repository")
    consumer_commit = _commit_value(consumer_commit, "consumer commit")
    document = _parse_document(contract)
    identity = _validated_identity(document)
    if successor is not None:
        _validate_successor(successor, identity.producer)
    return ConsumerBinding(
        consumer_repository=consumer_repository,
        consumer_commit=consumer_commit,
        contract_sha256=hashlib.sha256(contract).hexdigest(),
        producer_repository=identity.producer,
        contract_repository=identity.contract_repository,
        contract_commit=identity.contract_commit,
        schema_sha256=SCHEMA_SHA256,
        evidence_kind=identity.evidence_kind,
        dataset=identity.dataset,
        revision=identity.revision,
        path=identity.path,
        object_sha256=identity.object_sha256,
        byte_count=identity.byte_count,
        layer=identity.layer,
        bronze_stratum=identity.bronze_stratum,
        representation=identity.representation,
        source_id=identity.source_id,
        acquisition_id=identity.acquisition_id,
        schema_era=identity.schema_era,
        comparison_cohort=identity.comparison_cohort,
        effective_date=identity.effective_date,
        retrieved_at=identity.retrieved_at,
        successor=successor,
    )


def _parse_document(contract: bytes) -> dict[str, Any]:
    try:
        parsed: Any = json.loads(contract, object_pairs_hook=unique_json_object)
    except ValueError, TypeError:
        raise ValueError("invalid consumer contract") from None
    if type(parsed) is not dict:
        raise ValueError("consumer contract must be a JSON object")
    return cast("dict[str, Any]", parsed)


def _object_section(document: dict[str, Any], key: str) -> dict[str, Any]:
    section = document.get(key)
    if type(section) is not dict:
        raise ValueError(f"consumer contract {key} section must be an object")
    return cast("dict[str, Any]", section)


def _validated_identity(document: dict[str, Any]) -> _ValidatedIdentity:
    authority = _object_section(document, "authority")
    source = _object_section(document, "source")
    location = _object_section(document, "location")
    verification = _object_section(document, "verification")
    producer, contract_repository, contract_commit = _validate_authority(
        authority
    )
    object_identity = _validate_object(location, verification)
    source_identity = _validate_source(source)
    evidence_kind = document.get("evidence_kind")
    if not isinstance(evidence_kind, str) or evidence_kind not in {
        "synthetic",
        "live",
    }:
        raise ValueError("consumer contract evidence kind is invalid")
    return _ValidatedIdentity(
        producer=producer,
        contract_repository=contract_repository,
        contract_commit=contract_commit,
        evidence_kind=cast("Literal['synthetic', 'live']", evidence_kind),
        **object_identity,
        **source_identity,
    )


def _validate_authority(authority: dict[str, Any]) -> tuple[str, str, str]:
    if authority.get("schema_sha256") != SCHEMA_SHA256:
        raise ValueError("consumer contract schema pin mismatch")
    producer = _repo(
        authority.get("producer_repository"), "producer repository"
    )
    contract_repository = _repo(
        authority.get("contract_repository"), "contract repository"
    )
    contract_commit = _commit_value(
        authority.get("contract_commit"), "contract commit"
    )
    return producer, contract_repository, contract_commit


def _validate_object(
    location: dict[str, Any], verification: dict[str, Any]
) -> dict[str, Any]:
    for field in ("dataset", "revision", "path", "sha256", "bytes"):
        if location.get(field) != verification.get(field):
            raise ValueError("consumer contract identity mismatch")
    if (
        location.get("private") is not False
        or location.get("gated") is not False
    ):
        raise ValueError("consumer object must be public and non-gated")
    dataset = _repo(location.get("dataset"), "dataset identity")
    revision = _commit_value(location.get("revision"), "dataset revision")
    object_sha256 = _digest_value(location.get("sha256"), "object digest")
    path = location.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("consumer object path is invalid")
    byte_count = location.get("bytes")
    if type(byte_count) is not int or byte_count < 0:
        raise ValueError("consumer object byte count is invalid")
    return {
        "dataset": dataset,
        "revision": revision,
        "path": path,
        "object_sha256": object_sha256,
        "byte_count": byte_count,
    }


def _validate_source(source: dict[str, Any]) -> dict[str, Any]:
    for field in ("source_id", "acquisition_id", "schema_era"):
        value = source.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("consumer source identity is invalid")
    layer = source.get("layer")
    if not isinstance(layer, str) or layer not in {
        "bronze",
        "silver",
        "gold",
        "platinum",
    }:
        raise ValueError("consumer source layer is invalid")
    bronze_stratum = source.get("bronze_stratum")
    if bronze_stratum is not None and (
        not isinstance(bronze_stratum, str)
        or bronze_stratum not in {"B0", "B1", "B2"}
    ):
        raise ValueError("consumer Bronze stratum is invalid")
    representation = source.get("representation")
    if not isinstance(representation, str) or representation not in {
        "index",
        "metadata",
        "raw",
        "projection",
    }:
        raise ValueError("consumer source representation is invalid")
    cohort = source.get("comparison_cohort")
    if not isinstance(cohort, str) or cohort not in {
        "legacy",
        "current",
        "synthetic",
    }:
        raise ValueError("consumer comparison cohort is invalid")
    effective_date = source.get("effective_date")
    if effective_date is not None and not isinstance(effective_date, str):
        raise ValueError("consumer effective date is invalid")
    retrieved_at = source.get("retrieved_at")
    if not isinstance(retrieved_at, str) or not retrieved_at.strip():
        raise ValueError("consumer retrieval time is invalid")
    return {
        "layer": cast("Literal['bronze', 'silver', 'gold', 'platinum']", layer),
        "bronze_stratum": cast(
            "Literal['B0', 'B1', 'B2'] | None", bronze_stratum
        ),
        "representation": cast(
            "Literal['index', 'metadata', 'raw', 'projection']", representation
        ),
        "source_id": source["source_id"],
        "acquisition_id": source["acquisition_id"],
        "schema_era": source["schema_era"],
        "comparison_cohort": cast(
            "Literal['legacy', 'current', 'synthetic']", cohort
        ),
        "effective_date": effective_date,
        "retrieved_at": retrieved_at,
    }


def _validate_successor(link: SuccessorLink, producer: str) -> None:
    _repo(link.legacy_repository, "legacy repository")
    _repo(link.successor_repository, "successor repository")
    _commit_value(link.successor_commit, "successor commit")
    _digest_value(link.notice_digest, "successor notice digest")
    if link.successor_repository == producer:
        raise ValueError("successor link cannot replace producer authority")
    if link.legacy_repository == link.successor_repository:
        raise ValueError("successor link must change repository")


def _repo(value: Any, label: str) -> str:
    if not isinstance(value, str) or _REPOSITORY.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


def _commit_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or _COMMIT.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


def _digest_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value
