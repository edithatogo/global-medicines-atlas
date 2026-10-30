from __future__ import annotations

import json

import httpx
import scripts.structured_source_batch as batch


def test_tables_ignore_single_column_navigation():
    html = b"<table><tr><th>Medicine</th></tr><tr><td>Link</td></tr><tr><td>Other</td></tr></table>"
    assert batch.structured_tables(html) == []


def test_tables_preserve_quotes_and_multiple_columns():
    html = b"<table><tr><th>Medicine</th><th>Strength</th></tr><tr><td>A, B</td><td>5 mg</td></tr><tr><td>C</td><td>10 mg</td></tr></table>"
    assert '"A, B",5 mg' in batch.structured_tables(html)[0]


def test_acquisition_records_direct_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        batch,
        "BoundIPAddressTransport",
        lambda **_kwargs: httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"records": [1]},
            )
        ),
    )
    result = batch.acquire(
        {
            "source_id": "test-source",
            "url": "https://example.org/data",
            "allowed_hosts": ["example.org"],
        },
        tmp_path,
    )
    assert result["state"] == "downloaded_local"
    assert json.loads((tmp_path / "test-source/payload.bin").read_bytes()) == {
        "records": [1]
    }


def test_acquisition_does_not_retry_failures(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(403)

    monkeypatch.setattr(
        batch,
        "BoundIPAddressTransport",
        lambda **_kwargs: httpx.MockTransport(handler),
    )
    result = batch.acquire(
        {
            "source_id": "test-source",
            "url": "https://example.org/data",
            "allowed_hosts": ["example.org"],
        },
        tmp_path,
    )
    assert result["state"] == "failed"
    assert len(calls) == 1
