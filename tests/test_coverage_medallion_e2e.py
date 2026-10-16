"""Synthetic source-neutral coverage journey from materialization to products."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlsplit

import duckdb
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
from typer.testing import CliRunner

from global_medicines_atlas.api import create_app
from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.cli import app as cli_app
from global_medicines_atlas.coverage import (
    CoverageObservation,
    materialize_coverage_duckdb,
)
from global_medicines_atlas.models import AssertionKind, TimeInterval
from global_medicines_atlas.query_service import ReadOnlyQueryService

if TYPE_CHECKING:
    import pytest
    from playwright.sync_api import Page, Route

NOW = datetime(2026, 10, 10, tzinfo=UTC)
SECRET = b"synthetic-coverage-e2e-secret"


def _materialized_unknown_coverage_service(
    tmp_path: Path,
) -> tuple[Path, ReadOnlyQueryService]:
    database = tmp_path / "synthetic-coverage.duckdb"
    observation = CoverageObservation(
        jurisdiction="AU",
        source_id="synthetic-fixture-only",
        receipt_id="synthetic-receipt-only",
        observation_id="synthetic-observation-only",
        population_partition_id="synthetic-population-only",
        dimension=AssertionKind.FUNDING,
        medicine_concept_id="test:medicine",
        assertion_type="synthetic-fixture",
        assertion_status="unknown",
        concept_population="synthetic fixture population",
        valid_time=TimeInterval(start=NOW),
        observed_time=TimeInterval(start=NOW),
        assertion_count=0,
        concept_numerator=0,
        eligible_denominator=None,
    )
    materialize_coverage_duckdb(
        [observation], database, valid_at=NOW, observed_at=NOW
    )

    connection = duckdb.connect(str(database))
    try:
        connection.execute(
            """
            CREATE TABLE temporal_assertions (
                assertion_id VARCHAR NOT NULL, concept_id VARCHAR NOT NULL,
                jurisdiction VARCHAR NOT NULL, kind VARCHAR NOT NULL,
                authority VARCHAR NOT NULL, status_code VARCHAR NOT NULL,
                evidence_status VARCHAR NOT NULL, restrictions VARCHAR[] NOT NULL,
                valid_from TIMESTAMPTZ NOT NULL, valid_to TIMESTAMPTZ,
                observed_from TIMESTAMPTZ NOT NULL, observed_to TIMESTAMPTZ,
                supersedes_assertion_id VARCHAR, conflict_id VARCHAR,
                source_id VARCHAR NOT NULL, source_uri VARCHAR NOT NULL,
                retrieved_at TIMESTAMPTZ, source_effective_at TIMESTAMPTZ,
                source_path VARCHAR, source_sha256 VARCHAR,
                source_version VARCHAR, transformation VARCHAR
            );
            CREATE TABLE medicine_concepts (
                concept_id VARCHAR, preferred_name VARCHAR, concept_type VARCHAR
            );
            CREATE TABLE medicine_identifiers (
                concept_id VARCHAR, identifier_system VARCHAR,
                identifier_value VARCHAR
            );
            CREATE TABLE medicine_names (
                concept_id VARCHAR, name VARCHAR, name_type VARCHAR,
                normalized_name VARCHAR
            );
            CREATE TABLE medicine_concept_jurisdictions (
                concept_id VARCHAR, jurisdiction VARCHAR
            );
            CREATE TABLE medicine_sources (
                source_id VARCHAR, jurisdiction VARCHAR, authority VARCHAR,
                regulatory_system VARCHAR, funding_system VARCHAR
            );
            INSERT INTO medicine_concepts VALUES
                ('test:medicine', 'Synthetic test medicine', 'synthetic');
            INSERT INTO medicine_concept_jurisdictions VALUES
                ('test:medicine', 'AU');
            """
        )
    finally:
        connection.close()

    service = ReadOnlyQueryService(database, cursor_secret=SECRET)
    return database, service


def _route_test_client_requests(page: Page, client: TestClient) -> None:
    """Serve Chromium navigations through the real Atlas ASGI application."""
    base_url = "http://coverage.test"

    def fulfill_from_client(route: Route) -> None:
        request_url = urlsplit(route.request.url)
        path = request_url.path
        if request_url.query:
            path = f"{path}?{request_url.query}"
        response = client.get(path)
        route.fulfill(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    page.route(f"{base_url}/**", fulfill_from_client)


def test_synthetic_unknown_coverage_crosses_medallion_products(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown coverage and null denominator survive each user-facing surface."""
    database, service = _materialized_unknown_coverage_service(tmp_path)
    api = TestClient(create_app(service))
    params = {
        "jurisdictions": "AU",
        "dimensions": "funding",
        "valid_at": NOW.isoformat(),
        "observed_at": NOW.isoformat(),
    }
    response = api.get("/api/v1/coverage", params=params)
    assert response.status_code == 200, response.text
    api_item = response.json()["coverage"][0]
    assert api_item["state"] == "unknown"
    assert api_item["denominator"] is None
    assert api_item["covered_count"] == 0

    monkeypatch.setenv("GMA_CURSOR_SECRET", SECRET.decode("utf-8"))
    cli = CliRunner().invoke(
        cli_app,
        [
            "coverage",
            "--database",
            str(database),
            "--jurisdiction",
            "AU",
            "--dimension",
            "funding",
            "--valid-at",
            NOW.isoformat(),
            "--observed-at",
            NOW.isoformat(),
        ],
    )
    assert cli.exit_code == 0, cli.output
    cli_item = json.loads(cli.stdout)["coverage"][0]
    assert cli_item == api_item

    atlas = TestClient(create_atlas_app(service))
    page = atlas.get(
        "/",
        params={
            "concept_id": "test:medicine",
            "jurisdiction": "AU",
            "valid_at": NOW.isoformat(),
            "observed_at": NOW.isoformat(),
        },
    )
    assert page.status_code == 200, page.text
    assert 'data-state="unknown"' in page.text
    assert (
        "0 observed; denominator unknown, so no percentage is calculated"
        in page.text
    )
    assert "not_covered" not in page.text


def test_materialized_unknown_coverage_reaches_real_browser_page(
    tmp_path: Path,
) -> None:
    """Chromium sees the same unknown row queried from the materialized DB."""
    _, service = _materialized_unknown_coverage_service(tmp_path)
    client = TestClient(create_atlas_app(service))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            _route_test_client_requests(page, client)
            query = urlencode({
                "concept_id": "test:medicine",
                "jurisdiction": "AU",
                "valid_at": NOW.isoformat(),
                "observed_at": NOW.isoformat(),
            })
            response = page.goto(f"http://coverage.test/?{query}")
            assert response is not None
            assert response.status == 200

            table = page.get_by_role("table")
            expect(table).to_be_visible()
            coverage_row = table.get_by_role("row").filter(
                has=page.locator("[data-state='unknown']")
            )
            expect(coverage_row).to_have_count(1)
            expect(coverage_row).to_contain_text("Status: unknown")
            expect(coverage_row).to_contain_text(
                "0 observed; denominator unknown, so no percentage is calculated"
            )
            assert "%" not in coverage_row.inner_text()
        finally:
            browser.close()
