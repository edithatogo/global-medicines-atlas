"""Fail-closed validation for evidence-bearing Platinum result envelopes.

The validator is intentionally structural: it does not infer evidence from
rows, and it does not upgrade conservative states.  It is shared by tests and
future CLI/API adapters so a new result surface cannot silently omit the
metadata required by the Platinum contract.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, cast

REQUIRED_EVIDENCE_FIELDS = (
    "dataset",
    "revision",
    "path",
    "object_sha256",
    "semantic_dimension",
    "entity_granularity",
    "schema_era",
    "comparison_cohort",
    "effective_date",
    "retrieved_at",
    "coverage_state",
    "confidence_state",
    "uncertainty_state",
    "review_state",
    "comparison_validity",
)


class PlatinumEvidenceError(ValueError):
    """Raised when a result does not expose a complete evidence envelope."""


def _read(value: object, field: str) -> Any:
    if isinstance(value, Mapping):
        return cast("Mapping[str, Any]", value).get(field)
    return getattr(value, field, None)


def validate_result_evidence(result: object) -> object:
    """Validate mandatory evidence metadata and return ``result`` unchanged.

    Query results carry metadata in ``result.evidence``; identity envelopes
    are themselves evidence envelopes.  Other objects must opt in explicitly
    by exposing an ``evidence`` member.  All fields must be present, and the
    conservative state fields may not be blank or ``None``.
    """
    evidence = _read(result, "evidence") or result
    missing = tuple(
        field
        for field in REQUIRED_EVIDENCE_FIELDS
        if _read(evidence, field) is None
    )
    if missing:
        raise PlatinumEvidenceError(
            "result evidence is missing mandatory fields: " + ", ".join(missing)
        )
    for field in (
        "coverage_state",
        "confidence_state",
        "uncertainty_state",
        "review_state",
        "comparison_validity",
    ):
        value = _read(evidence, field)
        if not isinstance(value, str) or not value.strip():
            raise PlatinumEvidenceError(
                f"result evidence field {field!r} is invalid"
            )
    return result


@dataclass(frozen=True)
class ResultEvidenceAggregate:
    """Payload-free, deterministic evidence checkpoint for result batches."""

    result_count: int
    resource_ids: tuple[str, ...]
    evidence_sha256: str

    @property
    def canonical_bytes(self) -> bytes:
        """Return the canonical checkpoint without rows or result payloads."""
        return json.dumps(
            {
                "evidence_sha256": self.evidence_sha256,
                "resource_ids": self.resource_ids,
                "result_count": self.result_count,
                "version": "1.0",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    @property
    def receipt_sha256(self) -> str:
        """Return the content address of the checkpoint."""
        return hashlib.sha256(self.canonical_bytes).hexdigest()


@dataclass(frozen=True)
class RepresentativeEvidenceCheckpoint:
    """Payload-free checkpoint for a representative result cohort.

    This records only dimensions actually observed in the supplied results;
    it never turns a missing dimension into negative evidence.
    """

    result_count: int
    semantic_dimensions: tuple[str, ...]
    resource_ids: tuple[str, ...]
    evidence_sha256: str

    @property
    def canonical_bytes(self) -> bytes:
        """Serialize the representative checkpoint deterministically."""
        return json.dumps(
            {
                "evidence_sha256": self.evidence_sha256,
                "resource_ids": self.resource_ids,
                "result_count": self.result_count,
                "semantic_dimensions": self.semantic_dimensions,
                "version": "1.0",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    @property
    def receipt_sha256(self) -> str:
        """Return the content address of the representative checkpoint."""
        return hashlib.sha256(self.canonical_bytes).hexdigest()


def aggregate_result_evidence(
    results: Iterable[object],
) -> ResultEvidenceAggregate:
    """Validate and aggregate result evidence without retaining result data.

    The aggregate is suitable for a read-only Phase 2 checkpoint.  It binds
    each result's mandatory evidence and resource identity, rejects duplicate
    identities, and never serializes rows or other claim-bearing payloads.
    """
    documents: list[dict[str, object]] = []
    resource_ids: list[str] = []
    for result in results:
        validate_result_evidence(result)
        evidence = _read(result, "evidence") or result
        document = {
            field: _read(evidence, field) for field in REQUIRED_EVIDENCE_FIELDS
        }
        resource_id = _read(evidence, "resource_id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            resource_id = f"{document['dataset']}:{document['path']}"
        if resource_id in resource_ids:
            raise PlatinumEvidenceError(
                f"result evidence resource identity is duplicated: {resource_id}"
            )
        resource_ids.append(resource_id)
        documents.append(document)
    if not documents:
        raise PlatinumEvidenceError("result evidence aggregate cannot be empty")
    canonical = json.dumps(
        sorted(
            documents,
            key=lambda item: tuple(
                str(item[field]) for field in REQUIRED_EVIDENCE_FIELDS
            ),
        ),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return ResultEvidenceAggregate(
        result_count=len(documents),
        resource_ids=tuple(sorted(resource_ids)),
        evidence_sha256=hashlib.sha256(canonical).hexdigest(),
    )


def checkpoint_representative_evidence(
    results: Iterable[object],
    *,
    required_dimensions: Iterable[str] = (),
) -> RepresentativeEvidenceCheckpoint:
    """Validate a representative cohort and record observed dimensions.

    Every result must pass the mandatory evidence validator.  Required
    dimensions are an explicit caller contract; dimensions not supplied are
    reported as unobserved rather than inferred absent.
    """
    materialized = tuple(results)
    aggregate = aggregate_result_evidence(materialized)
    observed = {
        str(_read(_read(result, "evidence") or result, "semantic_dimension"))
        for result in materialized
    }
    required = {item for item in required_dimensions if item}
    missing = sorted(required - observed)
    if missing:
        raise PlatinumEvidenceError(
            "representative evidence is missing required dimensions: "
            + ", ".join(missing)
        )
    return RepresentativeEvidenceCheckpoint(
        result_count=aggregate.result_count,
        semantic_dimensions=tuple(sorted(observed)),
        resource_ids=aggregate.resource_ids,
        evidence_sha256=aggregate.evidence_sha256,
    )


__all__ = [
    "REQUIRED_EVIDENCE_FIELDS",
    "PlatinumEvidenceError",
    "RepresentativeEvidenceCheckpoint",
    "ResultEvidenceAggregate",
    "aggregate_result_evidence",
    "checkpoint_representative_evidence",
    "validate_result_evidence",
]
