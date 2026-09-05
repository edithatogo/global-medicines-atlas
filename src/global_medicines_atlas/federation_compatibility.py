"""Offline compatibility checks for federated dataset contract snapshots.

The canary compares caller-supplied, already-observed metadata only.  It does
not discover, admit, publish, or infer compatibility with a live dataset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_IMMUTABLE_REVISION = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class CompatibilitySnapshot:
    """Minimum immutable identity and semantic contract for a dataset."""

    dataset: str
    revision: str
    schema_sha256: str
    semantic_dimension: str
    required_fields: frozenset[str]
    successor_dataset: str | None = None


@dataclass(frozen=True)
class CompatibilityResult:
    """Deterministic comparison result; false means callers must not proceed."""

    compatible: bool
    reasons: tuple[str, ...]


def compare_federation_snapshots(
    expected: CompatibilitySnapshot, candidate: CompatibilitySnapshot
) -> CompatibilityResult:
    """Compare two snapshots without treating missing data as negative evidence.

    Revision and successor references are validated before comparison.  A
    mutable revision, malformed digest, or absent successor is an invalid
    canary input and raises rather than becoming a soft incompatibility.
    """
    _validate_snapshot(expected)
    _validate_snapshot(candidate)
    reasons: list[str] = []
    if expected.dataset != candidate.dataset:
        reasons.append("dataset identity drift")
    if expected.revision != candidate.revision:
        reasons.append("revision drift")
    if expected.schema_sha256 != candidate.schema_sha256:
        reasons.append("schema drift")
    if expected.semantic_dimension != candidate.semantic_dimension:
        reasons.append("semantic dimension drift")
    if not expected.required_fields <= candidate.required_fields:
        reasons.append("missing required fields")
    if expected.successor_dataset != candidate.successor_dataset:
        reasons.append("successor link drift")
    return CompatibilityResult(not reasons, tuple(reasons))


def _validate_snapshot(snapshot: CompatibilitySnapshot) -> None:
    if (
        not snapshot.dataset
        or snapshot.dataset != snapshot.dataset.strip()
        or any(char.isspace() for char in snapshot.dataset)
    ):
        raise ValueError("dataset identity must be nonempty")
    if _IMMUTABLE_REVISION.fullmatch(snapshot.revision) is None:
        raise ValueError("immutable revision is required")
    if _DIGEST.fullmatch(snapshot.schema_sha256) is None:
        raise ValueError("schema digest must be lowercase hexadecimal")
    if (
        not snapshot.semantic_dimension
        or snapshot.semantic_dimension != snapshot.semantic_dimension.strip()
        or any(char.isspace() for char in snapshot.semantic_dimension)
    ):
        raise ValueError("semantic dimension must be nonempty")
    if not snapshot.required_fields or any(
        not field or field != field.strip() or any(char.isspace() for char in field)
        for field in snapshot.required_fields
    ):
        raise ValueError("required fields must be nonempty")
    if (
        snapshot.successor_dataset is not None
        and (
            not snapshot.successor_dataset
            or snapshot.successor_dataset != snapshot.successor_dataset.strip()
            or any(char.isspace() for char in snapshot.successor_dataset)
        )
    ):
        raise ValueError("successor link must be explicit and nonempty")
