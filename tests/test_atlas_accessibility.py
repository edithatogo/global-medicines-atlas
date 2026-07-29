from __future__ import annotations

from datetime import UTC, datetime

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    ComparisonResponse,
    CoverageResponse,
    EvidenceAvailability,
    EvidenceDimension,
    PageMetadata,
    ProductConclusion,
    ProductState,
    ProvenanceLink,
    ResponseMetadata,
    Terminology,
    Uncertainty,
    UncertaintyLevel,
)

NOW = datetime(2026, 7, 29, 12, tzinfo=UTC)


def _metadata(returned: int) -> ResponseMetadata:
    return ResponseMetadata(
        generated_at=NOW,
        clocks=AsOfClocks(valid_at=NOW, observed_at=NOW),
        page=PageMetadata(limit=50, returned=returned),
    )


class FakeService:
    def comparisons(self, query):
        source_uri = (
            "javascript:alert(1)"
            if query.concept_id == "unsafe"
            else "https://example.test/evidence?id=<script>"
        )
        conclusion = ProductConclusion(
            concept_id=query.concept_id,
            jurisdiction="NZ",
            dimension=EvidenceDimension.REGULATORY,
            state=ProductState.CONFIRMED,
            status_code="approved",
            terminology=Terminology(
                native_code="Medsafe approved",
                native_label="<script>alert('native')</script>",
                native_system="Medsafe",
                canonical_code="rx:1",
                canonical_label="Example medicine",
                canonical_system="atlas",
            ),
            provenance=(
                ProvenanceLink(
                    source_id="Medsafe register",
                    source_uri=source_uri,
                    retrieved_at=NOW,
                ),
            ),
            evidence_availability=EvidenceAvailability.AVAILABLE,
            uncertainty=Uncertainty(level=UncertaintyLevel.NONE, confidence=1),
            valid_time=AsOfClocks(valid_at=NOW, observed_at=NOW),
        )
        return ComparisonResponse(
            metadata=_metadata(1), conclusions=(conclusion,)
        )

    def coverage(self, _query):
        return CoverageResponse(metadata=_metadata(0), coverage=())


def test_landmark_labels_focus_and_form_structure():
    client = TestClient(create_atlas_app(FakeService()))
    response = client.get("/")
    soup = BeautifulSoup(response.text, "html.parser")

    assert response.status_code == 200
    assert soup.select_one("html[lang='en']")
    assert soup.select_one("a.skip-link[href='#atlas-results']")
    assert soup.select_one("main#atlas-results[tabindex='-1']")
    assert soup.select_one("form[method='get']")
    assert len(soup.select("label input")) == 4
    assert soup.select_one("meta[name='viewport']")
    assert "does not claim WCAG conformance" in soup.get_text(" ", strip=True)
    stylesheet = client.get("/static/atlas.css")
    assert stylesheet.status_code == 200
    assert "@media (max-width: 42rem)" in stylesheet.text
    assert ":focus-visible" in stylesheet.text


def test_results_are_semantic_textual_and_source_linked():
    response = TestClient(create_atlas_app(FakeService())).get(
        "/",
        params={
            "concept_id": "rx:1",
            "jurisdiction": "NZ",
            "valid_at": NOW.isoformat(),
            "observed_at": NOW.isoformat(),
        },
    )
    soup = BeautifulSoup(response.text, "html.parser")
    card = soup.select_one("article[data-state='confirmed']")

    assert card is not None
    assert "Status: confirmed" in card.get_text(" ", strip=True)
    assert "Source-native term" in card.get_text(" ", strip=True)
    assert "Canonical mapping" in card.get_text(" ", strip=True)
    assert len(card.select("time[datetime]")) == 2
    assert card.select_one("details summary")
    link = card.select_one("a[href^='https://example.test/evidence']")
    assert link is not None
    assert not soup.select("script")
    assert "<script>" not in response.text


def test_unsafe_evidence_scheme_is_text_not_a_clickable_link():
    response = TestClient(create_atlas_app(FakeService())).get(
        "/",
        params={
            "concept_id": "unsafe",
            "jurisdiction": "NZ",
            "valid_at": NOW.isoformat(),
            "observed_at": NOW.isoformat(),
        },
    )
    soup = BeautifulSoup(response.text, "html.parser")

    assert "javascript:alert(1)" in soup.get_text(" ", strip=True)
    assert not soup.select("a[href^='javascript:']")
