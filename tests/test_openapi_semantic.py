from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from global_medicines_atlas.api import create_app
from global_medicines_atlas.generated.openapi_client import (
    GlobalMedicinesAtlasClient,
    JsonValue,
)
from global_medicines_atlas.openapi_client_generator import generate_client
from global_medicines_atlas.openapi_semantic import (
    OpenAPIContractError,
    assert_semantically_compatible,
    semantic_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "contracts/openapi-readonly-v1.json"


def _document() -> dict[str, Any]:
    return cast("dict[str, Any]", create_app(cast("Any", object())).openapi())


def _baseline() -> dict[str, Any]:
    return cast(
        "dict[str, Any]", json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    )


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete", "trace"])
def test_snapshot_rejects_every_mutation_method(method: str) -> None:
    document = _document()
    document["paths"]["/api/v1/health"][method] = {"operationId": "mutate"}
    with pytest.raises(OpenAPIContractError, match="mutation operations"):
        semantic_snapshot(document)


def test_snapshot_rejects_request_body_and_missing_operation_identity() -> None:
    document = _document()
    operation = document["paths"]["/api/v1/health"]["get"]
    operation["requestBody"] = {"content": {}}
    with pytest.raises(OpenAPIContractError, match="request bodies"):
        semantic_snapshot(document)
    del operation["requestBody"]
    del operation["operationId"]
    with pytest.raises(OpenAPIContractError, match="operationId"):
        semantic_snapshot(document)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("path", "path removed"),
        ("operation", "path removed"),
        ("identity", "operation identity changed"),
        ("response", "response removed"),
        ("media", "response media removed"),
        ("property", "response field removed"),
        ("type", "type changed"),
    ],
)
def test_semantic_diff_rejects_incompatible_changes(
    mutation: str, message: str
) -> None:
    baseline = _baseline()
    document = _document()
    path = "/api/v1/health"
    operation = document["paths"][path]["get"]
    if mutation == "path":
        del document["paths"][path]
    elif mutation == "operation":
        del document["paths"][path]["get"]
    elif mutation == "identity":
        operation["operationId"] = "changed"
    elif mutation == "response":
        del operation["responses"]["200"]
    elif mutation == "media":
        del operation["responses"]["200"]["content"]["application/json"]
    elif mutation == "property":
        del document["components"]["schemas"]["HealthResponse"]["properties"][
            "state"
        ]
    else:
        document["components"]["schemas"]["HealthResponse"]["properties"][
            "checked_at"
        ]["type"] = "integer"
    with pytest.raises(OpenAPIContractError, match=message):
        assert_semantically_compatible(baseline, document)


def test_documented_additive_read_only_change_is_compatible() -> None:
    document = _document()
    document["paths"]["/api/v1/additive"] = {
        "get": {
            "operationId": "additive_api_v1_additive_get",
            "parameters": [
                {
                    "in": "query",
                    "name": "optional",
                    "schema": {"type": "string"},
                }
            ],
            "responses": {
                "200": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"value": {"type": "string"}},
                            }
                        }
                    }
                }
            },
        }
    }
    assert_semantically_compatible(_baseline(), document)


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def request(
        self, method: str, path: str, query: dict[str, str]
    ) -> JsonValue:
        self.calls.append((method, path, query))
        return {"offline": True}


def test_generated_client_smoke_is_typed_read_only_and_offline() -> None:
    transport = RecordingTransport()
    client = GlobalMedicinesAtlasClient(transport)
    result = client.concept_detail_api_v1_concepts__concept_id__get(
        concept_id="nz:123"
    )
    assert result == {"offline": True}
    assert transport.calls == [("GET", "/api/v1/concepts/nz:123", {})]
    generated = generate_client(_baseline())
    assert "def post" not in generated
    assert generated == (
        ROOT / "src/global_medicines_atlas/generated/openapi_client.py"
    ).read_text(encoding="utf-8")


def test_generated_client_smokes_every_committed_read_only_operation() -> None:
    transport = RecordingTransport()
    client = GlobalMedicinesAtlasClient(transport)

    client.comparisons_api_v1_comparisons_get(
        concept_id="nz:123",
        cursor=None,
        dimensions="funding",
        jurisdictions="NZ,AU",
        limit=20,
        observed_at="2026-07-31",
        valid_at="2026-07-31",
    )
    client.concepts_api_v1_concepts_get(q="aspirin", limit=10)
    client.coverage_api_v1_coverage_get(
        jurisdictions="NZ",
        observed_at="2026-07-31",
        valid_at="2026-07-31",
    )
    client.evidence_api_v1_evidence_get(
        concept_id="nz:123",
        observed_at="2026-07-31",
        valid_at="2026-07-31",
    )
    client.health_api_v1_health_get()
    client.jurisdictions_api_v1_jurisdictions_get()
    client.readiness_api_v1_readiness_get()
    client.sources_api_v1_sources_get(jurisdiction="NZ")

    assert len(transport.calls) == 8
    assert {method for method, _, _ in transport.calls} == {"GET"}
    assert transport.calls[0][2] == {
        "concept_id": "nz:123",
        "dimensions": "funding",
        "jurisdictions": "NZ,AU",
        "limit": "20",
        "observed_at": "2026-07-31",
        "valid_at": "2026-07-31",
    }


def test_current_snapshot_is_deterministic_and_public_endpoint_matches() -> (
    None
):
    document = _document()
    assert semantic_snapshot(document) == _baseline()
    client = TestClient(create_app(cast("Any", object())))
    assert (
        semantic_snapshot(client.get("/api/v1/openapi.json").json())
        == _baseline()
    )


def test_snapshot_matches_its_committed_json_schema() -> None:
    schema = json.loads(
        (ROOT / "schemas/openapi-readonly-snapshot-v1.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_baseline())
