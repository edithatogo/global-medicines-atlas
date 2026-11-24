from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest
import scripts.structured_source_batch as batch
from scripts.publish_source_batch import batch_catalog
from scripts.source_download_batch import DownloadSelection


def test_dated_nadac_requires_an_exact_approved_csv(tmp_path: Path) -> None:
    batch_id = "cms-nadac-20261125"
    path = tmp_path / batch_id / "manifest.json"
    manifest = {
        "batch_id": batch_id,
        "repository": f"edithatogo/global-medicines-atlas-{batch_id}",
        "approval_reference": "Synthetic test approval",
        "expected_payloads": {
            "us-cms-nadac": {"sha256": "a" * 64, "byte_count": 100}
        },
    }
    url = "https://download.medicaid.gov/data/nadac-national-average-drug-acquisition-cost-11-25-2026.csv"
    selection = DownloadSelection(source_id="us-cms-nadac", expected_url=url)
    selected = batch_catalog(path, manifest, (selection,))
    assert (
        str(
            next(
                s.download_url
                for s in selected
                if s.source_id == selection.source_id
            )
        )
        == url
    )
    with pytest.raises(ValueError, match="exact official CSV"):
        batch_catalog(
            path,
            manifest,
            (
                selection.model_copy(
                    update={"expected_url": url.replace("11-25", "11-18")}
                ),
            ),
        )
    with pytest.raises(ValueError, match="approved size and SHA-256"):
        batch_catalog(path, manifest | {"expected_payloads": {}}, (selection,))


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
