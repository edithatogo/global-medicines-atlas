from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from global_medicines_atlas.product_contracts import (
    API_BASE_PATH,
    API_VERSION,
    DEFAULT_PAGE_SIZE,
    MAX_EXPORT_ROWS,
    MAX_PAGE_SIZE,
    PRODUCT_EVIDENCE_VERSION,
    AsOfClocks,
    ComparisonQuery,
    ComparisonResponse,
    CoverageItem,
    ErrorCode,
    ErrorEnvelope,
    EvidenceAvailability,
    EvidenceDimension,
    EvidenceQuery,
    ExportFormat,
    ExportRequest,
    HealthCheck,
    HealthResponse,
    HealthState,
    PageMetadata,
    ProductConclusion,
    ProductState,
    ProvenanceLink,
    ResponseMetadata,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)

NOW = datetime(2026, 7, 29, 2, 0, tzinfo=UTC)
EARLIER = datetime(2025, 1, 1, tzinfo=UTC)


def clocks() -> AsOfClocks:
    return AsOfClocks(valid_at=EARLIER, observed_at=NOW)


def terminology() -> Terminology:
    return Terminology(
        native_code="NZMT-123",
        native_label="Native medicine name",
        native_system="https://standards.digital.health.nz/ns/nzmt",
        canonical_code="RxCUI-456",
        canonical_label="Canonical medicine name",
        canonical_system="http://www.nlm.nih.gov/research/umls/rxnorm",
    )


def provenance() -> ProvenanceLink:
    return ProvenanceLink(
        source_id="medsafe-register",
        source_uri="https://www.medsafe.govt.nz/regulatory/product-detail",
        retrieved_at=NOW,
        source_sha256="a" * 64,
        transformation_id="pipeline:2026-07-29",
    )


def conclusion(**changes: object) -> ProductConclusion:
    values: dict[str, object] = {
        "concept_id": "medicine:123",
        "jurisdiction": "nz",
        "dimension": EvidenceDimension.REGULATORY,
        "state": ProductState.CONFIRMED,
        "status_code": "approved",
        "terminology": terminology(),
        "provenance": (provenance(),),
        "evidence_availability": EvidenceAvailability.AVAILABLE,
        "uncertainty": Uncertainty(
            level=UncertaintyLevel.LOW,
            confidence=0.98,
        ),
        "valid_time": clocks(),
    }
    values.update(changes)
    return ProductConclusion.model_validate(values)


def response_metadata() -> ResponseMetadata:
    return ResponseMetadata(
        generated_at=NOW,
        clocks=clocks(),
        page=PageMetadata(limit=50, returned=1),
    )


def test_contract_versions_and_base_path_are_frozen() -> None:
    assert API_VERSION == "v1"
    assert API_BASE_PATH == "/api/v1"
    assert PRODUCT_EVIDENCE_VERSION == "0.6"
    assert response_metadata().model_dump()["api_version"] == "v1"
    assert response_metadata().model_dump()["evidence_version"] == "0.6"


def test_comparison_query_normalizes_codes_and_bounds_pagination() -> None:
    query = ComparisonQuery(
        concept_id=" medicine:123 ",
        jurisdictions=("nz", "AUS"),
        valid_at=EARLIER,
        observed_at=NOW,
    )

    assert query.concept_id == "medicine:123"
    assert query.jurisdictions == ("NZ", "AUS")
    assert query.limit == DEFAULT_PAGE_SIZE
    assert query.dimensions == (
        EvidenceDimension.REGULATORY,
        EvidenceDimension.FUNDING,
    )


@pytest.mark.parametrize("limit", [0, MAX_PAGE_SIZE + 1])
def test_comparison_query_rejects_unbounded_pages(limit: int) -> None:
    with pytest.raises(ValidationError):
        ComparisonQuery(
            concept_id="medicine:123",
            jurisdictions=("NZ",),
            valid_at=EARLIER,
            observed_at=NOW,
            limit=limit,
        )


def test_query_rejects_offsets_unknown_fields_and_duplicate_filters() -> None:
    base = {
        "concept_id": "medicine:123",
        "jurisdictions": ("NZ",),
        "valid_at": EARLIER,
        "observed_at": NOW,
    }
    with pytest.raises(ValidationError, match="offset"):
        ComparisonQuery.model_validate({**base, "offset": 10})
    with pytest.raises(ValidationError, match="jurisdictions must be unique"):
        ComparisonQuery.model_validate(
            {**base, "jurisdictions": ("NZ", "nz")},
        )
    with pytest.raises(ValidationError, match="dimensions must be unique"):
        ComparisonQuery.model_validate(
            {
                **base,
                "dimensions": ("regulatory", "regulatory"),
            },
        )


@pytest.mark.parametrize("field", ["valid_at", "observed_at"])
def test_query_clocks_must_be_timezone_aware(field: str) -> None:
    values = {
        "concept_id": "medicine:123",
        "jurisdictions": ("NZ",),
        "valid_at": EARLIER,
        "observed_at": NOW,
    }
    values[field] = NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError):
        ComparisonQuery.model_validate(values)


@pytest.mark.parametrize(
    "cursor",
    ["short", "contains spaces____", "../../escape________", "x" * 2049],
)
def test_cursor_is_opaque_url_safe_and_bounded(cursor: str) -> None:
    with pytest.raises(ValidationError):
        ComparisonQuery(
            concept_id="medicine:123",
            jurisdictions=("NZ",),
            valid_at=EARLIER,
            observed_at=NOW,
            cursor=cursor,
        )


@given(
    max_rows=st.integers(min_value=1, max_value=MAX_EXPORT_ROWS),
    export_format=st.sampled_from(list(ExportFormat)),
)
def test_bounded_export_accepts_every_documented_value(
    max_rows: int,
    export_format: ExportFormat,
) -> None:
    request = ExportRequest(format=export_format, max_rows=max_rows)
    assert request.max_rows == max_rows
    assert request.format is export_format


@pytest.mark.parametrize("max_rows", [0, MAX_EXPORT_ROWS + 1])
def test_export_rejects_out_of_bounds_rows(max_rows: int) -> None:
    with pytest.raises(ValidationError):
        ExportRequest(max_rows=max_rows)


def test_export_formats_exclude_spreadsheet_unsafe_csv() -> None:
    assert {item.value for item in ExportFormat} == {"json", "jsonl"}


def test_native_terminology_is_never_replaced_by_canonical_mapping() -> None:
    value = terminology()
    assert value.native_label == "Native medicine name"
    assert value.canonical_label == "Canonical medicine name"
    assert value.native_label != value.canonical_label


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("canonical_code", "RxCUI-456"),
        ("canonical_label", "Canonical medicine name"),
        ("canonical_system", "RxNorm"),
    ],
)
def test_canonical_mapping_must_be_complete(field: str, value: str) -> None:
    base = {
        "native_code": "NZMT-123",
        "native_label": "Native medicine name",
        "native_system": "NZMT",
        field: value,
    }
    with pytest.raises(ValidationError, match="supplied together"):
        Terminology.model_validate(base)


def test_confirmed_conclusion_keeps_dimensions_and_evidence_explicit() -> None:
    value = conclusion()
    assert value.dimension is EvidenceDimension.REGULATORY
    assert value.state is ProductState.CONFIRMED
    assert value.provenance == (provenance(),)
    assert value.valid_time == clocks()


@pytest.mark.parametrize(
    "state",
    [ProductState.CONFIRMED, ProductState.INFERRED, ProductState.CONFLICTING],
)
def test_evidenced_states_cannot_be_emitted_without_evidence(
    state: ProductState,
) -> None:
    with pytest.raises(ValidationError, match="require evidence"):
        conclusion(
            state=state,
            status_code="candidate",
            provenance=(),
            evidence_availability=EvidenceAvailability.UNAVAILABLE,
            evidence_unavailable_reason="Source inaccessible",
        )


@pytest.mark.parametrize(
    "state",
    [
        ProductState.UNKNOWN,
        ProductState.NOT_COVERED,
        ProductState.CONFLICTING,
        ProductState.NOT_APPLICABLE,
    ],
)
def test_non_negative_states_remain_distinct(state: ProductState) -> None:
    assert ProductState(state.value) is state


@pytest.mark.parametrize(
    "state",
    [ProductState.UNKNOWN, ProductState.NOT_COVERED],
)
def test_absence_states_cannot_imply_a_negative_status(
    state: ProductState,
) -> None:
    with pytest.raises(ValidationError, match="cannot imply a status"):
        conclusion(
            state=state,
            status_code="not_approved",
            provenance=(),
            evidence_availability=EvidenceAvailability.UNAVAILABLE,
            evidence_unavailable_reason="No source coverage",
        )


def test_unknown_can_report_explicit_evidence_unavailability() -> None:
    value = conclusion(
        state=ProductState.UNKNOWN,
        status_code=None,
        provenance=(),
        evidence_availability=EvidenceAvailability.UNAVAILABLE,
        evidence_unavailable_reason="Source was not observed for this period",
        uncertainty=Uncertainty(
            level=UncertaintyLevel.UNKNOWN,
            reason="No authoritative assertion is available",
        ),
    )
    assert value.state is ProductState.UNKNOWN
    assert value.evidence_unavailable_reason is not None


def test_available_evidence_requires_provenance() -> None:
    with pytest.raises(ValidationError, match="provenance"):
        conclusion(provenance=())


def test_unavailable_evidence_requires_reason_and_forbids_provenance() -> None:
    with pytest.raises(ValidationError, match="explicit reason"):
        conclusion(
            state=ProductState.UNKNOWN,
            status_code=None,
            provenance=(),
            evidence_availability=EvidenceAvailability.UNAVAILABLE,
        )
    with pytest.raises(ValidationError, match="cannot include provenance"):
        conclusion(
            state=ProductState.UNKNOWN,
            status_code=None,
            evidence_availability=EvidenceAvailability.UNAVAILABLE,
            evidence_unavailable_reason="Unavailable",
        )


@given(confidence=st.floats(min_value=0.0, max_value=1.0))
def test_confidence_accepts_closed_unit_interval(confidence: float) -> None:
    value = Uncertainty(level=UncertaintyLevel.LOW, confidence=confidence)
    assert value.confidence == confidence


@pytest.mark.parametrize("confidence", [-0.0001, 1.0001])
def test_confidence_rejects_values_outside_unit_interval(
    confidence: float,
) -> None:
    with pytest.raises(ValidationError):
        Uncertainty(level=UncertaintyLevel.LOW, confidence=confidence)


@pytest.mark.parametrize(
    "level",
    [
        UncertaintyLevel.MEDIUM,
        UncertaintyLevel.HIGH,
        UncertaintyLevel.UNKNOWN,
    ],
)
def test_material_uncertainty_requires_reason(
    level: UncertaintyLevel,
) -> None:
    with pytest.raises(ValidationError, match="requires a reason"):
        Uncertainty(level=level)


def test_nullable_coverage_denominator_does_not_invent_percentage() -> None:
    item = CoverageItem(
        jurisdiction="NZ",
        dimension=EvidenceDimension.FUNDING,
        state=ProductState.UNKNOWN,
        covered_count=12,
        denominator=None,
        valid_time=clocks(),
    )
    assert item.denominator is None
    assert "percentage" not in item.model_dump()


def test_coverage_count_cannot_exceed_known_denominator() -> None:
    with pytest.raises(ValidationError, match="cannot exceed denominator"):
        CoverageItem(
            jurisdiction="NZ",
            dimension=EvidenceDimension.FUNDING,
            state=ProductState.CONFIRMED,
            covered_count=11,
            denominator=10,
            valid_time=clocks(),
        )


def test_evidence_query_requires_exactly_one_lookup_key() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        EvidenceQuery(valid_at=EARLIER, observed_at=NOW)
    with pytest.raises(ValidationError, match="exactly one"):
        EvidenceQuery(
            assertion_id="assertion:1",
            concept_id="medicine:1",
            valid_at=EARLIER,
            observed_at=NOW,
        )


def test_page_metadata_is_internally_bounded() -> None:
    with pytest.raises(ValidationError, match="cannot exceed page limit"):
        PageMetadata(limit=5, returned=6)


def test_response_serializes_versioned_evidence_contract() -> None:
    response = ComparisonResponse(
        metadata=response_metadata(),
        conclusions=(conclusion(),),
    )
    document = response.model_dump(mode="json")
    assert document["metadata"]["api_version"] == "v1"
    assert document["metadata"]["evidence_version"] == "0.6"
    assert document["conclusions"][0]["valid_time"] == {
        "valid_at": "2025-01-01T00:00:00Z",
        "observed_at": "2026-07-29T02:00:00Z",
    }
    assert document["conclusions"][0]["dimension"] == "regulatory"


def test_response_rejects_page_metadata_that_disagrees_with_payload() -> None:
    metadata = ResponseMetadata(
        generated_at=NOW,
        clocks=clocks(),
        page=PageMetadata(limit=50, returned=0),
    )
    with pytest.raises(ValidationError, match="must match conclusions"):
        ComparisonResponse(
            metadata=metadata,
            conclusions=(conclusion(),),
        )


def test_health_response_is_versioned_and_has_typed_states() -> None:
    response = HealthResponse(
        state=HealthState.DEGRADED,
        checked_at=NOW,
        checks=(
            HealthCheck(
                name="canonical-data",
                state=HealthState.UNAVAILABLE,
                detail="No qualified data bundle is mounted",
            ),
        ),
    )
    assert response.api_version == "v1"
    assert response.evidence_version == "0.6"
    assert response.checks[0].state is HealthState.UNAVAILABLE


def test_typed_error_envelope_is_stable_and_immutable() -> None:
    error = ErrorEnvelope(
        error=ErrorCode.INVALID_CURSOR,
        message="Cursor does not match this query",
        request_id="request-123",
    )
    assert error.model_dump(mode="json") == {
        "api_version": "v1",
        "error": "invalid_cursor",
        "message": "Cursor does not match this query",
        "request_id": "request-123",
        "details": [],
        "retryable": False,
    }
    with pytest.raises(ValidationError):
        ErrorEnvelope.model_validate(
            {
                **error.model_dump(),
                "stack_trace": "must not leak",
            },
        )
    with pytest.raises(ValidationError):
        error.retryable = True
