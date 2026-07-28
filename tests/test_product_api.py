from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient

from global_medicines_atlas.api import create_app
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    ComparisonQuery,
    ComparisonResponse,
    CoverageQuery,
    CoverageResponse,
    EvidenceAvailability,
    EvidenceDimension,
    EvidenceItem,
    EvidenceQuery,
    EvidenceResponse,
    PageMetadata,
    ProductConclusion,
    ProductState,
    ProvenanceLink,
    ResponseMetadata,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)
from global_medicines_atlas.query_service import (
    InvalidCursorError,
    QueryServiceError,
    ReadOnlyQueryService,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
CLOCK_PARAMS = {
    "valid_at": NOW.isoformat(),
    "observed_at": NOW.isoformat(),
}


class StubService:
    def __init__(self) -> None:
        self.comparison_query: ComparisonQuery | None = None
        self.coverage_query: CoverageQuery | None = None
        self.evidence_query: EvidenceQuery | None = None
        self.invalid_cursor = False
        self.unavailable = False

    def readiness_probe(self) -> None:
        if self.unavailable:
            raise QueryServiceError("sensitive DuckDB detail")

    @staticmethod
    def _metadata(
        *,
        limit: int,
        returned: int,
    ) -> ResponseMetadata:
        return ResponseMetadata(
            generated_at=NOW,
            clocks=AsOfClocks(valid_at=NOW, observed_at=NOW),
            page=PageMetadata(limit=limit, returned=returned),
        )

    def comparisons(self, query: ComparisonQuery) -> ComparisonResponse:
        if self.invalid_cursor:
            raise InvalidCursorError
        if self.unavailable:
            raise QueryServiceError("corrupt file at C:/sensitive/atlas.duckdb")
        self.comparison_query = query
        conclusion = ProductConclusion(
            concept_id=query.concept_id,
            jurisdiction="NZ",
            dimension=EvidenceDimension.REGULATORY,
            state=ProductState.UNKNOWN,
            terminology=Terminology(
                native_code="coverage-unknown",
                native_label="Coverage unknown",
                native_system="Medsafe",
            ),
            evidence_availability=EvidenceAvailability.UNAVAILABLE,
            evidence_unavailable_reason="No explicit source coverage assertion",
            uncertainty=Uncertainty(
                level=UncertaintyLevel.UNKNOWN,
                reason="Source coverage is unknown",
            ),
            valid_time=AsOfClocks(
                valid_at=query.valid_at,
                observed_at=query.observed_at,
            ),
        )
        return ComparisonResponse(
            metadata=self._metadata(limit=query.limit, returned=1),
            conclusions=(conclusion,),
        )

    def coverage(self, query: CoverageQuery) -> CoverageResponse:
        self.coverage_query = query
        return CoverageResponse(
            metadata=self._metadata(limit=query.limit, returned=0),
            coverage=(),
        )

    def evidence(self, query: EvidenceQuery) -> EvidenceResponse:
        self.evidence_query = query
        item = EvidenceItem(
            assertion_id=query.assertion_id or "assertion-by-concept",
            concept_id=query.concept_id or "rx:1",
            jurisdiction="NZ",
            dimension=EvidenceDimension.REGULATORY,
            state=ProductState.CONFIRMED,
            status_code="approved",
            terminology=Terminology(
                native_code="approved",
                native_label="Approved",
                native_system="Medsafe",
                canonical_code="rx:1",
                canonical_label="Example medicine",
                canonical_system="GMA",
            ),
            provenance=ProvenanceLink(
                source_id="medsafe",
                source_uri="https://example.test/medsafe/rx-1",
                retrieved_at=NOW,
                source_sha256="a" * 64,
            ),
            uncertainty=Uncertainty(level=UncertaintyLevel.NONE),
            valid_time=AsOfClocks(
                valid_at=query.valid_at,
                observed_at=query.observed_at,
            ),
        )
        return EvidenceResponse(
            metadata=self._metadata(limit=query.limit, returned=1),
            evidence=(item,),
        )


def _client() -> tuple[TestClient, StubService]:
    service = StubService()
    app = create_app(cast("ReadOnlyQueryService", service))
    return TestClient(app), service


def test_comparison_preserves_unknown_without_negative_status() -> None:
    client, service = _client()
    response = client.get(
        "/api/v1/comparisons",
        params={
            "concept_id": "rx:1",
            "jurisdictions": ["nz", "au"],
            "dimensions": ["regulatory", "funding"],
            **CLOCK_PARAMS,
        },
    )

    assert response.status_code == 200
    conclusion = response.json()["conclusions"][0]
    assert conclusion["state"] == "unknown"
    assert conclusion["status_code"] is None
    assert conclusion["evidence_availability"] == "unavailable"
    assert service.comparison_query is not None
    assert service.comparison_query.jurisdictions == ("NZ", "AU")
    assert response.headers["cache-control"].startswith("public")


def test_evidence_drill_down_exposes_source_and_native_terminology() -> None:
    client, service = _client()
    response = client.get(
        "/api/v1/evidence",
        params={"assertion_id": "a-nz-reg", **CLOCK_PARAMS},
    )

    assert response.status_code == 200
    evidence = response.json()["evidence"][0]
    assert evidence["assertion_id"] == "a-nz-reg"
    assert evidence["terminology"]["native_system"] == "Medsafe"
    assert evidence["provenance"]["source_uri"].startswith("https://")
    assert service.evidence_query is not None


def test_coverage_accepts_bounded_repeated_filters() -> None:
    client, service = _client()
    response = client.get(
        "/api/v1/coverage",
        params={
            "jurisdictions": ["NZ", "US"],
            "dimensions": ["regulatory"],
            "limit": 25,
            **CLOCK_PARAMS,
        },
    )

    assert response.status_code == 200
    assert service.coverage_query is not None
    assert service.coverage_query.limit == 25
    assert service.coverage_query.dimensions == (EvidenceDimension.REGULATORY,)


def test_validation_errors_use_stable_typed_envelope() -> None:
    client, _ = _client()
    response = client.get(
        "/api/v1/comparisons",
        params={
            "concept_id": "rx:1",
            "jurisdictions": "NZ",
            "limit": 251,
            **CLOCK_PARAMS,
        },
        headers={"x-request-id": "test-request"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "api_version": "v1",
        "error": "invalid_request",
        "message": "Request parameters are invalid",
        "request_id": "test-request",
        "details": [
            {
                "field": "query.limit",
                "message": "Input should be less than or equal to 250",
            }
        ],
        "retryable": False,
    }
    assert response.headers["cache-control"] == "no-store"


def test_cross_field_validation_requires_exactly_one_evidence_key() -> None:
    client, _ = _client()
    response = client.get("/api/v1/evidence", params=CLOCK_PARAMS)

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert "exactly one" in response.json()["details"][0]["message"]


def test_hostile_input_is_data_and_never_a_route_or_sql_surface() -> None:
    client, service = _client()
    hostile = "rx:1'; DROP TABLE temporal_assertions; --"
    response = client.get(
        "/api/v1/comparisons",
        params={
            "concept_id": hostile,
            "jurisdictions": "NZ",
            **CLOCK_PARAMS,
        },
    )

    assert response.status_code == 200
    assert service.comparison_query is not None
    assert service.comparison_query.concept_id == hostile


def test_invalid_cursor_has_stable_non_retryable_error() -> None:
    client, service = _client()
    service.invalid_cursor = True
    response = client.get(
        "/api/v1/comparisons",
        params={
            "concept_id": "rx:1",
            "jurisdictions": "NZ",
            "cursor": "A" * 16,
            **CLOCK_PARAMS,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_cursor"
    assert response.json()["retryable"] is False


def test_api_is_read_only_and_supports_cache_safe_head() -> None:
    client, _ = _client()
    path = "/api/v1/comparisons"
    params = {
        "concept_id": "rx:1",
        "jurisdictions": "NZ",
        **CLOCK_PARAMS,
    }

    head = client.head(path, params=params)
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["cache-control"].startswith("public")
    for method in (client.post, client.put, client.patch, client.delete):
        assert method(path, params=params).status_code == 405


def test_openapi_is_versioned_bounded_and_has_no_mutation_operations() -> None:
    client, _ = _client()
    schema = client.get("/api/v1/openapi.json").json()

    assert schema["info"]["version"] == "0.6"
    for path, operations in schema["paths"].items():
        if path.startswith("/api/v1/"):
            assert not ({"post", "put", "patch", "delete"} & set(operations))
    comparison_parameters = {
        parameter["name"]: parameter
        for parameter in schema["paths"]["/api/v1/comparisons"]["get"][
            "parameters"
        ]
    }
    assert comparison_parameters["limit"]["schema"]["maximum"] == 250
    assert comparison_parameters["jurisdictions"]["schema"]["maxItems"] == 50
    assert "offset" not in comparison_parameters
    assert schema["paths"]["/api/v1/evidence"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"].endswith("/EvidenceResponse")


def test_health_and_readiness_are_versioned_and_not_cached() -> None:
    client, _ = _client()
    for path in ("/api/v1/health", "/api/v1/readiness"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["api_version"] == "v1"
        assert response.json()["evidence_version"] == "0.6"
        assert response.headers["cache-control"] == "no-store"


def test_readiness_fails_closed_with_stable_non_leaking_envelope() -> None:
    client, service = _client()
    service.unavailable = True

    response = client.get(
        "/api/v1/readiness",
        headers={"x-request-id": "readiness-test"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "api_version": "v1",
        "error": "service_unavailable",
        "message": "The read-only query service is unavailable",
        "request_id": "readiness-test",
        "details": [],
        "retryable": True,
    }
    assert "sensitive" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_runtime_query_failure_uses_stable_non_leaking_envelope() -> None:
    client, service = _client()
    service.unavailable = True

    response = client.get(
        "/api/v1/comparisons",
        params={
            "concept_id": "rx:1",
            "jurisdictions": "NZ",
            **CLOCK_PARAMS,
        },
    )

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"
    assert response.json()["retryable"] is True
    assert "sensitive" not in response.text
