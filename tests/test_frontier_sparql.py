"""HTTP contract tests for the optional Oxigraph/SPARQL graph experiment."""

from __future__ import annotations

import json
from typing import cast
from urllib.request import Request

import pytest
from test_support.frontier_sparql import execute_query


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
