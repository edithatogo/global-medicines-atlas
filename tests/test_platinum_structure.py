"""Bounded source-structure Platinum and Atlas contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

from global_medicines_atlas.atlas import AtlasQueryService, create_atlas_app
from global_medicines_atlas.platinum_identity_service import (
    ResolverDatasetIdentityService,
    UnknownPlatinumResourceError,
)
from global_medicines_atlas.platinum_query import PlatinumQueryService
from global_medicines_atlas.platinum_resolver import StorageNeutralResolver
from global_medicines_atlas.platinum_structure import (
    SourceStructureQuery,
    SourceStructureService,
)
from global_medicines_atlas.platinum_surface_contracts import (
    DatasetIdentityV2Envelope,
)
from global_medicines_atlas.platinum_types import PlatinumSemanticDimension

RESOURCE_ID = "au.pbs.synthetic.structure"
OBJECT_SHA256 = "a" * 64


def _identity(
    semantic_dimension: PlatinumSemanticDimension = "source_structure",
    object_sha256: str = OBJECT_SHA256,
) -> DatasetIdentityV2Envelope:
    now = datetime.now(UTC)
    return DatasetIdentityV2Envelope(
        resource_id=RESOURCE_ID,
        dataset="example/australian-benefits-synthetic",
        revision="a" * 40,
        path="gold/pbs-edges.parquet",
        object_sha256=object_sha256,
        byte_count=1,
        contract_sha256="b" * 64,
        semantic_manifest_sha256="c" * 64,
        jurisdiction="AU",
        semantic_dimension=semantic_dimension,
        entity_granularity="evidence_edge",
        source_id="au-pbs",
        acquisition_id="synthetic-pbs-acquisition",
        layer="platinum",
        schema_era="synthetic-pbs-v1",
        comparison_cohort="synthetic",
        effective_date=None,
        retrieved_at=now,
        cache_expires_at=now + timedelta(hours=1),
        capabilities=(
            "exact_v4_resolution",
            "anonymous_verified_read",
            "verified_cache_offline",
        ),
        coverage_state="not_declared",
        comparison_validity="not_evaluated",
        product_admitted=True,
        rows_queried=False,
    )


def _service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    identity: DatasetIdentityV2Envelope | None = None,
    result: object | None = None,
) -> SourceStructureService:
    resolved_identity = identity or _identity()

    def identity_v2(
        self: ResolverDatasetIdentityService, resource_id: str
    ) -> DatasetIdentityV2Envelope:
        del self, resource_id
        return resolved_identity

    monkeypatch.setattr(
        ResolverDatasetIdentityService, "identity_v2", identity_v2
    )
    if result is not None:

        def query_state(
            self: PlatinumQueryService,
            resource_id: str,
            *,
            engine: str,
            spec: object,
            offline: bool = False,
        ) -> object:
            del self, resource_id, engine, spec, offline
            return result

        monkeypatch.setattr(PlatinumQueryService, "query_state", query_state)
    return SourceStructureService(
        cast("StorageNeutralResolver", object()),
        jurisdictions={RESOURCE_ID: "AU"},
    )


def _available_result(
    *,
    object_sha256: str = OBJECT_SHA256,
    semantic_dimension: PlatinumSemanticDimension = "source_structure",
) -> SimpleNamespace:
    return SimpleNamespace(
        status="available",
        evidence=SimpleNamespace(
            object_sha256=object_sha256,
            semantic_dimension=semantic_dimension,
        ),
        rows=({"kind": "source_contains_entity"},),
        query_receipt=SimpleNamespace(
            query_sha256="d" * 64,
            receipt_sha256="e" * 64,
        ),
    )


def test_source_structure_page_preserves_identity_and_query_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _available_result()
    page = _service(monkeypatch, result=result).query(
        RESOURCE_ID,
        SourceStructureQuery(columns=("kind",), limit=10),
    )

    assert page.status == "available"
    assert page.identity.semantic_dimension == "source_structure"
    assert page.rows == ({"kind": "source_contains_entity"},)
    assert page.query_sha256 == "d" * 64
    assert page.query_receipt_sha256 == "e" * 64
    assert page.coverage_state == "not_declared"
    assert page.comparison_validity == "not_evaluated"


def test_source_structure_unavailability_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = SimpleNamespace(
        status="unavailable",
        query_sha256="d" * 64,
        receipt_sha256="e" * 64,
        reason="offline_cache_unavailable",
    )
    page = _service(monkeypatch, result=result).query(
        RESOURCE_ID,
        SourceStructureQuery(columns=("kind",), offline=True),
    )

    assert page.status == "unavailable"
    assert page.rows == ()
    assert page.reason == "offline_cache_unavailable"


def test_non_structure_identity_is_rejected_before_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(monkeypatch, identity=_identity("service_benefit"))
    with pytest.raises(ValueError, match="not source-structure"):
        service.query(RESOURCE_ID, SourceStructureQuery(columns=("kind",)))


def test_query_identity_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _available_result(object_sha256="f" * 64)
    service = _service(monkeypatch, result=result)
    with pytest.raises(ValueError, match="identity differs"):
        service.query(RESOURCE_ID, SourceStructureQuery(columns=("kind",)))


def test_atlas_source_structure_selection_starts_without_a_query() -> None:
    class UnusedLookup:
        def query(
            self, resource_id: str, query: SourceStructureQuery
        ) -> object:
            del resource_id, query
            raise AssertionError("selection page must not query evidence")

    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=cast(
                "SourceStructureService", UnusedLookup()
            ),
        )
    )
    response = client.get("/federated/source-structure")

    assert response.status_code == 200
    assert "Choose a pinned source-structure resource" in response.text
    assert "Use verified cache only" in response.text


@pytest.mark.parametrize(
    ("error", "expected_status", "message"),
    [
        (
            UnknownPlatinumResourceError,
            404,
            "The admitted source-structure resource was not found.",
        ),
        (ValueError, 422, "The federated source-structure query is invalid."),
    ],
)
def test_atlas_source_structure_errors_are_bounded(
    error: type[Exception], expected_status: int, message: str
) -> None:
    class FailingLookup:
        def query(
            self, resource_id: str, query: SourceStructureQuery
        ) -> object:
            del resource_id, query
            raise error

    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=cast(
                "SourceStructureService", FailingLookup()
            ),
        )
    )
    response = client.get(
        "/federated/source-structure", params={"resource_id": RESOURCE_ID}
    )

    assert response.status_code == expected_status
    assert message in response.text
