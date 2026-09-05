"""Offline preparation and readback validation for source metadata appends.

This module cannot upload. A hosted transport must supply a complete verified
baseline and use ``parent_revision`` as the Hub commit's compare-and-swap
precondition. Caller-supplied readback is not independent publication evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from global_medicines_atlas.federation_source_metadata import (
    validate_source_metadata,
)

MAX_PATH = 4096
FIRST_PRINTABLE = 32
MAX_OBJECTS = 10000


@dataclass(frozen=True)
class ObjectDigest:
    """Exact object identity in a complete dataset sibling inventory."""

    path: str
    byte_count: int
    sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.path) is not str
            or not self.path
            or len(self.path) > MAX_PATH
            or any(ord(char) < FIRST_PRINTABLE for char in self.path)
            or any(char in self.path for char in ("%", "\\"))
        ):
            raise ValueError("unsafe object path")
        if (
            self.path != PurePosixPath(self.path).as_posix()
            or PurePosixPath(self.path).is_absolute()
            or ".." in PurePosixPath(self.path).parts
            or self.path == "."
        ):
            raise ValueError("unsafe object path")
        if type(self.byte_count) is not int or self.byte_count < 0:
            raise ValueError("invalid byte count")
        if type(self.sha256) is not str or not re.fullmatch(
            r"[0-9a-f]{64}", self.sha256
        ):
            raise ValueError("invalid SHA-256")


def _inventory(objects: tuple[ObjectDigest, ...]) -> dict[str, ObjectDigest]:
    if type(objects) is not tuple or not 1 <= len(objects) <= MAX_OBJECTS:
        raise ValueError("inventory must be a bounded nonempty tuple")
    result: dict[str, ObjectDigest] = {}
    for obj in objects:
        if type(obj) is not ObjectDigest:
            raise ValueError("inventory requires exact object identities")
        obj.__post_init__()
        if obj.path in result:
            raise ValueError("duplicate inventory path")
        result[obj.path] = obj
    return result


@dataclass(frozen=True)
class MetadataAppend:
    """One metadata addition, its exact parent and preserved baseline."""

    dataset: str
    parent_revision: str
    baseline: tuple[ObjectDigest, ...]
    addition: ObjectDigest
    payload: bytes


def prepare_metadata_append(
    document: dict[str, Any], baseline: tuple[ObjectDigest, ...]
) -> MetadataAppend:
    """Prepare canonical source metadata without network or filesystem I/O.

    The document's revision describes the existing source revision; it must
    not be rewritten to the eventual metadata commit, which is not yet known.
    The baseline must come from a complete independently verified inventory.
    """
    objects = _inventory(baseline)
    if len(objects) == MAX_OBJECTS:
        raise ValueError("inventory has no capacity for metadata addition")
    metadata = validate_source_metadata(document)
    canonical = metadata.model_dump(mode="json")
    payload = (
        json.dumps(canonical, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if len(payload) > 1024 * 1024:
        raise ValueError("metadata exceeds one MiB")
    provenance = metadata.provenance
    required = {item.path: item.sha256 for item in provenance.payloads}
    if provenance.receipt in required:
        raise ValueError("source payload cannot alias its receipt")
    required[provenance.receipt] = provenance.receipt_sha256
    for path, digest in required.items():
        if path not in objects or objects[path].sha256 != digest:
            raise ValueError(
                "baseline does not bind source payload and receipt"
            )
    digest = hashlib.sha256(payload).hexdigest()
    addition = ObjectDigest(
        f"metadata/source/{metadata.source.source_id}/{digest}.json",
        len(payload),
        digest,
    )
    if addition.path in objects:
        raise ValueError("metadata path already exists; append refused")
    return MetadataAppend(
        metadata.dataset,
        metadata.revision,
        tuple(sorted(baseline, key=lambda item: item.path)),
        addition,
        payload,
    )


def verify_metadata_append(
    plan: MetadataAppend,
    *,
    dataset: str,
    parent_revision: str,
    revision: str,
    private: bool,
    gated: bool,
    observed: tuple[ObjectDigest, ...],
    anonymous_payload: bytes,
) -> None:
    """Reject drift, visibility changes, replaced siblings or altered bytes.

    Rebuild the plan to reject caller-forged transaction objects. The hosted
    caller must observe the commit parent and anonymously hash every sibling;
    this offline check does not prove how those observations were obtained.
    """
    if type(plan.payload) is not bytes or len(plan.payload) > 1024 * 1024:
        raise ValueError("invalid metadata payload")
    rebuilt = prepare_metadata_append(json.loads(plan.payload), plan.baseline)
    if rebuilt != plan:
        raise ValueError("transaction differs from validated preparation")
    if dataset != plan.dataset or parent_revision != plan.parent_revision:
        raise ValueError("dataset or commit parent differs from CAS target")
    if (
        type(revision) is not str
        or not re.fullmatch(r"[0-9a-f]{40}", revision)
        or revision == parent_revision
    ):
        raise ValueError("append requires a new immutable revision")
    if private is not False or gated is not False:
        raise ValueError("result must be public and non-gated")
    expected = _inventory((*plan.baseline, plan.addition))
    if _inventory(observed) != expected:
        raise ValueError("complete sibling inventory differs from exact append")
    if (
        type(anonymous_payload) is not bytes
        or anonymous_payload != plan.payload
    ):
        raise ValueError("anonymous metadata bytes differ")
