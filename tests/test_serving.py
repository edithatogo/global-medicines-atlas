"""Configured packaged-service boundaries without production claims."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from fastapi.testclient import TestClient
from tests.test_support.synthetic_query_database import (
    create_synthetic_query_database,
)

if TYPE_CHECKING:
    from httpx import Client

from global_medicines_atlas.serving import create_app


def test_configured_service_shares_read_only_api_and_atlas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = create_synthetic_query_database(tmp_path / "source.duckdb")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    monkeypatch.setenv("GMA_DATABASE_PATH", str(database))
    monkeypatch.setenv("GMA_CURSOR_SECRET", "synthetic-test-secret-long-enough")
    with TestClient(create_app()) as raw_client:
        client = cast("Client", raw_client)
        for path in (
            "/api/v1/health",
            "/api/v1/readiness",
            "/",
            "/static/atlas.css",
        ):
            assert client.get(path).status_code == 200
        assert client.post("/api/v1/health", json={}).status_code == 405
        assert client.get("/api/v1/not-a-route").status_code == 404
        assert client.get("/api").status_code == 404
        assert client.get("/api/v1/openapi.json").status_code == 200
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before
        database.unlink()
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/readiness").status_code == 503
    # Database disappearance is detected and never recreates a writable file.
    assert not database.exists()


@pytest.mark.parametrize("missing", ["GMA_DATABASE_PATH", "GMA_CURSOR_SECRET"])
def test_missing_configuration_fails_closed(
    missing: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GMA_DATABASE_PATH", "/not/a/real/database.duckdb")
    monkeypatch.setenv("GMA_CURSOR_SECRET", "synthetic-test-secret-long-enough")
    monkeypatch.delenv(missing)
    with pytest.raises(ValueError, match=missing):
        create_app()


@pytest.mark.parametrize("secret", ["short", " " * 32])
def test_invalid_secret_is_not_echoed(
    secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GMA_DATABASE_PATH", "/private/database.duckdb")
    monkeypatch.setenv("GMA_CURSOR_SECRET", secret)
    with pytest.raises(ValueError, match="GMA_CURSOR_SECRET") as caught:
        create_app()
    assert secret not in str(caught.value)


def test_invalid_database_path_is_not_echoed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GMA_DATABASE_PATH", "/private/nonexistent.duckdb")
    monkeypatch.setenv("GMA_CURSOR_SECRET", "synthetic-test-secret-long-enough")
    with pytest.raises(
        ValueError, match="unavailable or incompatible"
    ) as caught:
        create_app()
    assert "/private" not in str(caught.value)


def test_api_dispatch_respects_asgi_root_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = create_synthetic_query_database(tmp_path / "source.duckdb")
    monkeypatch.setenv("GMA_DATABASE_PATH", str(database))
    monkeypatch.setenv("GMA_CURSOR_SECRET", "synthetic-test-secret-long-enough")
    with TestClient(create_app(), root_path="/atlas") as raw_client:
        client = cast("Client", raw_client)
        assert client.get("/atlas/api/v1/health").status_code == 200
        assert client.post("/atlas/api/v1/health").status_code == 405
        assert client.get("/atlas/").status_code == 200
        assert client.get("/atlas").status_code == 200
        assert client.get("/api/v1/health").status_code == 200
