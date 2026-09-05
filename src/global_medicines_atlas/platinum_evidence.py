"""Fail-closed validation for evidence-bearing Platinum result envelopes.

The validator is intentionally structural: it does not infer evidence from
rows, and it does not upgrade conservative states.  It is shared by tests and
future CLI/API adapters so a new result surface cannot silently omit the
metadata required by the Platinum contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
        return value.get(field)
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
        field for field in REQUIRED_EVIDENCE_FIELDS if _read(evidence, field) is None
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
            raise PlatinumEvidenceError(f"result evidence field {field!r} is invalid")
    return result


__all__ = [
    "REQUIRED_EVIDENCE_FIELDS",
    "PlatinumEvidenceError",
    "validate_result_evidence",
]
