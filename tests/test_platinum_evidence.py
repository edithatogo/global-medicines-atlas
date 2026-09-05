"""Acceptance checks for mandatory Platinum result evidence."""

import hashlib
from dataclasses import dataclass

import pytest

from global_medicines_atlas.platinum_evidence import (
    PlatinumEvidenceError,
    aggregate_result_evidence,
    checkpoint_representative_evidence,
    validate_result_evidence,
)


@dataclass(frozen=True)
class _Evidence:
    dataset: str = "owner/dataset"
    revision: str = "a" * 40
    path: str = "platinum/items.parquet"
    object_sha256: str = "a" * 64
    semantic_dimension: str = "funding"
    entity_granularity: str = "medicine_item"
    schema_era: str = "v1"
    comparison_cohort: str = "current"
    effective_date: str | None = "2026-01-01"
    retrieved_at: str = "2026-01-02T00:00:00Z"
    coverage_state: str = "not_declared"
    confidence_state: str = "not_declared"
    uncertainty_state: str = "not_declared"
    review_state: str = "not_declared"
    comparison_validity: str = "not_evaluated"


@dataclass(frozen=True)
class _Result:
    evidence: _Evidence


def test_result_evidence_accepts_complete_conservative_envelope() -> None:
    result = _Result(_Evidence())
    assert validate_result_evidence(result) is result


def test_result_evidence_rejects_missing_claim_bearing_field() -> None:
    result = _Result(_Evidence(confidence_state=""))
    with pytest.raises(PlatinumEvidenceError, match="confidence_state"):
        validate_result_evidence(result)


def test_identity_shaped_envelope_can_be_validated_without_nested_evidence() -> None:
    assert validate_result_evidence(_Evidence())


def test_result_evidence_aggregate_is_payload_free_and_order_independent() -> None:
    first = _Result(_Evidence(path="benefits.parquet"))
    second = _Result(_Evidence(path="history.parquet"))
    left = aggregate_result_evidence((first, second))
    right = aggregate_result_evidence((second, first))

    assert left == right
    assert left.result_count == 2
    assert left.resource_ids == (
        "owner/dataset:benefits.parquet",
        "owner/dataset:history.parquet",
    )
    assert b"rows" not in left.canonical_bytes
    assert len(left.receipt_sha256) == 64


def test_result_evidence_aggregate_rejects_empty_and_duplicate_resources() -> None:
    with pytest.raises(PlatinumEvidenceError, match="cannot be empty"):
        aggregate_result_evidence(())
    duplicate = _Result(_Evidence())
    with pytest.raises(PlatinumEvidenceError, match="duplicated"):
        aggregate_result_evidence((duplicate, duplicate))


def test_representative_checkpoint_records_only_observed_dimensions() -> None:
    results = (
        _Result(_Evidence(path="benefits.parquet", semantic_dimension="funding")),
        _Result(_Evidence(path="history.parquet", semantic_dimension="service_benefit")),
    )
    checkpoint = checkpoint_representative_evidence(
        results, required_dimensions=("funding", "service_benefit")
    )

    assert checkpoint.result_count == 2
    assert checkpoint.semantic_dimensions == ("funding", "service_benefit")
    assert checkpoint.resource_ids == (
        "owner/dataset:benefits.parquet",
        "owner/dataset:history.parquet",
    )
    assert b"rows" not in checkpoint.canonical_bytes
    assert checkpoint.receipt_sha256 == hashlib.sha256(
        checkpoint.canonical_bytes
    ).hexdigest()


def test_representative_checkpoint_does_not_infer_unobserved_dimensions() -> None:
    with pytest.raises(PlatinumEvidenceError, match="required dimensions"):
        checkpoint_representative_evidence(
            (_Result(_Evidence()),), required_dimensions=("regulatory",)
        )
