"""HTTP contract controls for the isolated additive V2 transport."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from global_medicines_atlas.platinum_v2_api import create_v2_app
from global_medicines_atlas.platinum_v2_contracts import (
    V2ComparisonQuery,
    V2ComparisonResponse,
    V2Conclusion,
    V2EvidenceDimension,
    V2EvidenceItem,
    V2EvidenceQuery,
    V2EvidenceResponse,
    V2ResponseMetadata,
)
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    EvidenceAvailability,
    PageMetadata,
    ProductState,
    ProvenanceLink,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)
from global_medicines_atlas.query_service import (
    InvalidCursorError,
    QueryServiceError,
)

NOW = datetime(2026, 9, 14, tzinfo=UTC)
CLOCK_PARAMS = {"valid_at": NOW.isoformat(), "observed_at": NOW.isoformat()}


class StubV2Service:
    def __init__(self) -> None:
        self.query: V2ComparisonQuery | None = None
        self.evidence_query: V2EvidenceQuery | None = None
        self.invalid_cursor = False
        self.unavailable = False

    def v2_comparisons(self, query: V2ComparisonQuery) -> V2ComparisonResponse:
        if self.invalid_cursor:
            raise InvalidCursorError
        if self.unavailable:
            raise QueryServiceError("sensitive DuckDB path")
        self.query = query
        conclusion = V2Conclusion(
            concept_id=query.concept_id,
            jurisdiction="NZ",
            dimension=V2EvidenceDimension.SERVICE_BENEFIT,
            state=ProductState.CONFIRMED,
            status_code="eligible",
            terminology=Terminology(
                native_code="eligible",
                native_label="Eligible service benefit",
                native_system="NZ service register",
            ),
            provenance=(
                ProvenanceLink(
                    source_id="nz-service-register",
                    source_uri="https://example.test/nz/service/1",
                    retrieved_at=NOW,
                    source_sha256="a" * 64,
                ),
            ),
            evidence_availability=EvidenceAvailability.AVAILABLE,
            uncertainty=Uncertainty(level=UncertaintyLevel.NONE),
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )
        return V2ComparisonResponse(
            metadata=V2ResponseMetadata(
                generated_at=NOW,
                clocks=AsOfClocks(
                    valid_at=query.valid_at, observed_at=query.observed_at
                ),
                page=PageMetadata(limit=query.limit, returned=1),
            ),
            conclusions=(conclusion,),
        )

    def v2_evidence(self, query: V2EvidenceQuery) -> V2EvidenceResponse:
        if self.invalid_cursor:
            raise InvalidCursorError
        if self.unavailable:
            raise QueryServiceError("sensitive DuckDB path")
        self.evidence_query = query
        item = V2EvidenceItem(
            assertion_id="a-nz-service",
            concept_id=query.concept_id,
            jurisdiction=query.jurisdiction,
            dimension=query.dimension,
            state=ProductState.CONFIRMED,
            status_code="eligible",
            terminology=Terminology(
                native_code="eligible",
                native_label="Eligible service benefit",
                native_system="NZ service register",
            ),
            provenance=ProvenanceLink(
                source_id="nz-service-register",
                source_uri="https://example.test/nz/service/1",
                retrieved_at=NOW,
                source_sha256="a" * 64,
            ),
            uncertainty=Uncertainty(level=UncertaintyLevel.NONE),
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )
        return V2EvidenceResponse(
            metadata=V2ResponseMetadata(
                generated_at=NOW,
                clocks=AsOfClocks(
                    valid_at=query.valid_at, observed_at=query.observed_at
                ),
                page=PageMetadata(limit=query.limit, returned=1),
            ),
            evidence=(item,),
        )


def _client() -> tuple[TestClient, StubV2Service]:
    service = StubV2Service()
    return TestClient(create_v2_app(service)), service


def _params() -> dict[str, object]:
    return {
        "concept_id": "rx:1",
        "jurisdictions": ["nz", "au"],
        "dimensions": ["service_benefit", "terminology"],
        **CLOCK_PARAMS,
    }


def test_v2_transport_preserves_all_requested_dimensions_and_version() -> None:
    client, service = _client()
    response = client.get("/api/v2/comparisons", params=_params())

    assert response.status_code == 200
    assert response.json()["metadata"]["api_version"] == "v2"
    assert response.json()["conclusions"][0]["dimension"] == "service_benefit"
    assert service.query is not None
    assert service.query.jurisdictions == ("NZ", "AU")
    assert service.query.dimensions == (
        V2EvidenceDimension.SERVICE_BENEFIT,
        V2EvidenceDimension.TERMINOLOGY,
    )
    assert response.headers["cache-control"].startswith("public")


def test_v2_transport_rejects_duplicate_dimension_with_v2_error() -> None:
    client, _ = _client()
    params = _params()
    params["dimensions"] = ["funding", "funding"]
    response = client.get(
        "/api/v2/comparisons",
        params=params,
        headers={"x-request-id": "v2-validation"},
    )

    assert response.status_code == 422
    assert response.json()["api_version"] == "v2"
    assert response.json()["error"] == "invalid_request"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] == "v2-validation"


def test_v2_transport_uses_v2_errors_for_framework_validation() -> None:
    client, _ = _client()
    response = client.get(
        "/api/v2/comparisons",
        params={
            "concept_id": "rx:1",
            "jurisdictions": "NZ",
            **CLOCK_PARAMS,
        },
        headers={"x-request-id": "x" * 129},
    )

    assert response.status_code == 422
    assert response.json()["api_version"] == "v2"
    assert response.json()["error"] == "invalid_request"
    assert response.headers["x-request-id"] != "x" * 129


def test_v2_transport_has_stable_cursor_and_service_failures() -> None:
    client, service = _client()
    service.invalid_cursor = True
    response = client.get(
        "/api/v2/comparisons", params={**_params(), "cursor": "A" * 16}
    )
    assert response.status_code == 400
    assert response.json()["api_version"] == "v2"
    assert response.json()["error"] == "invalid_cursor"

    service.invalid_cursor = False
    service.unavailable = True
    response = client.get("/api/v2/comparisons", params=_params())
    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"
    assert "sensitive" not in response.text


def test_v2_evidence_transport_uses_scoped_filters() -> None:
    client, service = _client()
    response = client.get(
        "/api/v2/evidence",
        params={
            "concept_id": "rx:1",
            "jurisdiction": "nz",
            "dimension": "service_benefit",
            **CLOCK_PARAMS,
        },
    )
    assert response.status_code == 200
    assert response.json()["evidence"][0]["dimension"] == "service_benefit"
    assert service.evidence_query is not None
    assert service.evidence_query.jurisdiction == "NZ"


def test_v2_transport_is_read_only_and_openapi_is_isolated() -> None:
    client, _ = _client()
    response = client.head("/api/v2/comparisons", params=_params())
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["cache-control"].startswith("public")
    assert (
        client.post("/api/v2/comparisons", params=_params()).status_code == 405
    )

    schema = client.get("/api/v2/openapi.json").json()
    assert schema["info"]["version"] == "v2"
    assert "/api/v2/comparisons" in schema["paths"]
    assert "/api/v2/evidence" in schema["paths"]
    assert not any(path.startswith("/api/v1/") for path in schema["paths"])
