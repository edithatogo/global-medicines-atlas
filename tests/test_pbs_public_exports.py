"""Exact-byte privacy boundary for historical public export publication."""

import base64
import gzip
import hashlib
import json

import pytest
from scripts.publish_pbs_public_exports import decode_bundle, main


def bundle(files):
    return base64.b64encode(gzip.compress(json.dumps(files).encode())).decode()


def test_exact_approved_bytes_only():
    data = "synthetic public report"
    approved = {
        "report.xls": {
            "bytes": len(data),
            "sha256": hashlib.sha256(data.encode()).hexdigest(),
        }
    }
    assert decode_bundle(bundle({"report.xls": data}), approved) == {
        "report.xls": data.encode()
    }
    for files in ({}, {"participant.csv": data}, {"report.xls": data + "x"}):
        with pytest.raises(ValueError, match="Public export"):
            decode_bundle(bundle(files), approved)


def test_expansion_and_encoded_bounds():
    with pytest.raises(ValueError, match="Public export"):
        decode_bundle("x" * 60_001, {})
    with pytest.raises(ValueError, match="Public export"):
        decode_bundle(bundle({"report": "x" * 2_000_001}), {})


def test_duplicate_names_and_trailing_stream_rejected():
    duplicate = base64.b64encode(gzip.compress(b'{"x":"a","x":"a"}'))
    with pytest.raises(ValueError, match="Public export"):
        decode_bundle(duplicate.decode(), {"x": {}})
    trailing = base64.b64encode(gzip.compress(b"{}") + b"extra")
    with pytest.raises(ValueError, match="Public export"):
        decode_bundle(trailing.decode(), {})


def test_local_publication_rejected_before_input_or_token(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(PermissionError, match="Actions main"):
        main()
