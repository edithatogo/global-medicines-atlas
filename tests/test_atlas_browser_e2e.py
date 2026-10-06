"""Browser checks for keyboard access to atlas evidence and uncertainty."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    ComparisonQuery,
    ComparisonResponse,
    ConceptDetail,
    ConceptSearchQuery,
    ConceptSearchResponse,
    ConceptSummary,
    CoverageQuery,
    CoverageResponse,
    DiscoveryMetadata,
    EvidenceAvailability,
    EvidenceDimension,
    MatchExplanation,
    MatchMethod,
    PageMetadata,
    ProductConclusion,
    ProductState,
    ProvenanceLink,
    ResponseMetadata,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


class AtlasFixtureService:
    """Small synthetic service with one medicine and explicit missing coverage."""

    def concept_detail(self, concept_id: str) -> ConceptDetail:
        return ConceptDetail(
            concept_id=concept_id,
            preferred_name="Example medicine",
            concept_type="medicinal_product",
        )

    def search_concepts(
        self, query: ConceptSearchQuery
    ) -> ConceptSearchResponse:
        return ConceptSearchResponse(
            metadata=DiscoveryMetadata(
                generated_at=NOW,
                page=PageMetadata(limit=query.limit, returned=1),
            ),
            concepts=(
                ConceptSummary(
                    concept_id="rx:fixture",
                    preferred_name="Example medicine",
                    concept_type="medicinal_product",
                    jurisdictions=("NZ",),
                    explanation=MatchExplanation(
                        method=MatchMethod.NORMALIZED_PREFERRED_NAME,
                        matched_value="Example medicine",
                        normalized_query=query.query.casefold(),
                    ),
                ),
            ),
        )

    def comparisons(self, query: ComparisonQuery) -> ComparisonResponse:
        conclusion = ProductConclusion(
            concept_id=query.concept_id,
            jurisdiction="NZ",
            dimension=EvidenceDimension.REGULATORY,
            state=ProductState.UNKNOWN,
            terminology=Terminology(
                native_code="not-covered",
                native_label="Not covered in this synthetic fixture",
                native_system="fixture",
                canonical_code=query.concept_id,
                canonical_label="Example medicine",
                canonical_system="atlas",
            ),
            provenance=(
                ProvenanceLink(
                    source_id="Synthetic public evidence",
                    source_uri="https://fixtures.invalid/evidence",
                    retrieved_at=NOW,
                ),
            ),
            evidence_availability=EvidenceAvailability.AVAILABLE,
            uncertainty=Uncertainty(
                level=UncertaintyLevel.UNKNOWN,
                reason="No source assertion is present in this fixture.",
            ),
            valid_time=AsOfClocks(
                valid_at=query.valid_at,
                observed_at=query.observed_at,
            ),
        )
        return ComparisonResponse(
            metadata=ResponseMetadata(
                generated_at=NOW,
                clocks=AsOfClocks(
                    valid_at=query.valid_at,
                    observed_at=query.observed_at,
                ),
                page=PageMetadata(limit=query.limit, returned=1),
            ),
            conclusions=(conclusion,),
        )

    def coverage(self, query: CoverageQuery) -> CoverageResponse:
        return CoverageResponse(
            metadata=ResponseMetadata(
                generated_at=NOW,
                clocks=AsOfClocks(
                    valid_at=query.valid_at,
                    observed_at=query.observed_at,
                ),
                page=PageMetadata(limit=query.limit, returned=0),
            ),
            coverage=(),
        )


def _show_response_in_browser(
    page: Page,
    client: TestClient,
    html: str,
) -> None:
    stylesheet = client.get("/static/atlas.css").text
    script = client.get("/static/atlas-autocomplete.js").text
    page.set_content(
        html.replace(
            '<link rel="stylesheet" href="/static/atlas.css">', ""
        ).replace(
            '<script src="/static/atlas-autocomplete.js" defer></script>', ""
        )
    )
    page.add_style_tag(content=stylesheet)
    page.add_script_tag(content=script)


@pytest.mark.e2e
@pytest.mark.timeout(90)
def test_keyboard_medicine_selection_and_evidence_review(page: Page) -> None:
    """Keyboard users can select a concept and inspect uncertainty evidence."""
    client = TestClient(create_atlas_app(AtlasFixtureService()))
    search_html = client.get("/", params={"concept_search": "example"}).text
    _show_response_in_browser(page, client, search_html)

    search = page.get_by_role("combobox", name="Medicine name or identifier")
    search.fill("")
    search.fill("example")
    assert (
        page
        .get_by_role("status")
        .inner_text()
        .startswith("1 medicine option available")
    )
    search.press("ArrowDown")
    assert search.get_attribute("aria-expanded") == "true"
    assert search.get_attribute("aria-activedescendant") == "concept-option-1"
    assert page.get_by_role("option").get_attribute("aria-selected") == "true"
    search.press("Enter")
    assert page.locator("input[name=concept_id]").input_value() == "rx:fixture"
    assert search.input_value() == "Example medicine"
    assert search.get_attribute("aria-expanded") == "false"
    assert (
        "Selected Example medicine" in page.get_by_role("status").inner_text()
    )

    comparison_html = client.get(
        "/",
        params={
            "concept_id": "rx:fixture",
            "jurisdiction": "NZ",
            "valid_at": NOW.isoformat(),
            "observed_at": NOW.isoformat(),
        },
    ).text
    assert "Comparison results for Example medicine" in comparison_html
    _show_response_in_browser(page, client, comparison_html)
    skip_link = page.get_by_role("link", name="Skip to comparison results")
    skip_link.focus()
    skip_link.press("Enter")
    assert page.evaluate("document.activeElement.id") == "atlas-results"

    card = page.locator("article[data-state='unknown']")
    assert "Status: Unknown" in card.inner_text()
    assert "not evidence of a negative" in card.inner_text()
    summary = page.get_by_text("Review source evidence")
    summary.focus()
    summary.press("Enter")
    assert page.locator("details").get_attribute("open") is not None
    evidence_link = page.get_by_role("link", name="Synthetic public evidence")
    assert evidence_link.is_visible()
    assert evidence_link.get_attribute("href") == (
        "https://fixtures.invalid/evidence"
    )
