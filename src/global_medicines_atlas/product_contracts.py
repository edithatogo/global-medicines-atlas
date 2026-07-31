"""Versioned, evidence-preserving contracts for public product surfaces."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

API_VERSION = "v1"
API_BASE_PATH = f"/api/{API_VERSION}"
PRODUCT_EVIDENCE_VERSION = "0.6"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 250
MAX_EXPORT_ROWS = 10_000

NonBlank = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]


def _normalize_jurisdiction(value: object) -> object:
    if isinstance(value, str):
        return value.strip().upper()
    return value


JurisdictionCode = Annotated[
    str,
    BeforeValidator(_normalize_jurisdiction),
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[A-Z]{2,3}$",
    ),
]
CursorToken = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=16,
        max_length=2048,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]


class ProductModel(BaseModel):
    """Immutable public model that rejects undocumented input fields."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class ProductState(StrEnum):
    """States that must never be collapsed into a negative conclusion."""

    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
    NOT_COVERED = "not_covered"
    CONFLICTING = "conflicting"
    NOT_APPLICABLE = "not_applicable"


class EvidenceDimension(StrEnum):
    REGULATORY = "regulatory"
    FUNDING = "funding"
    FORMULARY = "formulary"


class EvidenceAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_REQUIRED = "not_required"


class UncertaintyLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class ComparisonValidityOutcome(StrEnum):
    """Whether evidence supports only the stated status comparison."""

    VALID = "valid"
    VALID_WITH_CAVEATS = "valid_with_caveats"
    INAPPROPRIATE_COMPARISON = "inappropriate_comparison"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ComparisonDimensionState(StrEnum):
    ALIGNED = "aligned"
    COMPATIBLE = "compatible"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ExportFormat(StrEnum):
    JSON = "json"
    JSONL = "jsonl"


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INVALID_CURSOR = "invalid_cursor"
    NOT_FOUND = "not_found"
    LIMIT_EXCEEDED = "limit_exceeded"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INTERNAL_ERROR = "internal_error"


class HealthState(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class MatchMethod(StrEnum):
    """Deterministic candidate-discovery methods, in precedence order."""

    EXACT_CONCEPT_ID = "exact_concept_id"
    EXACT_IDENTIFIER = "exact_identifier"
    NORMALIZED_PREFERRED_NAME = "normalized_preferred_name"
    NORMALIZED_ALIAS = "normalized_alias"


class PageRequest(ProductModel):
    """Bounded cursor pagination; offset pagination is intentionally absent."""

    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    cursor: CursorToken | None = None


class ExportRequest(ProductModel):
    """Safe, bounded export controls shared by CLI and API."""

    format: ExportFormat = ExportFormat.JSON
    max_rows: int = Field(default=1_000, ge=1, le=MAX_EXPORT_ROWS)


class AsOfClocks(ProductModel):
    """Independent valid-time and observation-time query clocks."""

    valid_at: AwareDatetime
    observed_at: AwareDatetime


class ComparisonQuery(PageRequest, AsOfClocks):
    concept_id: NonBlank
    jurisdictions: tuple[JurisdictionCode, ...] = Field(
        min_length=1,
        max_length=50,
    )
    dimensions: tuple[EvidenceDimension, ...] = (
        EvidenceDimension.REGULATORY,
        EvidenceDimension.FUNDING,
    )
    export: ExportRequest | None = None

    @model_validator(mode="after")
    def unique_filters(self) -> Self:
        if len(set(self.jurisdictions)) != len(self.jurisdictions):
            raise ValueError("jurisdictions must be unique")
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("dimensions must be unique")
        return self


class CoverageQuery(PageRequest, AsOfClocks):
    jurisdictions: tuple[JurisdictionCode, ...] = Field(
        min_length=1,
        max_length=50,
    )
    dimensions: tuple[EvidenceDimension, ...] = ()


class EvidenceQuery(PageRequest, AsOfClocks):
    assertion_id: NonBlank | None = None
    concept_id: NonBlank | None = None

    @model_validator(mode="after")
    def exactly_one_lookup_key(self) -> Self:
        if (self.assertion_id is None) == (self.concept_id is None):
            raise ValueError(
                "exactly one of assertion_id or concept_id is required",
            )
        return self


class ConceptSearchQuery(PageRequest):
    """Bounded deterministic discovery without semantic equivalence."""

    query: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    jurisdictions: tuple[JurisdictionCode, ...] = Field(
        default=(), max_length=50
    )

    @model_validator(mode="after")
    def unique_jurisdictions(self) -> Self:
        if len(set(self.jurisdictions)) != len(self.jurisdictions):
            raise ValueError("jurisdictions must be unique")
        return self


class MatchExplanation(ProductModel):
    """Why a candidate was returned; never a clinical-equivalence claim."""

    method: MatchMethod
    matched_value: NonBlank
    normalized_query: NonBlank
    establishes_equivalence: Literal[False] = False


class ConceptSummary(ProductModel):
    concept_id: NonBlank
    preferred_name: NonBlank
    concept_type: NonBlank
    jurisdictions: tuple[JurisdictionCode, ...] = ()
    explanation: MatchExplanation


class ConceptIdentifier(ProductModel):
    system: NonBlank
    value: NonBlank


class ConceptName(ProductModel):
    name: NonBlank
    name_type: NonBlank


class ConceptDetail(ProductModel):
    concept_id: NonBlank
    preferred_name: NonBlank
    concept_type: NonBlank
    identifiers: tuple[ConceptIdentifier, ...] = ()
    names: tuple[ConceptName, ...] = ()
    jurisdictions: tuple[JurisdictionCode, ...] = ()


class JurisdictionSummary(ProductModel):
    jurisdiction: JurisdictionCode
    source_count: int = Field(ge=0)
    concept_count: int = Field(ge=0)


class SourceSummary(ProductModel):
    source_id: NonBlank
    jurisdiction: JurisdictionCode
    authority: NonBlank
    regulatory_system: bool
    funding_system: bool


class Terminology(ProductModel):
    """Source-native terminology retained beside canonical mapping."""

    native_code: NonBlank
    native_label: NonBlank
    native_system: NonBlank
    canonical_code: NonBlank | None = None
    canonical_label: NonBlank | None = None
    canonical_system: NonBlank | None = None

    @model_validator(mode="after")
    def canonical_fields_are_atomic(self) -> Self:
        canonical = (
            self.canonical_code,
            self.canonical_label,
            self.canonical_system,
        )
        if any(value is not None for value in canonical) and not all(
            value is not None for value in canonical
        ):
            raise ValueError(
                "canonical code, label, and system must be supplied together",
            )
        return self


class ProvenanceLink(ProductModel):
    source_id: NonBlank
    source_uri: NonBlank
    retrieved_at: AwareDatetime
    source_version: NonBlank | None = None
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = (
        None
    )
    transformation_id: NonBlank | None = None


class Uncertainty(ProductModel):
    level: UncertaintyLevel
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: NonBlank | None = None

    @model_validator(mode="after")
    def qualified_uncertainty_has_reason(self) -> Self:
        if (
            self.level
            in {
                UncertaintyLevel.MEDIUM,
                UncertaintyLevel.HIGH,
                UncertaintyLevel.UNKNOWN,
            }
            and self.reason is None
        ):
            raise ValueError(
                "material or unknown uncertainty requires a reason"
            )
        return self


class ComparisonValidityDimension(ProductModel):
    """One evidence-bearing validity dimension, without a clinical claim."""

    state: ComparisonDimensionState
    left_value: NonBlank | None = None
    right_value: NonBlank | None = None
    evidence_ids: tuple[NonBlank, ...] = ()

    @model_validator(mode="after")
    def evidence_supports_observed_state(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("comparison evidence identifiers must be unique")
        if self.state in {
            ComparisonDimensionState.ALIGNED,
            ComparisonDimensionState.COMPATIBLE,
            ComparisonDimensionState.MISMATCH,
        }:
            if self.left_value is None or self.right_value is None:
                raise ValueError(
                    "observed comparison states require both values"
                )
            if not self.evidence_ids:
                raise ValueError("observed comparison states require evidence")
        return self


class ComparisonValidityDimensions(ProductModel):
    granularity: ComparisonValidityDimension
    indication: ComparisonValidityDimension
    population: ComparisonValidityDimension
    mapping: ComparisonValidityDimension
    normalization: ComparisonValidityDimension


class ComparisonValidity(ProductModel):
    """Fail-closed fitness verdict for a status comparison only."""

    schema_id: Literal["global-medicines-atlas.comparison-validity"] = (
        "global-medicines-atlas.comparison-validity"
    )
    schema_version: Literal[1] = 1
    left_subject_id: NonBlank
    right_subject_id: NonBlank
    outcome: ComparisonValidityOutcome
    dimensions: ComparisonValidityDimensions
    material_mismatches: tuple[NonBlank, ...] = ()
    explanation: NonBlank
    establishes_medicine_equivalence: Literal[False] = False
    establishes_substitutability: Literal[False] = False
    establishes_therapeutic_interchangeability: Literal[False] = False
    establishes_equal_benefit: Literal[False] = False

    @model_validator(mode="after")
    def verdict_matches_dimensions(self) -> Self:
        if self.left_subject_id == self.right_subject_id:
            raise ValueError("comparison subjects must be distinct")
        states = {
            name: dimension.state
            for name, dimension in (
                ("granularity", self.dimensions.granularity),
                ("indication", self.dimensions.indication),
                ("population", self.dimensions.population),
                ("mapping", self.dimensions.mapping),
                ("normalization", self.dimensions.normalization),
            )
        }
        mismatches = tuple(
            name
            for name, state in states.items()
            if state is ComparisonDimensionState.MISMATCH
        )
        if self.material_mismatches != mismatches:
            raise ValueError(
                "material mismatches must exactly match dimensions"
            )
        if mismatches:
            expected = ComparisonValidityOutcome.INAPPROPRIATE_COMPARISON
        elif ComparisonDimensionState.UNKNOWN in states.values():
            expected = ComparisonValidityOutcome.INSUFFICIENT_EVIDENCE
        elif ComparisonDimensionState.COMPATIBLE in states.values():
            expected = ComparisonValidityOutcome.VALID_WITH_CAVEATS
        else:
            expected = ComparisonValidityOutcome.VALID
        if self.outcome is not expected:
            raise ValueError("comparison outcome does not match dimensions")
        return self


class ProductConclusion(ProductModel):
    """One jurisdiction and one evidence dimension; never a merged status."""

    concept_id: NonBlank
    jurisdiction: JurisdictionCode
    dimension: EvidenceDimension
    state: ProductState
    status_code: NonBlank | None = None
    terminology: Terminology
    provenance: tuple[ProvenanceLink, ...] = ()
    evidence_availability: EvidenceAvailability
    evidence_unavailable_reason: NonBlank | None = None
    uncertainty: Uncertainty
    valid_time: AsOfClocks

    @model_validator(mode="after")
    def evidence_is_explicit(self) -> Self:
        if self.evidence_availability is EvidenceAvailability.AVAILABLE:
            if not self.provenance:
                raise ValueError(
                    "available evidence requires at least one provenance link",
                )
            if self.evidence_unavailable_reason is not None:
                raise ValueError(
                    "available evidence cannot have an unavailable reason",
                )
        elif self.evidence_availability is EvidenceAvailability.UNAVAILABLE:
            if self.provenance:
                raise ValueError(
                    "unavailable evidence cannot include provenance links",
                )
            if self.evidence_unavailable_reason is None:
                raise ValueError(
                    "unavailable evidence requires an explicit reason",
                )
        elif self.evidence_unavailable_reason is not None:
            raise ValueError(
                "not-required evidence cannot have an unavailable reason",
            )

        if (
            self.state
            in {
                ProductState.CONFIRMED,
                ProductState.INFERRED,
                ProductState.CONFLICTING,
            }
            and self.evidence_availability is not EvidenceAvailability.AVAILABLE
        ):
            raise ValueError(f"{self.state} conclusions require evidence")
        if (
            self.state
            in {
                ProductState.UNKNOWN,
                ProductState.NOT_COVERED,
            }
            and self.status_code is not None
        ):
            raise ValueError(
                "unknown and not-covered conclusions cannot imply a status",
            )
        return self


class CoverageItem(ProductModel):
    jurisdiction: JurisdictionCode
    dimension: EvidenceDimension
    state: ProductState
    covered_count: int = Field(ge=0)
    denominator: int | None = Field(default=None, ge=0)
    provenance: tuple[ProvenanceLink, ...] = ()
    valid_time: AsOfClocks

    @model_validator(mode="after")
    def count_does_not_exceed_denominator(self) -> Self:
        if (
            self.denominator is not None
            and self.covered_count > self.denominator
        ):
            raise ValueError("covered_count cannot exceed denominator")
        return self


class EvidenceItem(ProductModel):
    assertion_id: NonBlank
    concept_id: NonBlank
    jurisdiction: JurisdictionCode
    dimension: EvidenceDimension
    state: ProductState
    status_code: NonBlank
    terminology: Terminology
    provenance: ProvenanceLink
    uncertainty: Uncertainty
    valid_time: AsOfClocks


class PageMetadata(ProductModel):
    limit: int = Field(ge=1, le=MAX_PAGE_SIZE)
    returned: int = Field(ge=0, le=MAX_PAGE_SIZE)
    next_cursor: CursorToken | None = None

    @model_validator(mode="after")
    def returned_fits_page(self) -> Self:
        if self.returned > self.limit:
            raise ValueError("returned count cannot exceed page limit")
        return self


class ResponseMetadata(ProductModel):
    api_version: Literal["v1"] = API_VERSION
    evidence_version: Literal["0.6"] = PRODUCT_EVIDENCE_VERSION
    generated_at: AwareDatetime
    clocks: AsOfClocks
    page: PageMetadata


class DiscoveryMetadata(ProductModel):
    api_version: Literal["v1"] = API_VERSION
    generated_at: AwareDatetime
    page: PageMetadata


class ConceptSearchResponse(ProductModel):
    metadata: DiscoveryMetadata
    concepts: tuple[ConceptSummary, ...]

    @model_validator(mode="after")
    def page_matches_payload(self) -> Self:
        if self.metadata.page.returned != len(self.concepts):
            raise ValueError("page returned count must match concepts")
        return self


class ComparisonResponse(ProductModel):
    metadata: ResponseMetadata
    conclusions: tuple[ProductConclusion, ...]
    validity: tuple[ComparisonValidity, ...] = ()

    @model_validator(mode="after")
    def page_matches_payload(self) -> Self:
        if self.metadata.page.returned != len(self.conclusions):
            raise ValueError("page returned count must match conclusions")
        return self


class CoverageResponse(ProductModel):
    metadata: ResponseMetadata
    coverage: tuple[CoverageItem, ...]

    @model_validator(mode="after")
    def page_matches_payload(self) -> Self:
        if self.metadata.page.returned != len(self.coverage):
            raise ValueError("page returned count must match coverage")
        return self


class EvidenceResponse(ProductModel):
    metadata: ResponseMetadata
    evidence: tuple[EvidenceItem, ...]

    @model_validator(mode="after")
    def page_matches_payload(self) -> Self:
        if self.metadata.page.returned != len(self.evidence):
            raise ValueError("page returned count must match evidence")
        return self


class HealthCheck(ProductModel):
    name: NonBlank
    state: HealthState
    detail: NonBlank | None = None


class HealthResponse(ProductModel):
    api_version: Literal["v1"] = API_VERSION
    evidence_version: Literal["0.6"] = PRODUCT_EVIDENCE_VERSION
    state: HealthState
    checked_at: AwareDatetime
    checks: tuple[HealthCheck, ...] = ()


class ErrorDetail(ProductModel):
    field: NonBlank | None = None
    message: NonBlank


class ErrorEnvelope(ProductModel):
    api_version: Literal["v1"] = API_VERSION
    error: ErrorCode
    message: NonBlank
    request_id: NonBlank
    details: tuple[ErrorDetail, ...] = ()
    retryable: bool = False
