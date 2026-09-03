"""Shared Platinum CLI/API presentation contract tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from global_medicines_atlas.platinum_resolver import ResolvedResource
from global_medicines_atlas.platinum_surface_contracts import (
    DatasetIdentityEnvelope,
    dataset_identity,
)


def resource() -> ResolvedResource:
    return ResolvedResource(
        resource_id="au.mbs.services.current",
        semantic_dimension="service_benefit",
        entity_granularity="service_item",
        dataset="edithatogo/australian-benefits-medallion",
        revision="a" * 40,
        path="gold/mbs/services.parquet",
        sha256="b" * 64,
        byte_count=1234,
        contract_sha256="c" * 64,
        semantic_manifest_sha256="d" * 64,
        source_id="au-mbs",
        acquisition_id="acq-1",
        layer="gold",
        schema_era="2026-08",
        comparison_cohort="current",
        effective_date="2026-08-01",
        retrieved_at="2026-08-02T00:00:00+00:00",
        cache_expires_at=datetime(2026, 9, 1, tzinfo=UTC),
        capabilities=("exact_v4_resolution", "anonymous_verified_read"),
    )


def test_identity_preserves_every_admitted_binding_without_row_claims() -> None:
    envelope = dataset_identity(resource(), jurisdiction="AU")
    payload = envelope.model_dump(mode="json")

    assert payload["revision"] == "a" * 40
    assert payload["object_sha256"] == "b" * 64
    assert payload["contract_sha256"] == "c" * 64
    assert payload["semantic_manifest_sha256"] == "d" * 64
    assert payload["semantic_dimension"] == "service_benefit"
    assert payload["entity_granularity"] == "service_item"
    assert payload["comparison_cohort"] == "current"
    assert payload["jurisdiction"] == "AU"
    assert payload["coverage_state"] == "not_declared"
    assert payload["comparison_validity"] == "not_evaluated"
    assert payload["product_admitted"] is True
    assert payload["rows_queried"] is False


@pytest.mark.parametrize(
    "changed",
    [
        {"revision": "main"},
        {"sha256": "bad"},
        {"contract_sha256": "bad"},
        {"semantic_manifest_sha256": "bad"},
        {"byte_count": 0},
        {"retrieved_at": "not-a-time"},
    ],
)
def test_identity_adapter_rejects_mutable_or_malformed_claims(changed) -> None:
    with pytest.raises((ValueError, ValidationError)):
        dataset_identity(replace(resource(), **changed), jurisdiction="AU")


@pytest.mark.parametrize(
    "changed",
    [
        {"semantic_dimension": "funding_and_regulatory"},
        {"entity_granularity": "patient"},
        {"capabilities": ("unbounded_download",)},
    ],
)
def test_identity_rejects_open_ended_semantic_claims(changed) -> None:
    with pytest.raises(ValidationError):
        dataset_identity(replace(resource(), **changed), jurisdiction="AU")


def test_identity_requires_every_claim_bearing_state() -> None:
    payload = dataset_identity(resource(), jurisdiction="AU").model_dump()
    for field in (
        "jurisdiction",
        "coverage_state",
        "comparison_validity",
        "product_admitted",
        "rows_queried",
    ):
        incomplete = {
            key: value for key, value in payload.items() if key != field
        }
        with pytest.raises(ValidationError):
            DatasetIdentityEnvelope.model_validate(incomplete)

    with pytest.raises(ValidationError):
        dataset_identity(resource(), jurisdiction="Australia")
