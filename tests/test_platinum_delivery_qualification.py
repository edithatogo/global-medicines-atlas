"""Consumer acceptance uses genuine trust loading and synthetic HTTP only."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from test_platinum_configuration import configuration
from test_platinum_query import (
    native_field_collection_payload,
    parquet_payload,
    resolver,
)

from global_medicines_atlas import cli
from global_medicines_atlas import (
    platinum_structure_qualification as qualification,
)
from global_medicines_atlas.platinum_delivery_qualification import (
    DeliveryQualificationError,
    DeliveryRequest,
    run_product_delivery_qualification,
)
from global_medicines_atlas.platinum_resolver import StorageNeutralResolver


def run(tmp_path, requests, **kwargs):
    return run_product_delivery_qualification(
        tmp_path / "trust.json",
        tmp_path,
        tmp_path / "schema.json",
        requests,
        **kwargs,
    )


@pytest.fixture
def transport(monkeypatch):
    def handle(request: httpx.Request) -> httpx.Response:
        if "/api/datasets/" in request.url.path:
            return httpx.Response(
                200, json={"sha": "a" * 40, "private": False, "gated": False}
            )
        return httpx.Response(200, content=parquet_payload())

    monkeypatch.setattr(
        "global_medicines_atlas.federation_reader.BoundIPAddressTransport",
        lambda **_kwargs: httpx.MockTransport(handle),
    )


def test_real_loader_and_consumer_routes_agree_without_retaining_values(
    tmp_path, transport, monkeypatch
):
    del transport
    configuration(tmp_path)
    monkeypatch.setenv("GMA_CURSOR_SECRET", "retained-user-secret")
    report = run(
        tmp_path,
        (
            DeliveryRequest(
                resource_id="au.mbs.items",
                columns=("item_code", "benefit"),
                limit=2,
            ),
        ),
    )
    assert report["status"] == "passed"
    evidence = report["evidence"][0]
    assert (
        evidence["row_count"]
        == evidence["export_row_count"]
        == evidence["atlas_rendered_row_count"]
        == 2
    )
    assert evidence["api_http_status"] == evidence["atlas_http_status"] == 200
    assert evidence["cli_exit_code"] == evidence["export_exit_code"] == 0
    assert (
        len(evidence["identity_sha256"]) == len(evidence["rows_sha256"]) == 64
    )
    encoded = json.dumps(report)
    assert "item_code" not in encoded
    assert "12.5" not in encoded
    assert "retained-user-secret" not in encoded
    assert os.environ["GMA_CURSOR_SECRET"] == "retained-user-secret"  # ruff: ignore[hardcoded-password-string] -- synthetic restoration assertion.


def test_bounded_browser_canary_matches_actual_atlas_response(
    tmp_path, transport
):
    del transport
    configuration(tmp_path)
    report = run(
        tmp_path,
        (
            DeliveryRequest(
                resource_id="au.mbs.items",
                columns=("item_code", "benefit"),
                limit=2,
            ),
        ),
        browser=True,
    )

    assert report["browser_qualification"] == "passed"
    canary = report["evidence"][0]
    browser = canary["browser"]
    assert browser["http_status"] == 200
    assert browser["row_count"] == canary["atlas_rendered_row_count"] == 2
    assert len(browser["identity_sha256"]) == 64
    assert len(browser["rendered_rows_sha256"]) == 64
    assert "12.5" not in json.dumps(report)
    assert "item_code" not in json.dumps(report)


def test_tampered_candidate_is_rejected_by_actual_loader(tmp_path):
    configuration(tmp_path)
    (tmp_path / "contract.json").write_text("{}")
    with pytest.raises(ValueError, match="operator trust"):
        run(
            tmp_path,
            (
                DeliveryRequest(
                    resource_id="au.mbs.items", columns=("item_code",)
                ),
            ),
        )


def test_uncached_offline_does_not_pass(tmp_path):
    configuration(tmp_path)
    with pytest.raises(DeliveryQualificationError, match="unavailable"):
        run(
            tmp_path,
            (
                DeliveryRequest(
                    resource_id="au.mbs.items", columns=("item_code",)
                ),
            ),
            offline=True,
        )


@pytest.mark.parametrize(
    "requests",
    [
        (),
        (DeliveryRequest(resource_id="au.mbs.items", columns=("item_code",)),)
        * 33,
    ],
)
def test_request_count_is_bounded_before_loading(tmp_path, requests):
    with pytest.raises(DeliveryQualificationError, match="request count"):
        run(tmp_path, requests)


@pytest.mark.parametrize(
    "update",
    [{"limit": 101}, {"limit": True}, {"columns": ()}, {"unrecognized": True}],
)
def test_request_bounds_and_unknown_fields_are_rejected(update):
    with pytest.raises(ValidationError):
        DeliveryRequest.model_validate({
            "resource_id": "au.mbs.items",
            "columns": ("item_code",),
            **update,
        })


@pytest.mark.parametrize(
    ("offline", "column", "closed_count"),
    [
        (False, "item_code", 3),
        (True, "item_code", 2),
        (False, "missing_column", 2),
    ],
)
def test_cli_and_http_resolvers_close_on_success_unavailable_and_query_failure(
    tmp_path, transport, monkeypatch, offline, column, closed_count
):
    del transport
    configuration(tmp_path)
    closed = []
    original_close = StorageNeutralResolver.close

    def close(resolver):
        original_close(resolver)
        closed.append(resolver.cached_bytes)

    monkeypatch.setattr(StorageNeutralResolver, "close", close)
    request = DeliveryRequest(
        resource_id="au.mbs.items", columns=(column,), limit=2
    )
    if offline or column == "missing_column":
        with pytest.raises(DeliveryQualificationError):
            run(tmp_path, (request,), offline=offline)
    else:
        run(tmp_path, (request,))
    assert closed == [0] * closed_count


def test_source_structure_qualification_renders_in_chromium(
    monkeypatch, tmp_path
):
    from playwright.sync_api import BrowserType  # ruff: ignore[import-outside-top-level]

    browser_path = Path(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    if browser_path.is_file():
        original = BrowserType.launch

        def launch(self, **kwargs):
            return original(self, executable_path=browser_path, **kwargs)

        monkeypatch.setattr(BrowserType, "launch", launch)

    def loader(**_kwargs):
        return resolver(
            native_field_collection_payload(),
            semantic_dimension="source_structure",
        )

    monkeypatch.setattr(qualification, "load_benefits_resolver", loader)
    monkeypatch.setattr(cli, "_dataset_resolver_loader", lambda: loader)
    trust_file = tmp_path / "trust.json"
    schema_file = tmp_path / "schema.json"
    trust_file.write_text("{}")
    schema_file.write_text("{}")
    receipt = qualification.qualify_structure_consumers(
        trust_file=trust_file,
        metadata_root=tmp_path,
        schema_file=schema_file,
        resource_id="au.mbs.service-items",
        columns=("source_field_id", "value"),
        view="fields",
        limit=2,
        browser=True,
    )
    assert receipt["browser_qualification"] == "passed"
    assert receipt["browser_evidence"][0]["row_count"] == 2
