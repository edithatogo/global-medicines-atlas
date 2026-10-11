"""Federated Atlas wording follows the pinned resource, not test defaults."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal, cast
from urllib.parse import urlsplit

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

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


def _unavailable_benefits_page(
    reason: Literal[
        "offline_cache_unavailable",
        "offline_contract_expired",
        "verified_resource_unavailable",
    ] = "offline_cache_unavailable",
) -> BenefitsPage:
    """Return a typed synthetic unavailable result."""
    payload = _benefits_page().model_dump(mode="python")
    payload.update(
        status="unavailable",
        rows=(),
        window_sha256=None,
        page_sha256=None,
        reason=reason,
        window_rows=0,
        window_complete=False,
    )
    return BenefitsPage.model_validate(payload)


def _unavailable_structure_page(
    reason: Literal[
        "offline_cache_unavailable",
        "offline_contract_expired",
        "verified_resource_unavailable",
        "future_internal_reason",
    ],
) -> SourceStructurePage:
    payload = _structure_page().model_dump(mode="python")
    payload.update(
        status="unavailable",
        rows=(),
        reason=reason,
        query_receipt_json=json.dumps(
            {"reason": reason}, sort_keys=True, separators=(",", ":")
        ),
    )
    return SourceStructurePage.model_validate(payload)


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
    unavailable: bool = False
    unavailable_reason: Literal[
        "offline_cache_unavailable",
        "offline_contract_expired",
        "verified_resource_unavailable",
    ] = "offline_cache_unavailable"

    def query(self, resource_id: str, query: BenefitsQuery) -> BenefitsPage:
        if resource_id != RESOURCE:
            raise UnknownPlatinumResourceError
        if (
            self.unavailable
            and self.unavailable_reason == "verified_resource_unavailable"
        ):
            if query.offline:
                raise AssertionError(
                    "online retrieval fixture received offline query"
                )
            return _unavailable_benefits_page(self.unavailable_reason)
        if self.unavailable and query.offline:
            return _unavailable_benefits_page(self.unavailable_reason)
        return _benefits_page(self.comparison_cohort)


@dataclass
class StructureLookup:
    comparison_cohort: Literal["current", "synthetic"] = "current"
    unavailable: bool = False
    unavailable_reason: Literal[
        "offline_cache_unavailable",
        "offline_contract_expired",
        "verified_resource_unavailable",
        "future_internal_reason",
    ] = "offline_cache_unavailable"

    def query(
        self, resource_id: str, query: SourceStructureQuery
    ) -> SourceStructurePage:
        if resource_id != RESOURCE:
            raise UnknownPlatinumResourceError
        if query.columns != ("kind",):
            raise ValueError("invalid bounded source-structure columns")
        if (
            self.unavailable_reason == "future_internal_reason"
            and self.unavailable
        ):
            return _unavailable_structure_page(self.unavailable_reason)
        if self.unavailable_reason == "verified_resource_unavailable":
            if self.unavailable and query.offline:
                raise AssertionError(
                    "online structure fixture received offline query"
                )
            if self.unavailable:
                return _unavailable_structure_page(self.unavailable_reason)
        if self.unavailable and query.offline:
            return _unavailable_structure_page(self.unavailable_reason)
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


def test_unavailable_source_structure_status_has_an_accessible_name() -> None:
    """Assistive technology can identify the unavailable state message."""
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=StructureLookup(
                unavailable=True, unavailable_reason="offline_cache_unavailable"
            ),
        )
    )

    response = client.get(
        "/federated/source-structure",
        params={"resource_id": RESOURCE, "columns": "kind", "offline": True},
    )
    soup = BeautifulSoup(response.text, "html.parser")
    status = soup.select_one("section[role='status']")

    assert response.status_code == 200
    assert status is not None
    labelled_by = status.get("aria-labelledby")
    assert isinstance(labelled_by, str)
    heading = soup.find(id=labelled_by)
    assert heading is not None
    assert heading.name in {"h2", "h3"}
    assert heading.get_text(" ", strip=True) == "Pinned evidence unavailable"


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


def _replace_focused_text(page: Page, value: str) -> None:
    """Replace a focused input using keyboard events."""
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.type(value)


def _assert_atlas_assets_loaded(
    requests: list[str], responses: dict[str, int], page: Page
) -> None:
    assert "/static/atlas.css" in requests
    assert "/static/atlas-autocomplete.js" in requests
    assert "/static/atlas-table-scroll.js" in requests
    assert responses["/static/atlas.css"] == 200
    assert responses["/static/atlas-autocomplete.js"] == 200
    assert responses["/static/atlas-table-scroll.js"] == 200
    assert (
        page.locator(".skip-link").evaluate(
            "element => getComputedStyle(element).position"
        )
        == "absolute"
    )


def _assert_keyboard_table_scroll(page: Page, region_name: str) -> None:
    """Prove the shared handler scrolls a narrow federated evidence region."""
    region = page.get_by_role("region", name=region_name)
    region.evaluate(
        """element => {
          element.style.width = '80px';
          element.querySelector('table').style.width = '400px';
        }"""
    )
    assert region.evaluate(
        "element => element.scrollWidth > element.clientWidth"
    )
    region.focus()
    initial_scroll_left = region.evaluate("element => element.scrollLeft")
    region.press("ArrowRight")
    keyboard_scroll_left = region.evaluate("element => element.scrollLeft")
    assert keyboard_scroll_left >= initial_scroll_left + 40
    region.press("ArrowLeft")
    assert (
        region.evaluate("element => element.scrollLeft") < keyboard_scroll_left
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
            _assert_keyboard_table_scroll(page, "Federated evidence rows")
            _assert_atlas_assets_loaded(requests, responses, page)

            page.goto("http://atlas.test/")
            _exercise_browser_structure_route(page)
            _assert_keyboard_table_scroll(
                page, "Source-structure evidence rows"
            )
            _assert_atlas_assets_loaded(requests, responses, page)
        finally:
            browser.close()


@pytest.mark.e2e
@pytest.mark.timeout(90)
def test_keyboard_user_can_query_bounded_benefits_evidence() -> None:
    """Keyboard users can open, query, and read the benefits evidence view."""
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

            benefits_link = page.get_by_role(
                "link", name="Browse pinned benefit evidence"
            )
            page.keyboard.press("Tab")
            assert page.evaluate(
                "document.activeElement.classList.contains('skip-link')"
            )
            page.keyboard.press("Tab")
            assert benefits_link.evaluate(
                "element => element === document.activeElement"
            )
            assert benefits_link.get_attribute("href") == "/federated/benefits"
            with page.expect_navigation():
                page.keyboard.press("Enter")
            assert page.url == "http://atlas.test/federated/benefits"

            page.keyboard.press("Tab")
            assert page.evaluate(
                "document.activeElement.classList.contains('skip-link')"
            )
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.id") == "resource-id"
            page.keyboard.type(RESOURCE)
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.id") == "columns"
            page.keyboard.type("item_code")
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.id") == "limit"
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.id") == "filters"
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.name") == "offline"
            page.keyboard.press("Tab")
            assert (
                page.evaluate("document.activeElement.textContent.trim()")
                == "Read pinned evidence"
            )
            with page.expect_response(
                lambda response: (
                    "/federated/benefits" in response.url
                    and response.status == 200
                )
            ):
                page.keyboard.press("Enter")

            expect(
                page.get_by_role("heading", name="Exact evidence identity")
            ).to_be_visible()
            rows = page.get_by_role(
                "region", name="Federated evidence rows"
            ).locator("tbody tr")
            expect(rows).to_have_count(1)
            assert "100" in rows.first.inner_text()
            assert (
                "Coverage is not declared here"
                in page.locator("main").inner_text()
            )
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
            invalid_filters = (
                '[{"column":"item_code","operator":"==","value":"100"}]'
            )
            page.get_by_label("Optional bounded filters (JSON array)").fill(
                invalid_filters
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
                page.get_by_label(
                    "Optional bounded filters (JSON array)"
                ).input_value()
                == invalid_filters
            )
        finally:
            browser.close()


@pytest.mark.e2e
@pytest.mark.timeout(90)
def test_browser_source_structure_errors_retain_submitted_query() -> None:
    """Unknown resources and invalid projections stay visible in the form."""
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=StructureLookup(),
        )
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            _route_client_requests(page, client)
            page.goto("http://atlas.test/")
            page.get_by_role(
                "link", name="Browse pinned source-structure evidence"
            ).click()
            resource_field = page.get_by_label("Resource identifier")
            columns_field = page.get_by_label("Source columns, comma separated")
            resource_field.fill("au.pbs.unknown")
            columns_field.fill("kind")
            with page.expect_response(
                lambda response: (
                    "/federated/source-structure" in response.url
                    and response.status == 404
                )
            ):
                page.get_by_role("button", name="Read pinned structure").click()
            assert "admitted source-structure resource was not found" in (
                page.get_by_role("alert").inner_text()
            )
            assert resource_field.input_value() == "au.pbs.unknown"
            assert columns_field.input_value() == "kind"
            assert page.get_by_role("table").count() == 0

            resource_field.fill(RESOURCE)
            columns_field.fill("kind,unknown_column")
            with page.expect_response(
                lambda response: (
                    "/federated/source-structure" in response.url
                    and response.status == 422
                )
            ):
                page.get_by_role("button", name="Read pinned structure").click()
            assert "federated source-structure query is invalid" in (
                page.get_by_role("alert").inner_text()
            )
            assert resource_field.input_value() == RESOURCE
            assert columns_field.input_value() == "kind,unknown_column"
            assert page.get_by_role("table").count() == 0
        finally:
            browser.close()


@pytest.mark.e2e
@pytest.mark.timeout(90)
@pytest.mark.parametrize(
    ("invalid_resource", "invalid_columns", "error_status"),
    [
        ("au.pbs.unknown", "kind", 404),
        (RESOURCE, "kind,unknown_column", 422),
    ],
)
def test_keyboard_user_can_recover_from_source_structure_error(
    invalid_resource: str,
    invalid_columns: str,
    error_status: int,
) -> None:
    """A 404 or 422 query can be corrected and resubmitted by keyboard."""
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
        try:
            _route_client_requests(page, client)
            page.goto("http://atlas.test/")
            source_link = page.get_by_role(
                "link", name="Browse pinned source-structure evidence"
            )
            source_link.focus()
            assert source_link.get_attribute("href") == (
                "/federated/source-structure"
            )
            with page.expect_navigation():
                source_link.press("Enter")
            assert page.url.endswith("/federated/source-structure")

            resource_field = page.get_by_label("Resource identifier")
            columns_field = page.get_by_label("Source columns, comma separated")
            resource_field.fill(invalid_resource)
            columns_field.fill(invalid_columns)
            submit = page.get_by_role("button", name="Read pinned structure")
            submit.focus()
            with page.expect_response(
                lambda response: (
                    "/federated/source-structure" in response.url
                    and response.status == error_status
                )
            ):
                page.keyboard.press("Enter")

            expect(page.get_by_role("alert")).to_be_visible()
            assert resource_field.input_value() == invalid_resource
            assert columns_field.input_value() == invalid_columns
            page.keyboard.press("Tab")
            assert page.evaluate(
                "document.activeElement.classList.contains('skip-link')"
            )
            page.keyboard.press("Enter")
            assert page.evaluate("document.activeElement.id") == "atlas-results"
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.id") == "resource-id"
            _replace_focused_text(page, RESOURCE)
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.id") == "columns"
            _replace_focused_text(page, "kind")
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.id") == "limit"
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.name") == "offline"
            page.keyboard.press("Tab")
            assert (
                page.evaluate("document.activeElement.textContent.trim()")
                == "Read pinned structure"
            )
            with page.expect_response(
                lambda response: (
                    "/federated/source-structure" in response.url
                    and response.status == 200
                )
            ):
                page.keyboard.press("Enter")
            expect(page.get_by_role("table")).to_be_visible()
            assert page.get_by_role("alert").count() == 0
        finally:
            browser.close()


@pytest.mark.e2e
@pytest.mark.timeout(90)
@pytest.mark.parametrize(
    ("reason", "expected_message", "offline"),
    [
        (
            "offline_cache_unavailable",
            "No verified cached copy is available",
            True,
        ),
        (
            "offline_contract_expired",
            "The cached copy has expired",
            True,
        ),
        (
            "verified_resource_unavailable",
            "The pinned resource could not be verified or retrieved",
            False,
        ),
        (
            "future_internal_reason",
            "The pinned source-structure evidence is unavailable",
            False,
        ),
    ],
)
def test_browser_explains_source_structure_unavailability(
    reason: Literal[
        "offline_cache_unavailable",
        "offline_contract_expired",
        "verified_resource_unavailable",
        "future_internal_reason",
    ],
    expected_message: str,
    *,
    offline: bool,
) -> None:
    """Unavailable source-structure reads remain clear and non-negative."""
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=StructureLookup(
                unavailable=True, unavailable_reason=reason
            ),
        )
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            _route_client_requests(page, client)
            page.goto("http://atlas.test/")
            page.get_by_role(
                "link", name="Browse pinned source-structure evidence"
            ).click()
            page.get_by_label("Resource identifier").fill(RESOURCE)
            page.get_by_label("Source columns, comma separated").fill("kind")
            if offline:
                page.get_by_label("Use verified cache only").check()
            with page.expect_response(
                lambda response: (
                    "/federated/source-structure" in response.url
                    and response.status == 200
                )
            ):
                page.get_by_role("button", name="Read pinned structure").click()
            unavailable = page.get_by_role("status")
            assert unavailable.get_by_role(
                "heading", name="Pinned evidence unavailable"
            ).is_visible()
            assert expected_message in unavailable.inner_text()
            assert reason not in page.locator("main").inner_text()
            assert (
                "Exact v2 evidence identity"
                in page.locator("main").inner_text()
            )
            assert (
                "exact bounded query receipt is retained"
                in page.locator("main").inner_text()
            )
            assert "No rows are shown" in unavailable.inner_text()
            assert page.get_by_role("table").count() == 0
        finally:
            browser.close()


@pytest.mark.e2e
@pytest.mark.timeout(90)
@pytest.mark.parametrize(
    ("reason", "expected_message", "offline"),
    [
        (
            "offline_cache_unavailable",
            "No verified cached copy is available",
            True,
        ),
        (
            "offline_contract_expired",
            "The cached copy has expired",
            True,
        ),
        (
            "verified_resource_unavailable",
            "The pinned resource could not be verified or retrieved",
            False,
        ),
    ],
)
def test_browser_explains_verified_query_unavailability(
    reason: Literal[
        "offline_cache_unavailable",
        "offline_contract_expired",
        "verified_resource_unavailable",
    ],
    expected_message: str,
    *,
    offline: bool,
) -> None:
    """Typed read failures remain unavailable without negative inference."""
    client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_benefits=BenefitsLookup(
                unavailable=True, unavailable_reason=reason
            ),
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
            page.get_by_label("Resource identifier").fill(RESOURCE)
            if offline:
                page.get_by_label("Use verified cache only").check()
            with page.expect_response(
                lambda response: (
                    "/federated/benefits" in response.url
                    and response.status == 200
                )
            ):
                page.get_by_role("button", name="Read pinned evidence").click()
            unavailable = page.get_by_role("status")
            assert unavailable.get_by_role(
                "heading", name="Pinned evidence unavailable"
            ).is_visible()
            assert expected_message in unavailable.inner_text()
            assert (
                page.get_by_role(
                    "region", name="Federated evidence rows"
                ).count()
                == 0
            )
            assert page.get_by_role("table").count() == 0
        finally:
            browser.close()
