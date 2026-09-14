"""Accessible, server-rendered atlas for evidence-backed comparisons."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Protocol
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .product_contracts import (
    ComparisonQuery,
    ComparisonResponse,
    ConceptDetail,
    ConceptSearchQuery,
    ConceptSearchResponse,
    CoverageItem,
    CoverageQuery,
    CoverageResponse,
    EvidenceDimension,
    ProductConclusion,
    ProvenanceLink,
)

_PACKAGE_ROOT = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=_PACKAGE_ROOT / "templates")
_DEFAULT_JURISDICTIONS = ("NZ", "AU", "US")


class AtlasQueryService(Protocol):
    """Narrow read-only service required by the atlas."""

    def comparisons(self, query: ComparisonQuery) -> ComparisonResponse: ...

    def coverage(self, query: CoverageQuery) -> CoverageResponse: ...

    def search_concepts(
        self, query: ConceptSearchQuery
    ) -> ConceptSearchResponse: ...

    def concept_detail(self, concept_id: str) -> ConceptDetail: ...


def _safe_source_uri(uri: str) -> str | None:
    parsed = urlsplit(uri)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return uri
    return None


def _evidence_links(
    conclusion: ProductConclusion,
) -> tuple[dict[str, str | None], ...]:
    if conclusion.provenance:
        return tuple(_evidence_link(item) for item in conclusion.provenance)
    return (
        {
            "label": "Evidence availability explanation",
            "uri": None,
            "detail": conclusion.evidence_unavailable_reason
            or "No source assertion is available for this conclusion.",
        },
    )


def _evidence_link(item: ProvenanceLink) -> dict[str, str | None]:
    return {
        "label": item.source_id,
        "uri": _safe_source_uri(item.source_uri),
        "detail": item.source_uri,
    }


def _conclusion_view(conclusion: ProductConclusion) -> dict[str, object]:
    return {
        "jurisdiction": conclusion.jurisdiction,
        "dimension": conclusion.dimension.value,
        "state": conclusion.state.value,
        "state_label": conclusion.state.value.replace("_", " "),
        "status_code": conclusion.status_code,
        "native_code": conclusion.terminology.native_code,
        "native_label": conclusion.terminology.native_label,
        "native_system": conclusion.terminology.native_system,
        "canonical_code": conclusion.terminology.canonical_code,
        "canonical_label": conclusion.terminology.canonical_label,
        "canonical_system": conclusion.terminology.canonical_system,
        "uncertainty": conclusion.uncertainty.level.value,
        "uncertainty_reason": conclusion.uncertainty.reason,
        "valid_at": conclusion.valid_time.valid_at.isoformat(),
        "observed_at": conclusion.valid_time.observed_at.isoformat(),
        "evidence": _evidence_links(conclusion),
    }


def _coverage_view(item: CoverageItem) -> dict[str, object]:
    # Kept local to avoid flattening nullable denominators into percentages.
    return {
        "jurisdiction": item.jurisdiction,
        "dimension": item.dimension.value,
        "state": item.state.value,
        "state_label": item.state.value.replace("_", " "),
        "covered_count": item.covered_count,
        "denominator": item.denominator,
        "valid_at": item.valid_time.valid_at.isoformat(),
        "observed_at": item.valid_time.observed_at.isoformat(),
    }


def _jurisdictions(values: Sequence[str]) -> tuple[str, ...]:
    parsed = tuple(
        part.strip().upper()
        for value in values
        for part in value.split(",")
        if part.strip()
    )
    return parsed or _DEFAULT_JURISDICTIONS


def _concept_views(
    response: ConceptSearchResponse,
) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "concept_id": item.concept_id,
            "preferred_name": item.preferred_name,
            "concept_type": item.concept_type,
            "match_method": item.explanation.method.value.replace("_", " "),
        }
        for item in response.concepts
    )


def create_atlas_app(service: AtlasQueryService) -> FastAPI:
    """Create an atlas app with an explicitly injected read-only service."""
    app = FastAPI(
        title="Global Medicines Atlas",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.mount(
        "/static",
        StaticFiles(directory=_PACKAGE_ROOT / "static"),
        name="static",
    )

    @app.get("/", response_class=HTMLResponse)
    def atlas(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        concept_id: Annotated[str | None, Query(max_length=512)] = None,
        concept_search: Annotated[str | None, Query(max_length=200)] = None,
        jurisdiction: Annotated[list[str] | None, Query()] = None,
        valid_at: Annotated[datetime | None, Query()] = None,
        observed_at: Annotated[datetime | None, Query()] = None,
    ) -> HTMLResponse:
        selected_valid_at = valid_at or datetime.now(UTC)
        selected_observed_at = observed_at or datetime.now(UTC)
        selected = _jurisdictions(jurisdiction or ())
        conclusions: tuple[dict[str, object], ...] = ()
        coverage: tuple[dict[str, object], ...] = ()
        concept_options: tuple[dict[str, str], ...] = ()
        selected_concept: ConceptDetail | None = None
        error: str | None = None
        search_error: str | None = None
        if concept_search:
            try:
                search_response = service.search_concepts(
                    ConceptSearchQuery(
                        query=concept_search,
                        jurisdictions=selected,
                        limit=20,
                    )
                )
            except (ValidationError, ValueError) as exc:
                search_error = f"The medicine search is invalid: {exc}"
            else:
                concept_options = _concept_views(search_response)
        if concept_id:
            try:
                selected_concept = service.concept_detail(concept_id)
                comparison = service.comparisons(
                    ComparisonQuery(
                        concept_id=concept_id,
                        jurisdictions=selected,
                        dimensions=(
                            EvidenceDimension.REGULATORY,
                            EvidenceDimension.FUNDING,
                        ),
                        valid_at=selected_valid_at,
                        observed_at=selected_observed_at,
                    )
                )
                coverage_response = service.coverage(
                    CoverageQuery(
                        jurisdictions=selected,
                        dimensions=(
                            EvidenceDimension.REGULATORY,
                            EvidenceDimension.FUNDING,
                        ),
                        valid_at=selected_valid_at,
                        observed_at=selected_observed_at,
                    )
                )
            except (ValidationError, ValueError) as exc:
                error = f"The comparison request is invalid: {exc}"
            else:
                conclusions = tuple(
                    _conclusion_view(item) for item in comparison.conclusions
                )
                coverage = tuple(
                    _coverage_view(item) for item in coverage_response.coverage
                )

        return _TEMPLATES.TemplateResponse(
            request=request,
            name="atlas.html",
            context={
                "concept_id": concept_id or "",
                "concept_search": concept_search or "",
                "concept_options": concept_options,
                "selected_concept": selected_concept,
                "search_error": search_error,
                "jurisdictions": ",".join(selected),
                "valid_at": selected_valid_at.isoformat(),
                "observed_at": selected_observed_at.isoformat(),
                "conclusions": conclusions,
                "coverage": coverage,
                "error": error,
            },
        )

    return app
