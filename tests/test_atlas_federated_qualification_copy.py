"""Federated Atlas wording follows the pinned resource, not test defaults."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from fastapi.testclient import TestClient

from global_medicines_atlas.atlas import AtlasQueryService, create_atlas_app
from global_medicines_atlas.platinum_benefits import BenefitsPage, BenefitsQuery
from global_medicines_atlas.platinum_identity_service import (
    UnknownPlatinumResourceError,
)
from global_medicines_atlas.platinum_structure import (
    SourceStructurePage,
    SourceStructureQuery,
)
from global_medicines_atlas.platinum_surface_contracts import (
    DatasetIdentityEnvelope,
    DatasetIdentityV2Envelope,
)

NOW = datetime(2026, 10, 9, tzinfo=UTC)
RESOURCE = "au.mbs.services"


def _benefits_page(
    comparison_cohort: Literal["current", "synthetic"] = "current",
) -> BenefitsPage:
    return BenefitsPage(
        status="available",
        identity=DatasetIdentityEnvelope(
            resource_id=RESOURCE,
            dataset="global-medicines-atlas/australian-benefits",
            revision="a" * 40,
            path="silver/mbs-services.parquet",
            object_sha256="b" * 64,
            byte_count=128,
            contract_sha256="c" * 64,
            semantic_manifest_sha256="d" * 64,
            jurisdiction="AU",
            semantic_dimension="service_benefit",
            entity_granularity="service_item",
            source_id="au-mbs",
            acquisition_id="mbs-acquisition-1",
            layer="silver",
            schema_era="mbs-2025-v1",
            comparison_cohort=comparison_cohort,
            effective_date="2025-07-01",
            retrieved_at=NOW,
            cache_expires_at=NOW + timedelta(hours=1),
            capabilities=("exact_v4_resolution", "anonymous_verified_read"),
            coverage_state="not_declared",
            comparison_validity="not_evaluated",
            product_admitted=True,
            rows_queried=False,
        ),
        rows=({"item_code": "100"},),
        query_sha256="e" * 64,
        window_sha256="f" * 64,
        page_sha256="1" * 64,
        receipt_sha256="2" * 64,
        reason=None,
        next_cursor=None,
        window_rows=1,
        window_complete=True,
    )


def _structure_page(
    comparison_cohort: Literal["current", "synthetic"] = "current",
) -> SourceStructurePage:
    return SourceStructurePage(
        status="available",
        identity=DatasetIdentityV2Envelope(
            resource_id=RESOURCE,
            dataset="global-medicines-atlas/australian-benefits",
            revision="a" * 40,
            path="gold/mbs-edges.parquet",
            object_sha256="b" * 64,
            byte_count=128,
            contract_sha256="c" * 64,
            semantic_manifest_sha256="d" * 64,
            jurisdiction="AU",
            semantic_dimension="source_structure",
            entity_granularity="evidence_edge",
            source_id="au-mbs",
            acquisition_id="mbs-acquisition-1",
            layer="gold",
            schema_era="mbs-2025-v1",
            comparison_cohort=comparison_cohort,
            effective_date="2025-07-01",
            retrieved_at=NOW,
            cache_expires_at=NOW + timedelta(hours=1),
            capabilities=("exact_v4_resolution", "anonymous_verified_read"),
            coverage_state="not_declared",
            comparison_validity="not_evaluated",
            product_admitted=True,
            rows_queried=False,
        ),
        rows=({"kind": "source_contains_entity"},),
        query_sha256="e" * 64,
        query_receipt_sha256="2" * 64,
        query_receipt_json="{}",
        reason=None,
    )


@dataclass
class BenefitsLookup:
    comparison_cohort: Literal["current", "synthetic"] = "current"

    def query(self, resource_id: str, query: BenefitsQuery) -> BenefitsPage:
        del query
        if resource_id != RESOURCE:
            raise UnknownPlatinumResourceError
        return _benefits_page(self.comparison_cohort)


@dataclass
class StructureLookup:
    comparison_cohort: Literal["current", "synthetic"] = "current"

    def query(
        self, resource_id: str, query: SourceStructureQuery
    ) -> SourceStructurePage:
        del query
        if resource_id != RESOURCE:
            raise UnknownPlatinumResourceError
        return _structure_page(self.comparison_cohort)


def test_benefits_view_does_not_call_a_current_resource_fixture_only() -> None:
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_benefits=BenefitsLookup(),
        )
    )

    response = client.get(
        "/federated/benefits",
        params={"resource_id": RESOURCE, "columns": "item_code"},
    )

    assert response.status_code == 200
    assert "Comparison cohort</dt><dd>current" in response.text
    assert "fixture-qualified view" not in response.text
    assert "Coverage is not declared here" in response.text


def test_structure_view_does_not_call_a_current_resource_synthetic() -> None:
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=StructureLookup(),
        )
    )

    response = client.get(
        "/federated/source-structure",
        params={"resource_id": RESOURCE, "columns": "kind"},
    )

    assert response.status_code == 200
    assert "Comparison cohort</dt><dd>current" in response.text
    assert "This synthetic qualification" not in response.text
    assert "Coverage is not declared here" in response.text


def test_benefits_view_retains_synthetic_resource_limits() -> None:
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_benefits=BenefitsLookup(comparison_cohort="synthetic"),
        )
    )

    response = client.get(
        "/federated/benefits",
        params={"resource_id": RESOURCE, "columns": "item_code"},
    )

    assert response.status_code == 200
    assert "synthetic qualification fixtures" in response.text
    assert "not populated production source data" in response.text


def test_structure_view_retains_synthetic_resource_limits() -> None:
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=StructureLookup(
                comparison_cohort="synthetic"
            ),
        )
    )

    response = client.get(
        "/federated/source-structure",
        params={"resource_id": RESOURCE, "columns": "kind"},
    )

    assert response.status_code == 200
    assert "synthetic qualification fixtures" in response.text
    assert "not populated production source data" in response.text
