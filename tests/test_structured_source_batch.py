from __future__ import annotations

import hashlib
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


def test_html_tables_retain_native_evidence(tmp_path, monkeypatch):
    html = b"<table><tr><th>Medicine</th><th>Price</th></tr><tr><td>A</td><td>1</td></tr><tr><td>B</td><td>2</td></tr></table>"
    monkeypatch.setattr(
        batch,
        "BoundIPAddressTransport",
        lambda **_kw: httpx.MockTransport(
            lambda _r: httpx.Response(
                200, headers={"content-type": "text/html"}, content=html
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
    digest = hashlib.sha256(html).hexdigest()
    directory = tmp_path / "test-source"
    assert (directory / f"{digest}.html").read_bytes() == html
    receipt = json.loads((directory / "source-receipt.json").read_text())
    assert receipt["sha256"] == digest
    assert receipt["derived_tables"] == ["table-0.csv"]
    assert result["digests"][f"{digest}.html"] == digest


def test_relative_export_uses_redirect_destination(tmp_path, monkeypatch):
    requested = []

    def handler(request):
        requested.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(
                302, headers={"location": "/downloads/index.html"}
            )
        if request.url.path == "/downloads/index.html":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b'<a href="medicines.csv">Medicines</a>',
            )
        assert request.url.path == "/downloads/medicines.csv"
        return httpx.Response(
            200,
            headers={"content-type": "text/csv"},
            content=b"Medicine,Price\nA,1\n",
        )

    monkeypatch.setattr(
        batch,
        "BoundIPAddressTransport",
        lambda **_kw: httpx.MockTransport(handler),
    )
    result = batch.acquire(
        {
            "source_id": "test-source",
            "url": "https://example.org/start",
            "allowed_hosts": ["example.org"],
        },
        tmp_path,
    )
    assert result["state"] == "downloaded_local"
    assert requested[-1] == "https://example.org/downloads/medicines.csv"
