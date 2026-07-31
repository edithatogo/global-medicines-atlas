"""Versioned API exposure for deterministic concept discovery."""

# ruff: file-ignore[import-private-name]

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from tests.test_concept_query_service import _catalog_database
from tests.test_query_service import SECRET

from global_medicines_atlas.api import create_app
from global_medicines_atlas.query_service import ReadOnlyQueryService


def _client(tmp_path: Path) -> TestClient:
    service = ReadOnlyQueryService(
        _catalog_database(tmp_path / "catalog.duckdb"),
        cursor_secret=SECRET,
        allowed_root=tmp_path,
    )
    return TestClient(create_app(service))


def test_concept_search_is_versioned_bounded_and_explained(
    tmp_path: Path,
) -> None:
    response = _client(tmp_path).get(
        "/api/v1/concepts",
        params={"q": "paracetamol", "jurisdictions": "NZ", "limit": 1},
        headers={"x-request-id": "discovery-request"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["api_version"] == "v1"
    assert payload["metadata"]["page"]["returned"] == 1
    assert payload["concepts"][0]["concept_id"] == "gma:para"
    assert (
        payload["concepts"][0]["explanation"]["establishes_equivalence"]
        is False
    )
    assert response.headers["cache-control"].startswith("public")


def test_concept_detail_and_catalogue_routes_are_read_only(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    detail = client.get("/api/v1/concepts/gma:aspirin")
    jurisdictions = client.get("/api/v1/jurisdictions")
    sources = client.get("/api/v1/sources", params={"jurisdiction": "nz"})

    assert detail.json()["identifiers"][0]["value"] == "1191"
    assert [item["jurisdiction"] for item in jurisdictions.json()] == [
        "AU",
        "NZ",
    ]
    assert {item["source_id"] for item in sources.json()} == {
        "medsafe",
        "pharmac",
    }
    for path in (
        "/api/v1/concepts",
        "/api/v1/concepts/gma:aspirin",
        "/api/v1/jurisdictions",
        "/api/v1/sources",
    ):
        head = client.head(
            path, params={"q": "aspirin"} if path.endswith("concepts") else None
        )
        assert head.status_code == 200
        assert head.content == b""
        assert client.post(path).status_code == 405


def test_discovery_errors_are_typed_and_do_not_leak_service_detail(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    invalid = client.get(
        "/api/v1/concepts",
        params={"q": "aspirin", "limit": 251},
        headers={"x-request-id": "invalid-discovery"},
    )
    missing = client.get("/api/v1/concepts/unknown")

    assert invalid.status_code == 422
    assert invalid.json()["error"] == "invalid_request"
    assert invalid.json()["request_id"] == "invalid-discovery"
    assert missing.status_code == 503
    assert missing.json()["error"] == "service_unavailable"
    assert "unknown" not in missing.text
