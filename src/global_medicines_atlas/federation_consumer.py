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
from typing import Any

from .federation_reader import SCHEMA_SHA256

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
    dataset: str
    revision: str
    path: str
    object_sha256: str
    layer: str
    source_id: str
    acquisition_id: str
    successor: SuccessorLink | None


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
    _repo(consumer_repository, "consumer repository")
    _commit_value(consumer_commit, "consumer commit")
    digest = hashlib.sha256(contract).hexdigest()
    try:
        document: dict[str, Any] = json.loads(contract)
        authority = document["authority"]
        source = document["source"]
        location = document["location"]
    except json.JSONDecodeError, KeyError, TypeError:
        raise ValueError("invalid consumer contract") from None
    if authority.get("schema_sha256") != SCHEMA_SHA256:
        raise ValueError("consumer contract schema pin mismatch")
    producer = authority.get("producer_repository")
    _repo(producer, "producer repository")
    for field in ("dataset", "revision", "path", "sha256"):
        if location.get(field) != document.get("verification", {}).get(field):
            raise ValueError("consumer contract identity mismatch")
    _repo(location.get("dataset"), "dataset identity")
    _commit_value(location.get("revision"), "dataset revision")
    _digest_value(location.get("sha256"), "object digest")
    if successor is not None:
        _validate_successor(successor, producer)
    return ConsumerBinding(
        consumer_repository=consumer_repository,
        consumer_commit=consumer_commit,
        contract_sha256=digest,
        producer_repository=producer,
        dataset=location["dataset"],
        revision=location["revision"],
        path=location["path"],
        object_sha256=location["sha256"],
        layer=source["layer"],
        source_id=source["source_id"],
        acquisition_id=source["acquisition_id"],
        successor=successor,
    )


def _validate_successor(link: SuccessorLink, producer: str) -> None:
    _repo(link.legacy_repository, "legacy repository")
    _repo(link.successor_repository, "successor repository")
    _commit_value(link.successor_commit, "successor commit")
    _digest_value(link.notice_digest, "successor notice digest")
    if link.successor_repository == producer:
        raise ValueError("successor link cannot replace producer authority")
    if link.legacy_repository == link.successor_repository:
        raise ValueError("successor link must change repository")


def _repo(value: Any, label: str) -> None:
    if not isinstance(value, str) or _REPOSITORY.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")


def _commit_value(value: Any, label: str) -> None:
    if not isinstance(value, str) or _COMMIT.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")


def _digest_value(value: Any, label: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
