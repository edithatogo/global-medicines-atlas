"""Configured packaged-service boundaries without production claims."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, cast

import duckdb
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
    monkeypatch.setenv("GMA_APPLICATION_COMMIT", "a" * 40)
    monkeypatch.setenv("GMA_DATABASE_PATH", "existing-owner-binding")
    monkeypatch.delenv("GMA_CURSOR_SECRET", raising=False)
    monkeypatch.setenv(
        "SPACE_SIGNING_SECRET", "synthetic-platform-signing-value"
    )

    def prepare(path):
        receipt = hosted_service.prepare_database(path, _hosted_payload())
        hosted_service.materialize_approval_events(
            path,
            [
                {
                    "concept_id": "us-drugsfda:NDA000001:001",
                    "qualification": "unmatched",
                    "approval_date": None,
                }
            ],
        )
        return receipt

    monkeypatch.setattr(hosted_service, "prepare_hosted", prepare)
    for _ in range(2):
        with TestClient(hosted_service.create_app()) as client:
            assert client.get("/api/v1/readiness").status_code == 200
            metadata = client.get("/deployment.json").json()
            events = client.get("/approval-events.json")
            assert events.status_code == 200
            assert events.json()["application_commit"] == "a" * 40
            assert events.json()["events"][0]["qualification"] == "unmatched"
            assert "not continuing approval" in events.json()["scope"]
            assert metadata["product_count"] == 1
            assert metadata["production_data_qualified"] is False
            assert metadata["temporal_assertion_count"] == 0
            assert client.get("/api/v1/concepts?q=Synthetic").status_code == 200
            page = client.get("/?concept_search=Synthetic")
            assert 'data-concept-id="us-drugsfda:NDA000001:001"' in page.text
            assert metadata["application_commit"] == "a" * 40
            assert metadata["python_version"] == "3.15.1"
            assert "Historical FDA catalogue candidate" in page.text
            assert "content-length" not in page.headers
    assert len(list(tmp_path.glob("boot-*/catalogue.duckdb"))) == 2
    assert (
        hosted_service.os.environ["GMA_DATABASE_PATH"]
        == "existing-owner-binding"
    )
    assert "GMA_CURSOR_SECRET" not in hosted_service.os.environ


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


def test_hosted_commit_identity_is_mandatory(monkeypatch):
    monkeypatch.setenv("GMA_CURSOR_SECRET", "synthetic-existing-signing-value")
    monkeypatch.delenv("GMA_APPLICATION_COMMIT", raising=False)
    with pytest.raises(ValueError, match="application commit"):
        hosted_service.create_app()


def test_hosted_scope_disclosure_handles_split_body_chunks(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GMA_HOSTED_CACHE", str(tmp_path))
    monkeypatch.setenv("GMA_APPLICATION_COMMIT", "b" * 40)
    monkeypatch.setenv("GMA_CURSOR_SECRET", "synthetic-existing-signing-value")
    monkeypatch.setattr(hosted_service, "prepare_hosted", lambda _: {})

    async def streamed(_scope, _receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await send({
            "type": "http.response.body",
            "body": b"<html><body><hea",
            "more_body": True,
        })
        await send({
            "type": "http.response.body",
            "body": b"der>chunked</header></body></html>",
        })

    monkeypatch.setattr(
        hosted_service, "configured_app", lambda **_kwargs: streamed
    )
    client = TestClient(hosted_service.create_app())
    try:
        response = client.get("/")
        assert "Historical FDA catalogue candidate" in response.text
        assert "</p></header></body>" in response.text
        assert '<header>chunked<p role="note">' in response.text
    finally:
        client.close()


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
    "failure", [None, "duplicate", "rights", "bytes", "denominator", "orange"]
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
    archive_stream = io.BytesIO()
    with zipfile.ZipFile(archive_stream, "w") as archive:
        archive.writestr(
            "products.txt",
            "Appl_Type~Appl_No~Product_No~Approval_Date\n"
            "N~000001~001~Jan 02, 2001\n"
            "N~000002~001~Approved Prior to Jan 1, 1982\n",
        )
    orange_payload = archive_stream.getvalue()
    monkeypatch.setattr(
        hosted_service, "ORANGE_SHA", hashlib.sha256(orange_payload).hexdigest()
    )
    entries.append({
        "source_id": "us-fda-orange-book",
        "admission_state": "accepted",
        "payload_sha256": hosted_service.ORANGE_SHA,
        "payload_byte_count": len(orange_payload),
        "rights_state": "restricted",
    })
    if failure == "orange":
        entries[-1]["admission_state"] = "quarantined"
    monkeypatch.setattr(
        hosted_service.httpx,
        "stream",
        lambda *_args, **_kwargs: nullcontext(
            httpx.Response(
                200,
                content=orange_payload,
                request=httpx.Request("GET", hosted_service.ORANGE_URI),
            )
        ),
    )
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
        receipt = hosted_service.prepare_hosted(tmp_path / "source.duckdb")
        assert receipt["application_count"] == 100
        assert (
            receipt["approval_event_summary"]["bounded_before_1982_count"] == 1
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


@pytest.mark.parametrize("content", [b"oversized", b"x"])
def test_orange_download_rejects_size_or_digest_drift(monkeypatch, content):
    monkeypatch.setattr(
        hosted_service.httpx,
        "stream",
        lambda *_a, **_k: nullcontext(
            httpx.Response(
                200,
                content=content,
                request=httpx.Request("GET", hosted_service.ORANGE_URI),
            )
        ),
    )
    with pytest.raises(ValueError, match="Orange Book payload"):
        hosted_service.download_orange_book(1)


@pytest.mark.parametrize("size", [0, hosted_service.MAX_BYTES + 1])
def test_orange_download_rejects_unbounded_admission_before_network(
    monkeypatch, size
):
    def reject(*_a, **_k):
        raise AssertionError("network must not be contacted")

    monkeypatch.setattr(hosted_service.httpx, "stream", reject)
    with pytest.raises(ValueError, match="admission size"):
        hosted_service.download_orange_book(size)


def test_approval_event_database_accounts_for_exact_catalogue(tmp_path):
    path = tmp_path / "catalogue.duckdb"
    hosted_service.prepare_database(path, _hosted_payload())
    event = {
        "concept_id": "us-drugsfda:NDA000001:001",
        "qualification": "exact_product_approval_date",
        "approval_date": "2001-01-02",
        "source_id": "us-fda-orange-book",
    }
    counts = hosted_service.materialize_approval_events(path, [event])
    assert counts["exact_product_approval_date"] == 1
    assert sum(counts.values()) == 1
    with duckdb.connect(str(path), read_only=True) as connection:
        row = connection.execute(
            "SELECT concept_id, qualification, CAST(approval_date AS VARCHAR), evidence_json FROM product_approval_events"
        ).fetchone()
    assert row is not None
    assert row[:3] == (
        event["concept_id"],
        event["qualification"],
        event["approval_date"],
    )
    assert json.loads(row[3]) == event


@pytest.mark.parametrize("case", ["duplicate", "unknown", "count", "identity"])
def test_approval_event_database_rejects_invalid_coverage(tmp_path, case):
    path = tmp_path / "catalogue.duckdb"
    hosted_service.prepare_database(path, _hosted_payload())
    event = {
        "concept_id": "us-drugsfda:NDA000001:001",
        "qualification": "unmatched",
        "approval_date": None,
    }
    events = [event]
    if case == "duplicate":
        events = [event, event]
    elif case == "unknown":
        event["qualification"] = "unsupported"
    elif case == "count":
        events = []
    else:
        event["concept_id"] = "wrong"
    with pytest.raises(ValueError, match="approval-event"):
        hosted_service.materialize_approval_events(path, events)
