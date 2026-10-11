"""HTTP contract tests for the optional Oxigraph/SPARQL graph experiment."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import cast
from urllib.request import Request

import pytest
from test_support.frontier_sparql import execute_query

_OXIGRAPH_RECEIPT = (
    Path(__file__).parents[1]
    / "quality/qualifications/oxigraph-synthetic-graph-parity-20261012.json"
)
_OXIGRAPH_RECEIPT_SHA256 = (
    "95ecdfdcf3b16efa86065a241b24b0498940ee61c1b1fbb00eefabbfc1f2c746"
)


class _Response:
    def __init__(self, body: dict[str, object], status: int = 200) -> None:
        self.body = json.dumps(body).encode()
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_execute_query_uses_sparql_protocol_and_decodes_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_urlopen(request: Request, *, timeout: float) -> _Response:
        seen["url"] = request.full_url
        seen["body"] = cast("bytes", request.data).decode()
        seen["headers"] = dict(request.header_items())
        seen["timeout"] = timeout
        return _Response({
            "head": {"vars": ["node", "payload"]},
            "results": {
                "bindings": [
                    {
                        "node": {"type": "uri", "value": "urn:gma:node:a"},
                        "payload": {"type": "literal", "value": "{}"},
                    }
                ]
            },
        })

    monkeypatch.setattr("test_support.frontier_sparql.urlopen", fake_urlopen)
    result = execute_query("http://127.0.0.1:7878", "SELECT * WHERE {}")

    assert seen["url"] == "http://127.0.0.1:7878/query?default"
    assert seen["body"] == "SELECT * WHERE {}"
    assert result == (
        ["node", "payload"],
        [
            [
                {"type": "uri", "value": "urn:gma:node:a"},
                {"type": "literal", "value": "{}"},
            ]
        ],
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "file:///tmp/oxigraph",
        "http://user:secret@localhost:7878",
        "http://localhost:7878/path",
        "http://localhost:7878/?token=secret",
    ],
)
def test_execute_query_rejects_unsafe_endpoint(endpoint: str) -> None:
    with pytest.raises(ValueError, match="endpoint must be"):
        execute_query(endpoint, "SELECT * WHERE {}")


def test_execute_query_rejects_invalid_result_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(_request: Request, *, timeout: float) -> _Response:
        assert timeout > 0.0
        return _Response({"head": {"vars": ["node"]}, "results": {}})

    monkeypatch.setattr("test_support.frontier_sparql.urlopen", fake_urlopen)
    with pytest.raises(TypeError, match="bindings"):
        execute_query("http://localhost:7878", "SELECT * WHERE {}")


def test_committed_oxigraph_receipt_pins_synthetic_engine_parity() -> None:
    document = json.loads(_OXIGRAPH_RECEIPT.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    receipt = cast("dict[str, object]", document)
    embedded_digest = receipt.pop("receipt_sha256")
    canonical = json.dumps(
        receipt,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")

    assert embedded_digest == _OXIGRAPH_RECEIPT_SHA256
    assert sha256(canonical).hexdigest() == _OXIGRAPH_RECEIPT_SHA256
    assert receipt["engine"] == "oxigraph"
    assert receipt["engine_version"] == "0.4.11"
    assert receipt["engine_image_digest"] == (
        "sha256:af35499a41f8c9768a43b2c31d0f32726dd6ec20855653dfa07814c5dce13565"
    )
    assert receipt["disposition"] == "retain-preview"
    assert receipt["source_scope"] == "synthetic-mbs-pbs-only"
    assert receipt["source_payloads_accessed"] is False
    assert receipt["rights_clearance_claimed"] is False
    assert receipt["production_authority_promoted"] is False
    cases = cast("dict[str, object]", receipt["cases"])
    for family, expected in {"mbs": (4, 2), "pbs": (10, 9)}.items():
        case = cast("dict[str, object]", cases[family])
        assert (case["node_count"], case["edge_count"]) == expected
        assert case["exact_payload_and_direction_parity"] is True
