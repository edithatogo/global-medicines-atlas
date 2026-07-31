"""End-to-end contracts for accessible Atlas concept discovery."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    ComparisonResponse,
    ConceptDetail,
    ConceptSearchResponse,
    ConceptSummary,
    CoverageResponse,
    DiscoveryMetadata,
    MatchExplanation,
    MatchMethod,
    PageMetadata,
    ResponseMetadata,
)

NOW = datetime(2026, 7, 31, 12, tzinfo=UTC)


class DiscoveryService:
    def search_concepts(self, query):
        concept = ConceptSummary(
            concept_id="gma:hostile",
            preferred_name="<img src=x onerror=alert(1)> Aspirin",
            concept_type="medicinal_product",
            jurisdictions=("NZ",),
            explanation=MatchExplanation(
                method=MatchMethod.NORMALIZED_ALIAS,
                matched_value="Aspirin",
                normalized_query=query.query.lower(),
            ),
        )
        return ConceptSearchResponse(
            metadata=DiscoveryMetadata(
                generated_at=NOW,
                page=PageMetadata(limit=query.limit, returned=1),
            ),
            concepts=(concept,),
        )

    def concept_detail(self, concept_id):
        return ConceptDetail(
            concept_id=concept_id,
            preferred_name="<b>Selected Aspirin</b>",
            concept_type="medicinal_product",
            jurisdictions=("NZ",),
        )

    def comparisons(self, query):
        del query
        return ComparisonResponse(
            metadata=_response_metadata(),
            conclusions=(),
        )

    def coverage(self, query):
        del query
        return CoverageResponse(metadata=_response_metadata(), coverage=())


def _response_metadata():
    return ResponseMetadata(
        generated_at=NOW,
        clocks=AsOfClocks(valid_at=NOW, observed_at=NOW),
        page=PageMetadata(limit=50, returned=0),
    )


def test_no_javascript_search_requires_explicit_canonical_selection() -> None:
    response = TestClient(create_atlas_app(DiscoveryService())).get(
        "/",
        params={"concept_search": "aspirin", "jurisdiction": "NZ"},
    )
    soup = BeautifulSoup(response.text, "html.parser")

    assert response.status_code == 200
    assert "Medicine search results" in soup.get_text(" ", strip=True)
    assert (
        "A candidate match does not establish clinical equivalence"
        in response.text
    )
    assert soup.select_one("input[name='concept_id'][value='']")
    result = soup.select_one(".search-results a")
    assert result is not None
    assert "concept_id=gma%3Ahostile" in result["href"]
    assert "<img" not in response.text
    assert "&lt;img" in response.text
    assert "Comparison results" not in response.text


def test_explicit_selection_shows_visible_name_and_canonical_identifier() -> (
    None
):
    response = TestClient(create_atlas_app(DiscoveryService())).get(
        "/",
        params={
            "concept_id": "gma:hostile",
            "concept_search": "Aspirin",
            "jurisdiction": "NZ",
        },
    )
    soup = BeautifulSoup(response.text, "html.parser")

    assert response.status_code == 200
    assert "Comparison results for <b>Selected Aspirin</b>" in soup.get_text(
        " ", strip=True
    )
    code = soup.select_one("code")
    assert code is not None
    assert code.get_text() == "gma:hostile"
    assert "<b>Selected Aspirin</b>" not in response.text
    assert "&lt;b&gt;Selected Aspirin&lt;/b&gt;" in response.text


def test_combobox_script_contract_covers_keyboard_status_and_safe_rendering() -> (
    None
):
    root = Path(__file__).parents[1]
    script = (
        root / "src/global_medicines_atlas/static/atlas-autocomplete.js"
    ).read_text(encoding="utf-8")
    response = TestClient(create_atlas_app(DiscoveryService())).get("/")
    soup = BeautifulSoup(response.text, "html.parser")

    combobox = soup.select_one("[role='combobox']")
    assert combobox is not None
    assert combobox["aria-autocomplete"] == "list"
    assert soup.select_one("[role='listbox']")
    assert soup.select_one("[role='status'][aria-live='polite']")
    for key in ("ArrowDown", "ArrowUp", "Enter", "Escape"):
        assert f'event.key === "{key}"' in script
    assert "textContent =" in script
    assert "innerHTML" not in script
    assert "fetch(" not in script
    assert 'selected.value = ""' in script
