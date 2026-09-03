"""Shared Platinum CLI/API presentation contract tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from global_medicines_atlas.platinum_resolver import ResolvedResource
from global_medicines_atlas.platinum_surface_contracts import dataset_identity


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
    envelope = dataset_identity(resource())
    payload = envelope.model_dump(mode="json")

    assert payload["revision"] == "a" * 40
    assert payload["object_sha256"] == "b" * 64
    assert payload["contract_sha256"] == "c" * 64
    assert payload["semantic_manifest_sha256"] == "d" * 64
    assert payload["semantic_dimension"] == "service_benefit"
    assert payload["entity_granularity"] == "service_item"
    assert payload["comparison_cohort"] == "current"
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
        dataset_identity(replace(resource(), **changed))
