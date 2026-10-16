"""HTTP contract tests for the optional Neo4j graph experiment."""

import hashlib
import json
from pathlib import Path
from urllib.request import Request

import pytest
from test_support.frontier_neo4j import decode_rows, execute_query

_NEO4J_RECEIPT = (
    Path(__file__).parents[1]
    / "quality/qualifications/neo4j-synthetic-graph-parity-20261011.json"
)
_NEO4J_RECEIPT_SHA256 = (
    "1da2e161e35f6d4644782b8625ba15ee94d71a664e207f2ba446f23cc7e09231"
)


class _Response:
    def __init__(self, body: dict[str, object], status: int = 202) -> None:
        self.body = json.dumps(body).encode()
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_execute_query_uses_parameterized_v2_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_urlopen(request: Request, *, timeout: float) -> _Response:
        seen["url"] = request.full_url
        body = request.data
        assert isinstance(body, bytes)
        seen["body"] = json.loads(body)
        seen["timeout"] = timeout
        return _Response({"data": {"fields": ["value"], "values": [[7]]}})

    monkeypatch.setattr("test_support.frontier_neo4j.urlopen", fake_urlopen)

    result = execute_query(
        "http://127.0.0.1:7474/",
        "RETURN $value AS value",
        {"value": 7},
    )

    assert seen == {
        "url": "http://127.0.0.1:7474/db/neo4j/query/v2",
        "body": {
            "statement": "RETURN $value AS value",
            "parameters": {"value": 7},
        },
        "timeout": 10.0,
    }
    assert result == (["value"], [[7]])


@pytest.mark.parametrize(
    "endpoint",
    [
        "file:///tmp/neo4j",
        "http://user:secret@localhost:7474",
        "http://localhost:7474/path",
        "http://localhost:7474/?token=secret",
    ],
)
def test_execute_query_rejects_unsafe_endpoint(endpoint: str) -> None:
    with pytest.raises(ValueError, match="endpoint must be"):
        execute_query(endpoint, "RETURN 1 AS value", {})


def test_execute_query_rejects_database_query_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(_request: Request, *, timeout: float) -> _Response:
        assert timeout > 0.0
        return _Response({"errors": [{"code": "bad"}]})

    monkeypatch.setattr("test_support.frontier_neo4j.urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="Neo4j query failed"):
        execute_query("http://localhost:7474", "RETURN 1 AS value", {})


def test_execute_query_rejects_invalid_tabular_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(_request: Request, *, timeout: float) -> _Response:
        assert timeout > 0.0
        return _Response({
            "data": {"fields": ["left", "right"], "values": [[1]]}
        })

    monkeypatch.setattr("test_support.frontier_neo4j.urlopen", fake_urlopen)

    with pytest.raises(TypeError, match="row width differs"):
        execute_query("http://localhost:7474", "RETURN 1 AS value", {})


def test_execute_query_accepts_write_without_returned_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(_request: Request, *, timeout: float) -> _Response:
        assert timeout > 0.0
        return _Response({"queryType": "rw"})

    monkeypatch.setattr("test_support.frontier_neo4j.urlopen", fake_urlopen)

    assert execute_query("http://localhost:7474", "CREATE (n)", {}) == ([], [])


def test_readback_rejects_observed_edge_direction_conflict() -> None:
    fields = ["edge_id", "source_node_id", "target_node_id", "payload_json"]
    values: list[list[object]] = [
        [
            "edge-1",
            "observed-source",
            "observed-target",
            json.dumps({
                "edge_id": "edge-1",
                "source_node_id": "expected-source",
                "target_node_id": "expected-target",
            }),
        ]
    ]

    with pytest.raises(ValueError, match="structural field"):
        decode_rows(
            fields,
            values,
            ["edge_id", "source_node_id", "target_node_id", "payload_json"],
        )


def test_committed_neo4j_receipt_is_checksummed_and_non_promoting() -> None:
    receipt = json.loads(_NEO4J_RECEIPT.read_text(encoding="utf-8"))
    digest = receipt.pop("receipt_sha256")
    canonical = json.dumps(
        receipt,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")

    assert digest == _NEO4J_RECEIPT_SHA256
    assert hashlib.sha256(canonical).hexdigest() == digest
    assert receipt["engine"] == "neo4j"
    assert receipt["source_scope"] == "synthetic-mbs-pbs-only"
    assert receipt["source_payloads_accessed"] is False
    assert receipt["rights_clearance_claimed"] is False
    assert receipt["production_authority_promoted"] is False
    cases = receipt["cases"]
    assert set(cases) == {"mbs", "pbs"}
    assert all(
        case["exact_payload_and_direction_parity"] for case in cases.values()
    )
