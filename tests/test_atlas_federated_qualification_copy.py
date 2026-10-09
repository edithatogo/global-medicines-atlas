"""Federated Atlas wording follows the pinned resource, not test defaults."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal, cast
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from global_medicines_atlas.atlas import AtlasQueryService, create_atlas_app
from global_medicines_atlas.platinum_benefits import BenefitsPage, BenefitsQuery
from global_medicines_atlas.platinum_identity_service import (
    UnknownPlatinumResourceError,
)
from global_medicines_atlas.platinum_structure import (
    SourceStructurePage,
    SourceStructureQuery,
)
from global_medicines_atlas.platinum_surface_contracts import (
    DatasetIdentityEnvelope,
    DatasetIdentityV2Envelope,
)

NOW = datetime(2026, 10, 9, tzinfo=UTC)
RESOURCE = "au.mbs.services"

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route


def _benefits_page(
    comparison_cohort: Literal["current", "synthetic"] = "current",
) -> BenefitsPage:
    return BenefitsPage(
        status="available",
        identity=DatasetIdentityEnvelope(
            resource_id=RESOURCE,
            dataset="global-medicines-atlas/australian-benefits",
            revision="a" * 40,
            path="silver/mbs-services.parquet",
            object_sha256="b" * 64,
            byte_count=128,
            contract_sha256="c" * 64,
            semantic_manifest_sha256="d" * 64,
            jurisdiction="AU",
            semantic_dimension="service_benefit",
            entity_granularity="service_item",
            source_id="au-mbs",
            acquisition_id="mbs-acquisition-1",
            layer="silver",
            schema_era="mbs-2025-v1",
            comparison_cohort=comparison_cohort,
            effective_date="2025-07-01",
            retrieved_at=NOW,
            cache_expires_at=NOW + timedelta(hours=1),
            capabilities=("exact_v4_resolution", "anonymous_verified_read"),
            coverage_state="not_declared",
            comparison_validity="not_evaluated",
            product_admitted=True,
            rows_queried=False,
        ),
        rows=({"item_code": "100"},),
        query_sha256="e" * 64,
        window_sha256="f" * 64,
        page_sha256="1" * 64,
        receipt_sha256="2" * 64,
        reason=None,
        next_cursor=None,
        window_rows=1,
        window_complete=True,
    )


def _structure_page(
    comparison_cohort: Literal["current", "synthetic"] = "current",
) -> SourceStructurePage:
    return SourceStructurePage(
        status="available",
        identity=DatasetIdentityV2Envelope(
            resource_id=RESOURCE,
            dataset="global-medicines-atlas/australian-benefits",
            revision="a" * 40,
            path="gold/mbs-edges.parquet",
            object_sha256="b" * 64,
            byte_count=128,
            contract_sha256="c" * 64,
            semantic_manifest_sha256="d" * 64,
            jurisdiction="AU",
            semantic_dimension="source_structure",
            entity_granularity="evidence_edge",
            source_id="au-mbs",
            acquisition_id="mbs-acquisition-1",
            layer="gold",
            schema_era="mbs-2025-v1",
            comparison_cohort=comparison_cohort,
            effective_date="2025-07-01",
            retrieved_at=NOW,
            cache_expires_at=NOW + timedelta(hours=1),
            capabilities=("exact_v4_resolution", "anonymous_verified_read"),
            coverage_state="not_declared",
            comparison_validity="not_evaluated",
            product_admitted=True,
            rows_queried=False,
        ),
        rows=({"kind": "source_contains_entity"},),
        query_sha256="e" * 64,
        query_receipt_sha256="2" * 64,
        query_receipt_json="{}",
        reason=None,
    )


@dataclass
class BenefitsLookup:
    comparison_cohort: Literal["current", "synthetic"] = "current"

    def query(self, resource_id: str, query: BenefitsQuery) -> BenefitsPage:
        del query
        if resource_id != RESOURCE:
            raise UnknownPlatinumResourceError
        return _benefits_page(self.comparison_cohort)


@dataclass
class StructureLookup:
    comparison_cohort: Literal["current", "synthetic"] = "current"

    def query(
        self, resource_id: str, query: SourceStructureQuery
    ) -> SourceStructurePage:
        del query
        if resource_id != RESOURCE:
            raise UnknownPlatinumResourceError
        return _structure_page(self.comparison_cohort)


def test_benefits_view_does_not_call_a_current_resource_fixture_only() -> None:
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_benefits=BenefitsLookup(),
        )
    )

    response = client.get(
        "/federated/benefits",
        params={"resource_id": RESOURCE, "columns": "item_code"},
    )

    assert response.status_code == 200
    assert "Comparison cohort</dt><dd>current" in response.text
    assert "fixture-qualified view" not in response.text
    assert "Coverage is not declared here" in response.text


def test_structure_view_does_not_call_a_current_resource_synthetic() -> None:
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=StructureLookup(),
        )
    )

    response = client.get(
        "/federated/source-structure",
        params={"resource_id": RESOURCE, "columns": "kind"},
    )

    assert response.status_code == 200
    assert "Comparison cohort</dt><dd>current" in response.text
    assert "This synthetic qualification" not in response.text
    assert "Coverage is not declared here" in response.text


def test_benefits_view_retains_synthetic_resource_limits() -> None:
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_benefits=BenefitsLookup(comparison_cohort="synthetic"),
        )
    )

    response = client.get(
        "/federated/benefits",
        params={"resource_id": RESOURCE, "columns": "item_code"},
    )

    assert response.status_code == 200
    assert "synthetic qualification fixtures" in response.text
    assert "not populated production source data" in response.text


def test_structure_view_retains_synthetic_resource_limits() -> None:
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=StructureLookup(
                comparison_cohort="synthetic"
            ),
        )
    )

    response = client.get(
        "/federated/source-structure",
        params={"resource_id": RESOURCE, "columns": "kind"},
    )

    assert response.status_code == 200
    assert "synthetic qualification fixtures" in response.text
    assert "not populated production source data" in response.text


def _route_client_requests(page: Page, client: TestClient) -> None:
    """Fulfil browser navigations and assets through the synthetic ASGI app."""
    base_url = "http://atlas.test"

    def fulfill_from_client(route: Route) -> None:
        parsed_url = urlsplit(route.request.url)
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


def _assert_atlas_assets_loaded(
    requests: list[str], responses: dict[str, int], page: Page
) -> None:
    assert "/static/atlas.css" in requests
    assert "/static/atlas-autocomplete.js" in requests
    assert responses["/static/atlas.css"] == 200
    assert responses["/static/atlas-autocomplete.js"] == 200
    assert (
        page.locator(".skip-link").evaluate(
            "element => getComputedStyle(element).position"
        )
        == "absolute"
    )


def _exercise_browser_benefits_route(page: Page) -> None:
    benefits_link = page.get_by_role(
        "link", name="Browse pinned benefit evidence"
    )
    assert benefits_link.get_attribute("href") == "/federated/benefits"
    benefits_link.click()
    assert page.url == "http://atlas.test/federated/benefits"
    assert page.get_by_role(
        "heading", name="Australian benefit evidence"
    ).is_visible()
    page.get_by_label("Resource identifier").fill(RESOURCE)
    page.get_by_label("Source columns, comma separated").fill("item_code")
    page.get_by_role("button", name="Read pinned evidence").click()
    content = page.locator("main").inner_text()
    assert "Comparison cohort" in content
    assert "current" in content
    assert "fixture-qualified view" not in content
    benefit_rows = page.get_by_role(
        "region", name="Federated evidence rows"
    ).locator("tbody tr")
    assert benefit_rows.count() == 1
    assert "100" in benefit_rows.first.inner_text()


def _exercise_browser_structure_route(page: Page) -> None:
    structure_link = page.get_by_role(
        "link", name="Browse pinned source-structure evidence"
    )
    assert structure_link.get_attribute("href") == (
        "/federated/source-structure"
    )
    structure_link.click()
    assert page.url == "http://atlas.test/federated/source-structure"
    assert page.get_by_role(
        "heading", name="Source-structure evidence"
    ).is_visible()
    page.get_by_label("Resource identifier").fill(RESOURCE)
    page.get_by_label("Source columns, comma separated").fill("kind")
    page.get_by_role("button", name="Read pinned structure").click()
    content = page.locator("main").inner_text()
    assert "Comparison cohort" in content
    assert "current" in content
    assert "This synthetic qualification" not in content
    structure_rows = page.get_by_role(
        "region", name="Source-structure evidence rows"
    ).locator("tbody tr")
    assert structure_rows.count() == 1
    assert "source_contains_entity" in structure_rows.first.inner_text()


@pytest.mark.e2e
@pytest.mark.timeout(90)
def test_browser_navigates_from_home_to_bounded_federated_evidence() -> None:
    """Users can reach and query both pinned federated views in the browser."""
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_benefits=BenefitsLookup(),
            federated_source_structure=StructureLookup(),
        )
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        requests: list[str] = []
        responses: dict[str, int] = {}
        page.on(
            "request",
            lambda request: requests.append(urlsplit(request.url).path),
        )
        page.on(
            "response",
            lambda response: responses.update({
                urlsplit(response.url).path: response.status
            }),
        )
        try:
            _route_client_requests(page, client)
            home_response = page.goto("http://atlas.test/")
            assert home_response is not None
            assert home_response.status == 200
            _assert_atlas_assets_loaded(requests, responses, page)
            _exercise_browser_benefits_route(page)

            page.goto("http://atlas.test/")
            _exercise_browser_structure_route(page)
        finally:
            browser.close()


@pytest.mark.e2e
@pytest.mark.timeout(90)
def test_browser_explains_unknown_resources_and_invalid_benefit_filters() -> (
    None
):
    """Federated form failures remain visible and actionable in the browser."""
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_benefits=BenefitsLookup(),
        )
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            _route_client_requests(page, client)
            page.goto("http://atlas.test/")
            page.get_by_role(
                "link", name="Browse pinned benefit evidence"
            ).click()
            page.get_by_label("Resource identifier").fill("au.mbs.unknown")
            with page.expect_response(
                lambda response: (
                    "/federated/benefits" in response.url
                    and response.status == 404
                )
            ):
                page.get_by_role("button", name="Read pinned evidence").click()
            unknown_alert = page.get_by_role("alert")
            assert "admitted benefits resource was not found" in (
                unknown_alert.inner_text()
            )

            page.get_by_label("Resource identifier").fill(RESOURCE)
            page.get_by_label("Optional bounded filters (JSON array)").fill(
                '[{"column":"item_code","operator":"==","value":"100"}]'
            )
            with page.expect_response(
                lambda response: (
                    "/federated/benefits" in response.url
                    and response.status == 422
                )
            ):
                page.get_by_role("button", name="Read pinned evidence").click()
            filter_alert = page.get_by_role("alert")
            assert "federated benefits query is invalid" in (
                filter_alert.inner_text()
            )
            assert (
                page
                .get_by_label("Optional bounded filters (JSON array)")
                .input_value()
                .startswith('[{"column":"item_code"')
            )
        finally:
            browser.close()
