from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    ComparisonResponse,
    CoverageItem,
    CoverageResponse,
    EvidenceAvailability,
    EvidenceDimension,
    PageMetadata,
    ProductConclusion,
    ProductState,
    ResponseMetadata,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)
from global_medicines_atlas.query_service import QueryServiceError

NOW = datetime(2026, 7, 29, 12, tzinfo=UTC)


def _metadata(returned: int) -> ResponseMetadata:
    return ResponseMetadata(
        generated_at=NOW,
        clocks=AsOfClocks(valid_at=NOW, observed_at=NOW),
        page=PageMetadata(limit=50, returned=returned),
    )


class StateService:
    def comparisons(self, query):
        items = tuple(
            ProductConclusion(
                concept_id=query.concept_id,
                jurisdiction=jurisdiction,
                dimension=dimension,
                state=state,
                terminology=Terminology(
                    native_code=state.value,
                    native_label=state.value.replace("_", " "),
                    native_system="fixture",
                    canonical_code=query.concept_id,
                    canonical_label="Fixture medicine",
                    canonical_system="atlas",
                ),
                evidence_availability=EvidenceAvailability.UNAVAILABLE,
                evidence_unavailable_reason=f"Explicit {state.value} coverage",
                uncertainty=Uncertainty(
                    level=UncertaintyLevel.UNKNOWN,
                    reason=f"Explicit {state.value} fixture",
                ),
                valid_time=AsOfClocks(
                    valid_at=query.valid_at, observed_at=query.observed_at
                ),
            )
            for jurisdiction, dimension, state in (
                ("NZ", EvidenceDimension.FUNDING, ProductState.UNKNOWN),
                (
                    "AU",
                    EvidenceDimension.REGULATORY,
                    ProductState.NOT_COVERED,
                ),
            )
        )
        return ComparisonResponse(
            metadata=_metadata(len(items)), conclusions=items
        )

    def coverage(self, query):
        items = (
            CoverageItem(
                jurisdiction="NZ",
                dimension=EvidenceDimension.FUNDING,
                state=ProductState.UNKNOWN,
                covered_count=17,
                denominator=None,
                valid_time=AsOfClocks(
                    valid_at=query.valid_at, observed_at=query.observed_at
                ),
            ),
        )
        return CoverageResponse(metadata=_metadata(len(items)), coverage=items)


def test_complete_comparison_keeps_unknown_states_and_nullable_coverage():
    response = TestClient(create_atlas_app(StateService())).get(
        "/",
        params=[
            ("concept_id", "rx:fixture"),
            ("jurisdiction", "NZ,AU"),
            ("valid_at", NOW.isoformat()),
            ("observed_at", NOW.isoformat()),
        ],
    )

    assert response.status_code == 200
    assert "Status: unknown" in response.text
    assert "Status: not covered" in response.text
    assert "not evidence of a negative" in response.text
    assert "17 observed; denominator unknown" in response.text
    assert "17%" not in response.text
    assert response.text.count("Review source evidence") == 2
    assert "Valid at" in response.text
    assert "observed at" in response.text


def test_hostile_values_are_escaped_and_unsafe_links_are_not_clickable():
    client = TestClient(create_atlas_app(StateService()))
    response = client.get(
        "/",
        params={
            "concept_id": "<img src=x onerror=alert(1)>",
            "jurisdiction": "NZ",
        },
    )

    assert response.status_code == 200
    assert "<img src=x" not in response.text
    assert "&lt;img src=x" in response.text


def test_invalid_jurisdiction_is_a_visible_bounded_error():
    response = TestClient(create_atlas_app(StateService())).get(
        "/",
        params={"concept_id": "rx:1", "jurisdiction": "NOT-A-CODE"},
    )

    assert response.status_code == 200
    assert 'role="alert"' in response.text
    assert "comparison request is invalid" in response.text.lower()


def test_runtime_query_failure_is_visible_without_internal_details():
    class UnavailableService(StateService):
        def comparisons(self, query):
            del query
            raise QueryServiceError(
                "The read-only query service is unavailable"
            )

    response = TestClient(create_atlas_app(UnavailableService())).get(
        "/",
        params={"concept_id": "rx:1", "jurisdiction": "NZ"},
    )

    assert response.status_code == 200
    assert 'role="alert"' in response.text
    assert "read-only query service is unavailable" in response.text
    assert "duckdb" not in response.text.lower()
