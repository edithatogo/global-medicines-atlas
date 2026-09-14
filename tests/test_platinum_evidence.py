"""Acceptance checks for mandatory Platinum result evidence."""

import hashlib
from dataclasses import dataclass

import pytest

from global_medicines_atlas.platinum_benefits import BenefitsPage
from global_medicines_atlas.platinum_evidence import (
    PlatinumEvidenceError,
    aggregate_result_evidence,
    checkpoint_representative_evidence,
    validate_result_evidence,
)
from global_medicines_atlas.platinum_identity_service import DatasetIdentityPage
from global_medicines_atlas.platinum_surface_contracts import (
    DatasetIdentityEnvelope,
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


def _identity() -> DatasetIdentityEnvelope:
    return DatasetIdentityEnvelope(
        resource_id="au.mbs.services.current",
        dataset="owner/dataset",
        revision="a" * 40,
        path="platinum/items.parquet",
        object_sha256="b" * 64,
        byte_count=1,
        contract_sha256="c" * 64,
        semantic_manifest_sha256="d" * 64,
        jurisdiction="AU",
        semantic_dimension="service_benefit",
        entity_granularity="service_item",
        source_id="au-mbs",
        acquisition_id="acq-1",
        layer="gold",
        schema_era="v1",
        comparison_cohort="current",
        effective_date="2026-01-01",
        retrieved_at="2026-01-02T00:00:00Z",
        cache_expires_at="2026-01-03T00:00:00Z",
        capabilities=("exact_v4_resolution",),
        coverage_state="not_declared",
        comparison_validity="not_evaluated",
        product_admitted=True,
        rows_queried=False,
    )


def test_actual_identity_and_benefits_page_share_complete_evidence() -> None:
    identity = _identity()
    page = BenefitsPage(
        status="available",
        query_sha256="e" * 64,
        identity=identity,
        rows=(),
        window_sha256="f" * 64,
        page_sha256="0" * 64,
        receipt_sha256="1" * 64,
        reason=None,
        next_cursor=None,
        window_rows=0,
        window_complete=True,
    )

    assert validate_result_evidence(identity) is identity
    assert validate_result_evidence(page) is page
    identities = DatasetIdentityPage(datasets=(identity,), returned=1)
    assert validate_result_evidence(identities) is identities


def test_dataset_collection_rejects_bypassed_untyped_members() -> None:
    malformed = DatasetIdentityPage.model_construct(
        datasets=[_identity()], returned=1
    )

    with pytest.raises(PlatinumEvidenceError, match="typed tuple"):
        validate_result_evidence(malformed)


def test_result_evidence_accepts_complete_conservative_envelope() -> None:
    result = _Result(_Evidence())
    assert validate_result_evidence(result) is result


def test_result_evidence_rejects_missing_claim_bearing_field() -> None:
    result = _Result(_Evidence(confidence_state=""))
    with pytest.raises(PlatinumEvidenceError, match="confidence_state"):
        validate_result_evidence(result)


def test_identity_shaped_envelope_can_be_validated_without_nested_evidence() -> (
    None
):
    assert validate_result_evidence(_Evidence())


def test_result_evidence_aggregate_is_payload_free_and_order_independent() -> (
    None
):
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


def test_result_evidence_aggregate_rejects_empty_and_duplicate_resources() -> (
    None
):
    with pytest.raises(PlatinumEvidenceError, match="cannot be empty"):
        aggregate_result_evidence(())
    duplicate = _Result(_Evidence())
    with pytest.raises(PlatinumEvidenceError, match="duplicated"):
        aggregate_result_evidence((duplicate, duplicate))


def test_representative_checkpoint_records_only_observed_dimensions() -> None:
    results = (
        _Result(
            _Evidence(path="benefits.parquet", semantic_dimension="funding")
        ),
        _Result(
            _Evidence(
                path="history.parquet", semantic_dimension="service_benefit"
            )
        ),
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
    assert (
        checkpoint.receipt_sha256
        == hashlib.sha256(checkpoint.canonical_bytes).hexdigest()
    )


def test_representative_checkpoint_does_not_infer_unobserved_dimensions() -> (
    None
):
    with pytest.raises(PlatinumEvidenceError, match="required dimensions"):
        checkpoint_representative_evidence(
            (_Result(_Evidence()),), required_dimensions=("regulatory",)
        )
