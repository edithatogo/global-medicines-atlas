"""Cross-surface synthetic benefits query acceptance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit

if TYPE_CHECKING:
    import httpx

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Route, sync_playwright
from test_atlas_e2e import StateService
from test_platinum_benefits_api import service
from typer.testing import CliRunner

from global_medicines_atlas import cli
from global_medicines_atlas.api import create_app
from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.platinum_resolver import StorageNeutralResolver
from global_medicines_atlas.query_service import ReadOnlyQueryService


@pytest.mark.parametrize(
    ("source", "semantic_dimension"),
    [("mbs", "service_benefit"), ("pbs", "funding")],
)
def test_synthetic_benefits_query_agrees_across_cli_api_and_atlas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    semantic_dimension: str,
) -> None:
    benefits = service(source=source)
    resource_id = f"au.{source}.service-items"
    columns = ("item_code", "benefit")
    cursor_secret = "k" * 32
    monkeypatch.setenv("GMA_CURSOR_SECRET", cursor_secret)

    trust_file = tmp_path / "trust.json"
    schema_file = tmp_path / "schema.json"
    metadata_root = tmp_path / "metadata"
    trust_file.write_text("{}", encoding="utf-8")
    schema_file.write_text("{}", encoding="utf-8")
    metadata_root.mkdir()
    resolver = benefits._resolver  # pyright: ignore[reportPrivateUsage] -- fixture shares the resolver configured by the service helper.

    def load_test_resolver(
        *, trust_file: Path, metadata_root: Path, schema_file: Path
    ) -> StorageNeutralResolver:
        del trust_file, metadata_root, schema_file
        return resolver

    monkeypatch.setattr(
        "global_medicines_atlas.platinum_configuration.load_benefits_resolver",
        load_test_resolver,
    )

    cli_result = CliRunner().invoke(
        cli.app,
        [
            "benefits",
            resource_id,
            "--trust-file",
            str(trust_file),
            "--metadata-root",
            str(metadata_root),
            "--schema-file",
            str(schema_file),
            "--column",
            columns[0],
            "--column",
            columns[1],
            "--limit",
            "2",
        ],
    )
    assert cli_result.exit_code == 0, cli_result.output
    cli_page = json.loads(cli_result.stdout)

    api_response = cast(
        "httpx.Response",
        TestClient(
            create_app(
                cast("ReadOnlyQueryService", object()), benefits=benefits
            )
        ).get(  # pyright: ignore[reportUnknownMemberType] -- Starlette TestClient stubs omit its response type.
            f"/api/v1/benefits/{resource_id}",
            params=[("columns", column) for column in columns]
            + [("limit", "2")],
        ),
    )
    assert api_response.status_code == 200
    api_page = cast("dict[str, object]", api_response.json())

    atlas_response = cast(
        "httpx.Response",
        TestClient(
            create_atlas_app(StateService(), federated_benefits=benefits)
        ).get(  # pyright: ignore[reportUnknownMemberType] -- Starlette TestClient stubs omit its response type.
            "/federated/benefits",
            params={
                "resource_id": resource_id,
                "columns": ",".join(columns),
                "limit": 2,
            },
        ),
    )
    assert atlas_response.status_code == 200
    assert (
        "<tbody><tr><td><code>100</code></td><td><code>12.5</code></td></tr>"
        "<tr><td><code>200</code></td><td><code>25.0</code></td></tr></tbody>"
        in atlas_response.text
    )
    assert "not declared" in atlas_response.text
    assert "not evaluated" in atlas_response.text

    assert cli_page["status"] == api_page["status"] == "available"
    assert (
        cli_page["rows"]
        == api_page["rows"]
        == [
            {"item_code": "100", "benefit": 12.5},
            {"item_code": "200", "benefit": 25.0},
        ]
    )
    for page in (cli_page, api_page):
        identity = cast("dict[str, object]", page["identity"])
        assert identity["semantic_dimension"] == semantic_dimension
        assert identity["comparison_cohort"] == "synthetic"
        assert page["coverage_state"] == "not_declared"
        assert page["confidence_state"] == "not_declared"
        assert page["comparison_validity"] == "not_evaluated"


@pytest.mark.parametrize(
    ("source", "semantic_dimension"),
    [("mbs", "service_benefit"), ("pbs", "funding")],
)
def test_synthetic_benefits_render_in_chromium_atlas(
    source: str,
    semantic_dimension: str,
) -> None:
    """Exercise the benefits query through the Atlas page in a real browser."""
    benefits = service(source=source)
    client = TestClient(
        create_atlas_app(StateService(), federated_benefits=benefits)
    )

    def fulfill_from_atlas(route: Route) -> None:
        request = route.request
        parsed = urlsplit(request.url)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        typed_client = cast("httpx.Client", client)
        response = typed_client.get(path)
        route.fulfill(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.route("http://atlas.test/**", fulfill_from_atlas)
            response = page.goto(
                "http://atlas.test/federated/benefits?resource_id="
                f"au.{source}.service-items&columns=item_code%2Cbenefit&limit=2"
            )
            assert response is not None
            assert response.status == 200
            rows = page.get_by_role("table").get_by_role("row")
            assert rows.count() == 3
            assert rows.nth(1).inner_text() == "100\t12.5"
            assert rows.nth(2).inner_text() == "200\t25.0"
            body = page.locator("body").inner_text()
            semantic_value = page.locator("dl").get_by_text(
                semantic_dimension, exact=True
            )
            assert semantic_value.is_visible()
            assert "Coverage\nnot declared" in body
            assert "Comparison validity\nnot evaluated" in body
            assert "synthetic qualification fixtures" in body
        finally:
            browser.close()
