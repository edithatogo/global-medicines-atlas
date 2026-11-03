"""Configured packaged-service boundaries without production claims."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from tests.test_support.synthetic_query_database import (
    create_synthetic_query_database,
)

if TYPE_CHECKING:
    from httpx import Client

from global_medicines_atlas import hosted_service
from global_medicines_atlas.serving import create_app


def _hosted_payload() -> bytes:
    return json.dumps({
        "results": [
            {
                "application_number": "NDA000001",
                "products": [
                    {"product_number": "001", "brand_name": "Synthetic product"}
                ],
            }
        ]
    }).encode()


def test_hosted_catalogue_is_real_schema_without_invented_assertions(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GMA_HOSTED_CACHE", str(tmp_path))
    monkeypatch.delenv("GMA_CURSOR_SECRET", raising=False)
    monkeypatch.setenv(
        "SPACE_SIGNING_SECRET", "synthetic-platform-signing-value"
    )

    def prepare(path):
        return hosted_service.prepare_database(path, _hosted_payload())

    monkeypatch.setattr(hosted_service, "prepare_hosted", prepare)
    for _ in range(2):
        with TestClient(hosted_service.create_app()) as client:
            assert client.get("/api/v1/readiness").status_code == 200
            metadata = client.get("/deployment.json").json()
            assert metadata["product_count"] == 1
            assert metadata["production_data_qualified"] is False
            assert metadata["temporal_assertion_count"] == 0
            assert client.get("/api/v1/concepts?q=Synthetic").status_code == 200
            page = client.get("/")
            assert "Historical FDA catalogue candidate" in page.text
            assert "content-length" not in page.headers
    assert len(list(tmp_path.glob("boot-*/catalogue.duckdb"))) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"results": []},
        {"results": [{"application_number": "", "products": []}]},
        {
            "results": [
                {"application_number": "x", "products": [{"brand_name": "x"}]}
            ]
        },
        {
            "results": [
                {
                    "application_number": "x",
                    "products": [{"product_number": "1"}],
                }
            ]
        },
        {"results": [{"application_number": "x", "products": []}]},
        {
            "results": [
                {
                    "application_number": "x",
                    "products": [{"product_number": "1", "brand_name": "x"}],
                },
                {
                    "application_number": "x",
                    "products": [{"product_number": "1", "brand_name": "x"}],
                },
            ]
        },
    ],
)
def test_hosted_catalogue_rejects_ambiguous_or_missing_native_data(payload):
    with pytest.raises(
        ValueError,
        match=r"native|applications|products|admission|denominator|byte count",
    ):
        hosted_service.catalogue(json.dumps(payload).encode())


def test_hosted_projection_refuses_overwrite(tmp_path):
    path = tmp_path / "existing.duckdb"
    path.write_bytes(b"preserved")
    with pytest.raises(ValueError, match="overwrite"):
        hosted_service.prepare_database(path, _hosted_payload())
    assert path.read_bytes() == b"preserved"


def test_hosted_boot_requires_existing_platform_secret(monkeypatch):
    monkeypatch.delenv("GMA_CURSOR_SECRET", raising=False)
    monkeypatch.delenv("SPACE_SIGNING_SECRET", raising=False)
    with pytest.raises(ValueError, match="signing secret"):
        hosted_service.create_app()


def test_hosted_source_download_is_anonymous_and_digest_bound(monkeypatch):
    calls = []

    def download(url, timeout, follow_redirects):
        calls.append((url, timeout))
        assert follow_redirects is True
        return httpx.Response(
            200, content=b"payload", request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(hosted_service.httpx, "get", download)
    assert (
        hosted_service.verified_download(
            "data/us-openfda-drugsfda.json",
            hashlib.sha256(b"payload").hexdigest(),
        )
        == b"payload"
    )
    assert calls[0][0].startswith(hosted_service.BASE)
    with pytest.raises(ValueError, match="digest"):
        hosted_service.verified_download(
            "data/us-openfda-drugsfda.json", "0" * 64
        )
    with pytest.raises(ValueError, match="unapproved"):
        hosted_service.verified_download("private.json", "0" * 64)


@pytest.mark.parametrize(
    "failure", [None, "duplicate", "rights", "bytes", "denominator"]
)
def test_hosted_source_admission_is_preserved(tmp_path, monkeypatch, failure):
    payload = _hosted_payload()
    # The pure bootstrap is exercised with synthetic bytes; actual archive
    # bytes are used only in the dedicated hosted container qualification.
    document = json.loads(payload)
    document["results"] *= 100
    for index, row in enumerate(document["results"]):
        document["results"][index] = {
            **row,
            "application_number": f"NDA{index:06}",
        }
    payload = json.dumps(document).encode()
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(hosted_service, "PAYLOAD_SHA", digest)
    entry = {
        "source_id": hosted_service.SOURCE,
        "admission_state": "accepted",
        "rights_state": "permitted",
        "source_records_projected": True,
        "payload_sha256": digest,
        "payload_byte_count": len(payload),
        "source_record_count": 100,
    }
    if failure == "rights":
        entry["rights_state"] = "unknown"
    if failure == "bytes":
        entry["payload_byte_count"] = 1
    if failure == "denominator":
        document["results"].pop()
        payload = json.dumps(document).encode()
        entry["payload_byte_count"] = len(payload)
    entries = [entry, entry] if failure == "duplicate" else [entry]
    monkeypatch.setattr(
        hosted_service,
        "verified_download",
        lambda member, _: (
            json.dumps(entries).encode()
            if member.startswith("acquisition")
            else payload
        ),
    )
    if failure:
        with pytest.raises(
            ValueError,
            match=r"native|applications|products|admission|denominator|byte count",
        ):
            hosted_service.prepare_hosted(tmp_path / "source.duckdb")
    else:
        assert (
            hosted_service.prepare_hosted(tmp_path / "source.duckdb")[
                "application_count"
            ]
            == 100
        )


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
