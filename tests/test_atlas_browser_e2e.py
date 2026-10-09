"""Browser checks for keyboard access to atlas evidence and uncertainty."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Thread
from time import monotonic, sleep
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlsplit

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.historical_change import (
    HistoricalChangeService,
    compare_historical_snapshots,
)
from global_medicines_atlas.historical_comparison import (
    NativeField,
    NativeRow,
    NativeSnapshot,
)
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    ComparisonQuery,
    ComparisonResponse,
    ConceptDetail,
    ConceptSearchQuery,
    ConceptSearchResponse,
    ConceptSummary,
    CoverageItem,
    CoverageQuery,
    CoverageResponse,
    DiscoveryMetadata,
    EvidenceAvailability,
    EvidenceContext,
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
    from playwright.sync_api import Page, Route

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


@contextmanager
def _serve_atlas_on_loopback() -> Iterator[str]:
    """Run the fixture Atlas through a real HTTP server on an ephemeral port."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_atlas_app(AtlasFixtureService()),
            host="127.0.0.1",
            port=port,
            lifespan="off",
            access_log=False,
            log_level="error",
        )
    )
    thread = Thread(
        target=server.run,
        kwargs={"sockets": [listener]},
        daemon=True,
    )
    thread.start()
    deadline = monotonic() + 10
    while not server.started and thread.is_alive() and monotonic() < deadline:
        sleep(0.01)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("The synthetic Atlas ASGI server failed to stop after startup")
        listener.close()
        raise RuntimeError("The synthetic Atlas ASGI server did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("The synthetic Atlas ASGI server did not stop")
        listener.close()


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
            evidence_context=EvidenceContext(
                schema_era="fixture-v1",
                comparison_cohort="synthetic",
                entity_granularity="medicine_item",
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
        item = CoverageItem(
            jurisdiction="NZ",
            dimension=EvidenceDimension.REGULATORY,
            state=ProductState.UNKNOWN,
            covered_count=0,
            evidence_context=EvidenceContext(
                schema_era="fixture-v1",
                comparison_cohort="synthetic",
                entity_granularity="coverage_record",
            ),
            valid_time=AsOfClocks(
                valid_at=query.valid_at, observed_at=query.observed_at
            ),
        )
        return CoverageResponse(
            metadata=ResponseMetadata(
                generated_at=NOW,
                clocks=AsOfClocks(
                    valid_at=query.valid_at,
                    observed_at=query.observed_at,
                ),
                page=PageMetadata(limit=query.limit, returned=1),
            ),
            coverage=(item,),
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


def _route_test_client_requests(page: Page, client: TestClient) -> None:
    """Serve browser navigations and asset requests through the ASGI client."""
    base_url = "http://atlas.test"

    def fulfill_from_client(route: Route) -> None:
        request = route.request
        parsed_url = urlsplit(request.url)
        path = parsed_url.path
        if parsed_url.query:
            path = f"{path}?{parsed_url.query}"
        response = client.get(path)
        route.fulfill(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    page.route(f"{base_url}/**", fulfill_from_client)


def _navigate_to_history_page(page: Page, client: TestClient) -> None:
    """Follow the real Atlas link after the browser loads its app assets."""
    requested_paths: list[str] = []
    asset_statuses: dict[str, int] = {}
    page.on(
        "request",
        lambda request: requested_paths.append(urlsplit(request.url).path),
    )
    page.on(
        "response",
        lambda response: asset_statuses.update({
            urlsplit(response.url).path: response.status
        }),
    )
    _route_test_client_requests(page, client)
    home_response = page.goto("http://atlas.test/?concept_search=example")
    assert home_response is not None
    assert home_response.status == 200
    assert "/static/atlas.css" in requested_paths
    assert "/static/atlas-autocomplete.js" in requested_paths
    assert asset_statuses["/static/atlas.css"] == 200
    assert asset_statuses["/static/atlas-autocomplete.js"] == 200
    medicine_search = page.get_by_role(
        "combobox", name="Medicine name or identifier"
    )
    medicine_search.fill("example")
    assert (
        page
        .get_by_role("status")
        .inner_text()
        .startswith("1 medicine option available")
    )
    history_link = page.get_by_role("link", name="Review historical changes")
    assert history_link.get_attribute("href") == "/history"
    history_link.click()
    assert page.url == "http://atlas.test/history"
    assert page.locator("link[rel='stylesheet']").count() == 1
    assert (
        page.locator(".skip-link").evaluate(
            "element => getComputedStyle(element).position"
        )
        == "absolute"
    )


@pytest.mark.e2e
@pytest.mark.timeout(90)
def test_keyboard_medicine_selection_and_evidence_review() -> None:
    """Keyboard users can select a concept and inspect uncertainty evidence."""
    client = TestClient(create_atlas_app(AtlasFixtureService()))
    search_html = client.get("/", params={"concept_search": "example"}).text
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            _exercise_keyboard_evidence_flow(page, client, search_html)
        finally:
            browser.close()


@pytest.mark.e2e
@pytest.mark.timeout(90)
def test_synthetic_atlas_renders_through_loopback_asgi_server() -> None:
    """Exercise page, assets, and evidence over a real local HTTP socket."""
    params = urlencode({
        "concept_id": "rx:fixture",
        "jurisdiction": "NZ",
        "valid_at": NOW.isoformat(),
        "observed_at": NOW.isoformat(),
    })
    with (
        _serve_atlas_on_loopback() as base_url,
        sync_playwright() as playwright,
    ):
        browser = playwright.chromium.launch()
        page = browser.new_page()
        observed_responses: dict[str, int] = {}
        requested_urls: list[str] = []
        page.on(
            "request",
            lambda request: requested_urls.append(request.url),
        )
        page.on(
            "response",
            lambda response: observed_responses.update({
                urlsplit(response.url).path: response.status
            }),
        )
        try:
            response = page.goto(f"{base_url}/?{params}")
            assert response is not None
            assert response.status == 200
            assert page.get_by_role(
                "heading", name="Global Medicines Atlas"
            ).is_visible()
            assert page.get_by_text(
                "Canonical medicine identifier: rx:fixture"
            ).is_visible()
            assert page.locator(".result-card").count() == 1
            assert (
                "Status: Unknown" in page.locator(".result-card").inner_text()
            )
            assert observed_responses["/static/atlas.css"] == 200
            assert observed_responses["/static/atlas-autocomplete.js"] == 200
            assert requested_urls
            assert all(url.startswith(base_url) for url in requested_urls)
        finally:
            browser.close()


@pytest.mark.e2e
@pytest.mark.timeout(90)
def test_keyboard_history_timeline_preserves_snapshot_evidence() -> None:
    """Keyboard users can inspect native before/after history evidence."""
    previous = NativeSnapshot(
        source_id="synthetic-mbs",
        table="descriptions",
        dimension="service_benefit",
        schema_era="fixture-v1",
        identity_profile="mbs-description-record",
        scope_id="synthetic-history-fixture",
        source_revision="fixture-revision-previous",
        source_path="fixtures/previous.xml",
        b1_sha256="a" * 64,
        b2_sha256="b" * 64,
        observed_at=NOW,
        cohort="synthetic",
        declared_rows=1,
        complete=True,
        rows=(
            NativeRow(
                native_id="mbs:001:00",
                occurrence_id="001",
                fields=(
                    NativeField(
                        name="Description",
                        state="value",
                        value="Prior synthetic service",
                    ),
                    NativeField(name="Benefit", state="missing"),
                ),
            ),
        ),
    )
    current = NativeSnapshot(
        source_id="synthetic-mbs",
        table="descriptions",
        dimension="service_benefit",
        schema_era="fixture-v1",
        identity_profile="mbs-description-record",
        scope_id="synthetic-history-fixture",
        source_revision="fixture-revision-current",
        source_path="fixtures/current.xml",
        b1_sha256="c" * 64,
        b2_sha256="d" * 64,
        observed_at=NOW,
        cohort="synthetic",
        declared_rows=1,
        complete=True,
        rows=(
            NativeRow(
                native_id="mbs:001:00",
                occurrence_id="001",
                fields=(
                    NativeField(
                        name="Description",
                        state="value",
                        value="Current synthetic service",
                    ),
                    NativeField(name="Benefit", state="null"),
                ),
            ),
        ),
    )
    history = HistoricalChangeService((
        compare_historical_snapshots(previous, current),
    ))
    client = TestClient(
        create_atlas_app(AtlasFixtureService(), historical_changes=history)
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            _navigate_to_history_page(page, client)

            skip_link = page.get_by_role(
                "link", name="Skip to historical changes"
            )
            skip_link.focus()
            skip_link.press("Enter")
            assert page.evaluate("document.activeElement.id") == (
                "history-results"
            )
            page.keyboard.press("Tab")
            assert (
                page.evaluate(
                    "document.activeElement.getAttribute('aria-label')"
                )
                == "Source snapshot identity"
            )

            history_region = page.get_by_role(
                "region", name="Source snapshot identity"
            )
            snapshot_rows = history_region.locator("tbody tr")
            assert snapshot_rows.count() == 2
            earlier_row = snapshot_rows.nth(0).inner_text()
            later_row = snapshot_rows.nth(1).inner_text()
            assert "Earlier" in earlier_row
            assert "fixture-revision-previous" in earlier_row
            assert "fixtures/previous.xml" in earlier_row
            assert "Later" in later_row
            assert "fixture-revision-current" in later_row
            assert "fixtures/current.xml" in later_row
            assert "synthetic-mbs" in earlier_row
            assert "synthetic-mbs" in later_row
            assert (
                "absence interpretation: unknown"
                in page.locator("main").inner_text()
            )

            observations = " ".join(
                " ".join(item.split())
                for item in page.locator("main ul li").all_inner_texts()
            )
            assert "Prior synthetic service" in observations
            assert "Current synthetic service" in observations
            assert "Earlier observation missing" in observations
            assert "Later observation null" in observations
        finally:
            browser.close()


def _exercise_keyboard_evidence_flow(
    page: Page, client: TestClient, search_html: str
) -> None:
    """Run the interaction checks inside one explicitly bounded browser."""
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
    context = card.locator("[data-evidence-context]")
    assert "Schema era" in context.inner_text()
    assert "fixture-v1" in context.inner_text()
    assert "Synthetic" in context.inner_text()
    summary = page.get_by_text("Review source evidence")
    summary.focus()
    summary.press("Enter")
    assert page.locator("details").get_attribute("open") is not None
    evidence_link = page.get_by_role("link", name="Synthetic public evidence")
    assert evidence_link.is_visible()
    assert evidence_link.get_attribute("href") == (
        "https://fixtures.invalid/evidence"
    )
    coverage_context = page.locator("table [data-evidence-context]")
    coverage_row = page.locator("table tbody tr").filter(
        has=page.locator("[data-state='unknown']")
    )
    assert coverage_row.count() == 1
    assert "Status: Unknown" in coverage_row.inner_text()
    assert (
        "0 observed; denominator unknown, so no percentage is calculated"
        in coverage_row.inner_text()
    )
    assert "%" not in coverage_row.inner_text()
    assert "Schema era" in coverage_context.inner_text()
    assert "fixture-v1" in coverage_context.inner_text()
    assert "Coverage record" in coverage_context.inner_text()
