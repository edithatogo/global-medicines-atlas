"""Dataset identity service and API contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient

from global_medicines_atlas.api import create_app
from global_medicines_atlas.platinum_identity_service import (
    ResolverDatasetIdentityService,
    UnknownPlatinumResourceError,
)
from global_medicines_atlas.platinum_resolver import (
    ResolvedResource,
    StorageNeutralResolver,
)
from global_medicines_atlas.platinum_surface_contracts import dataset_identity
from global_medicines_atlas.query_service import ReadOnlyQueryService


def resolved() -> ResolvedResource:
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


class ResolverStub:
    opened = False

    def resolve(self, resource_id: str) -> ResolvedResource:
        if resource_id != "au.mbs.services.current":
            raise ValueError("sensitive resolver detail")
        return resolved()


class QueryStub:
    pass


class IdentityStub:
    def identity(self, resource_id: str):
        if resource_id != "au.mbs.services.current":
            raise UnknownPlatinumResourceError
        return dataset_identity(resolved(), jurisdiction="AU")


def client(*, configured: bool = True) -> TestClient:
    return TestClient(
        create_app(
            cast("ReadOnlyQueryService", QueryStub()),
            dataset_identities=IdentityStub() if configured else None,
        )
    )


def test_resolver_service_returns_identity_without_opening_bytes() -> None:
    resolver = ResolverStub()
    service = ResolverDatasetIdentityService(
        cast("StorageNeutralResolver", resolver),
        jurisdictions={"au.mbs.services.current": "AU"},
    )

    result = service.identity("au.mbs.services.current")

    assert result.jurisdiction == "AU"
    assert result.rows_queried is False
    assert resolver.opened is False


@pytest.mark.parametrize(
    ("resource_id", "jurisdictions"),
    [
        ("unknown.resource", {"au.mbs.services.current": "AU"}),
        ("unknown.resource", {"unknown.resource": "AU"}),
    ],
)
def test_resolver_service_hides_unknown_resource_details(
    resource_id: str, jurisdictions: dict[str, str]
) -> None:
    service = ResolverDatasetIdentityService(
        cast("StorageNeutralResolver", ResolverStub()),
        jurisdictions=jurisdictions,
    )

    with pytest.raises(UnknownPlatinumResourceError) as error:
        service.identity(resource_id)

    assert not str(error.value)


@pytest.mark.parametrize("jurisdictions", [{}, {"resource": "Australia"}])
def test_resolver_service_rejects_invalid_jurisdiction_map(
    jurisdictions,
) -> None:
    with pytest.raises(ValueError, match="jurisdictions"):
        ResolverDatasetIdentityService(
            cast("StorageNeutralResolver", ResolverStub()),
            jurisdictions=jurisdictions,
        )


def test_dataset_identity_endpoint_returns_exact_typed_envelope() -> None:
    response = client().get(
        "/api/v1/datasets/au.mbs.services.current",
        headers={"x-request-id": "identity-test"},
    )

    assert response.status_code == 200
    assert response.json()["revision"] == "a" * 40
    assert response.json()["coverage_state"] == "not_declared"
    assert response.json()["comparison_validity"] == "not_evaluated"
    assert response.headers["cache-control"].startswith("public")


def test_unknown_identity_is_typed_not_found_without_internal_detail() -> None:
    response = client().get("/api/v1/datasets/unknown.resource")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
    assert "sensitive" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_unconfigured_identity_service_fails_closed() -> None:
    response = client(configured=False).get(
        "/api/v1/datasets/au.mbs.services.current"
    )

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"
    assert response.json()["retryable"] is True


def test_identity_endpoint_is_bounded_in_openapi() -> None:
    document = client().get("/api/v1/openapi.json").json()
    operation = document["paths"]["/api/v1/datasets/{resource_id}"]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]
    assert operation["responses"]["404"]["content"]["application/json"]
    assert operation["responses"]["503"]["content"]["application/json"]
