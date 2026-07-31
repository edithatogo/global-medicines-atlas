# ruff: file-ignore[suspicious-subprocess-import, subprocess-without-shell-equals-true]

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from scripts import qualify_openapi_client as qualifier
from scripts.qualify_openapi_client import load_historical_snapshot

from global_medicines_atlas import openapi_semantic
from global_medicines_atlas.api import create_app
from global_medicines_atlas.generated import openapi_client as generated_client
from global_medicines_atlas.generated.openapi_client import (
    ClientTransport,
    ClientTransportError,
    GlobalMedicinesAtlasClient,
    JsonValue,
)
from global_medicines_atlas.openapi_client_generator import (
    OpenAPIClientGenerationError,
    generate_client,
)
from global_medicines_atlas.openapi_semantic import (
    OpenAPIContractError,
    assert_semantically_compatible,
    semantic_snapshot,
)
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    ComparisonQuery,
    ComparisonResponse,
    PageMetadata,
    ResponseMetadata,
)
from global_medicines_atlas.query_service import ReadOnlyQueryService

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


def test_mandatory_authentication_is_a_breaking_change() -> None:
    document = _document()
    document["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer"}
    }
    document["security"] = [{"BearerAuth": []}]
    with pytest.raises(
        OpenAPIContractError,
        match="security requirements changed",
    ):
        assert_semantically_compatible(_baseline(), document)


def test_security_scheme_identity_changes_fail_closed() -> None:
    document = _document()
    document["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer"}
    }
    document["security"] = [{"BearerAuth": []}]
    baseline = semantic_snapshot(document)
    document["components"]["securitySchemes"]["BearerAuth"]["scheme"] = "basic"
    with pytest.raises(OpenAPIContractError, match="scheme changed"):
        assert_semantically_compatible(baseline, document)


def test_response_enum_addition_is_breaking_but_removal_is_compatible() -> None:
    document = _document()
    health_state = document["components"]["schemas"]["HealthState"]["enum"]
    health_state.append("maintenance")
    with pytest.raises(
        OpenAPIContractError,
        match="response enum values added",
    ):
        assert_semantically_compatible(_baseline(), document)

    document = _document()
    document["components"]["schemas"]["HealthState"]["enum"].remove(
        "unavailable"
    )
    assert_semantically_compatible(_baseline(), document)


def _enum_parameter_document(values: list[str]) -> dict[str, Any]:
    document = _document()
    document["paths"]["/api/v1/additive"] = {
        "get": {
            "operationId": "enum_parameter",
            "parameters": [
                {
                    "in": "query",
                    "name": "state",
                    "required": False,
                    "schema": {"type": "string", "enum": values},
                }
            ],
            "responses": {
                "200": {
                    "content": {
                        "application/json": {"schema": {"type": "object"}}
                    }
                }
            },
        }
    }
    return document


def test_request_enum_addition_is_compatible_but_removal_is_breaking() -> None:
    baseline = semantic_snapshot(_enum_parameter_document(["a", "b"]))
    assert_semantically_compatible(
        baseline,
        _enum_parameter_document(["a", "b", "c"]),
    )
    with pytest.raises(
        OpenAPIContractError,
        match="request enum values removed",
    ):
        assert_semantically_compatible(
            baseline,
            _enum_parameter_document(["a"]),
        )


@pytest.mark.parametrize(
    ("baseline", "current", "variance", "reason"),
    [
        (
            {"type": "string"},
            {"type": "string", "enum": ["NZ"]},
            "request",
            "enum narrowed",
        ),
        (
            {"type": "integer", "minimum": 1},
            {"type": "integer", "minimum": 2},
            "request",
            "range narrowed",
        ),
        (
            {"type": "integer", "maximum": 10},
            {"type": "integer", "maximum": 9},
            "request",
            "range narrowed",
        ),
        (
            {"type": "string"},
            {"type": "string", "pattern": "^NZ$"},
            "request",
            "pattern narrowed",
        ),
        (
            {"type": "string", "pattern": "^NZ$"},
            {"type": "string"},
            "response",
            "pattern widened",
        ),
        (
            {"type": "object", "required": []},
            {"type": "object", "required": ["q"]},
            "request",
            "required request fields added",
        ),
        (
            {"type": "object", "required": ["state"]},
            {"type": "object", "required": []},
            "response",
            "required response fields removed",
        ),
        (
            {"type": "array", "items": {"type": "string"}},
            {"type": "array"},
            "response",
            "array item schema removed",
        ),
        (
            {"anyOf": [{"type": "string"}]},
            {"anyOf": [{"type": "integer"}]},
            "response",
            "anyOf changed",
        ),
    ],
)
def test_schema_variance_rejects_additional_breaking_boundaries(
    baseline: dict[str, Any],
    current: dict[str, Any],
    variance: str,
    reason: str,
) -> None:
    changes = openapi_semantic._schema_changes(
        baseline,
        current,
        "test.schema",
        cast("Any", variance),
    )
    assert any(reason in change.reason for change in changes)


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, tuple[tuple[str, str], ...]]] = []

    def request(
        self,
        method: str,
        path: str,
        query: Sequence[tuple[str, str]],
    ) -> JsonValue:
        self.calls.append((method, path, tuple(query)))
        return {"offline": True}


def test_generated_client_smoke_is_typed_read_only_and_offline() -> None:
    transport = RecordingTransport()
    client = GlobalMedicinesAtlasClient(transport)
    result = client.concept_detail_api_v1_concepts__concept_id__get(
        concept_id="nz:123/β?detail=true"
    )
    assert result == {"offline": True}
    assert transport.calls == [
        (
            "GET",
            "/api/v1/concepts/nz%3A123%2F%CE%B2%3Fdetail%3Dtrue",
            (),
        )
    ]
    generated = generate_client(_baseline())
    assert "def post" not in generated
    assert "jurisdictions: Sequence[str]" in generated
    assert (
        'dimensions: Sequence[Literal["regulatory", "funding", "formulary"]]'
        in generated
    )
    assert generated == (
        ROOT / "src/global_medicines_atlas/generated/openapi_client.py"
    ).read_text(encoding="utf-8")


def test_generated_client_smokes_every_committed_read_only_operation() -> None:
    transport = RecordingTransport()
    client = GlobalMedicinesAtlasClient(transport)

    client.comparisons_api_v1_comparisons_get(
        concept_id="nz:123",
        cursor=None,
        dimensions=("regulatory", "funding"),
        jurisdictions=("NZ", "AU"),
        limit=20,
        observed_at="2026-07-31",
        valid_at="2026-07-31",
    )
    client.concepts_api_v1_concepts_get(q="aspirin", limit=10)
    client.coverage_api_v1_coverage_get(
        dimensions=None,
        jurisdictions=("NZ",),
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
    assert transport.calls[0][2] == (
        ("concept_id", "nz:123"),
        ("dimensions", "regulatory"),
        ("dimensions", "funding"),
        ("jurisdictions", "NZ"),
        ("jurisdictions", "AU"),
        ("limit", "20"),
        ("observed_at", "2026-07-31"),
        ("valid_at", "2026-07-31"),
    )


NOW = datetime(2026, 7, 31, tzinfo=UTC)


class ComparisonService:
    def __init__(self) -> None:
        self.query: ComparisonQuery | None = None

    def comparisons(self, query: ComparisonQuery) -> ComparisonResponse:
        self.query = query
        return ComparisonResponse(
            metadata=ResponseMetadata(
                generated_at=NOW,
                clocks=AsOfClocks(valid_at=NOW, observed_at=NOW),
                page=PageMetadata(limit=query.limit, returned=0),
            ),
            conclusions=(),
        )


def test_generated_client_reaches_real_asgi_with_repeated_array_pairs() -> None:
    service = ComparisonService()
    test_client = TestClient(create_app(cast("ReadOnlyQueryService", service)))
    transport = ClientTransport(cast("Any", test_client))
    client = GlobalMedicinesAtlasClient(transport)

    payload = client.comparisons_api_v1_comparisons_get(
        concept_id="nz:123",
        cursor=None,
        dimensions=("regulatory", "funding"),
        jurisdictions=("NZ", "AU"),
        limit=20,
        observed_at="2026-07-31T00:00:00Z",
        valid_at="2026-07-31T00:00:00Z",
    )

    assert isinstance(payload, dict)
    assert service.query is not None
    assert service.query.jurisdictions == ("NZ", "AU")
    assert service.query.dimensions == ("regulatory", "funding")


def test_asgi_transport_fails_closed_on_http_errors() -> None:
    transport = ClientTransport(
        cast(
            "Any",
            TestClient(create_app(cast("ReadOnlyQueryService", object()))),
        )
    )
    client = GlobalMedicinesAtlasClient(transport)
    with pytest.raises(ClientTransportError, match="HTTP 422"):
        client.comparisons_api_v1_comparisons_get(
            concept_id="nz:123",
            cursor=None,
            dimensions=("regulatory",),
            jurisdictions=("NZ",),
            limit=20,
            observed_at="not-a-date",
            valid_at="not-a-date",
        )


class StaticResponse:
    def __init__(self, value: object) -> None:
        self.status_code = 200
        self._value = value

    def json(self) -> object:
        return self._value


class StaticClient:
    def __init__(self, value: object) -> None:
        self._value = value

    def request(
        self,
        _method: str,
        _url: str,
        *,
        params: Sequence[tuple[str, str]],
    ) -> StaticResponse:
        assert isinstance(params, Sequence)
        return StaticResponse(self._value)


@pytest.mark.parametrize("value", [{1: "invalid"}, object()])
def test_transport_rejects_non_json_response_values(value: object) -> None:
    transport = ClientTransport(cast("Any", StaticClient(value)))
    with pytest.raises(TypeError, match=r"JSON object keys|unsupported JSON"):
        transport.request("GET", "/api/v1/health", ())


def test_query_serialization_is_deterministic_for_boolean_scalars() -> None:
    assert generated_client._query((("enabled", True), ("omitted", None))) == (
        ("enabled", "true"),
    )


def test_generator_fails_closed_on_unsupported_query_schema() -> None:
    snapshot = _baseline()
    parameter = snapshot["paths"]["/api/v1/sources"]["get"]["parameters"][0]
    parameter["schema"] = {"type": "object"}
    with pytest.raises(
        OpenAPIClientGenerationError,
        match="unsupported query schema type",
    ):
        generate_client(snapshot)


@pytest.mark.parametrize(
    ("schema", "message"),
    [
        ({"anyOf": [{"type": "string"}, {"type": "integer"}]}, "anyOf"),
        (
            {"$ref": "external.json#/value"},
            "unsupported query schema reference",
        ),
        (
            {"$ref": "#/components/schemas/Missing"},
            "query schema reference is missing",
        ),
        ({"type": "string", "enum": []}, "enum values"),
    ],
)
def test_generator_rejects_ambiguous_or_unresolved_query_schemas(
    schema: dict[str, Any],
    message: str,
) -> None:
    snapshot = _baseline()
    parameter = snapshot["paths"]["/api/v1/sources"]["get"]["parameters"][0]
    parameter["schema"] = schema
    with pytest.raises(OpenAPIClientGenerationError, match=message):
        generate_client(snapshot)


def test_generator_rejects_invalid_path_parameter_contracts() -> None:
    snapshot = _baseline()
    operation = snapshot["paths"]["/api/v1/concepts/{concept_id}"]["get"]
    operation["parameters"][0]["required"] = False
    with pytest.raises(OpenAPIClientGenerationError, match="must be required"):
        generate_client(snapshot)

    snapshot = _baseline()
    operation = snapshot["paths"]["/api/v1/concepts/{concept_id}"]["get"]
    operation["parameters"][0]["name"] = "missing"
    with pytest.raises(OpenAPIClientGenerationError, match="no placeholder"):
        generate_client(snapshot)

    snapshot = _baseline()
    operation = snapshot["paths"]["/api/v1/concepts/{concept_id}"]["get"]
    operation["parameters"] = []
    with pytest.raises(OpenAPIClientGenerationError, match="unbound path"):
        generate_client(snapshot)


def _run_git(root: Path, *arguments: str) -> None:
    executable = shutil.which("git")
    assert executable is not None
    subprocess.run(
        [executable, *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_historical_baseline_ignores_worktree_snapshot_edits(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    contract = repository / "contracts/openapi-readonly-v1.json"
    contract.parent.mkdir(parents=True)
    baseline = {
        "contract": "global-medicines-atlas.openapi-readonly",
        "version": 1,
        "components": {},
        "paths": {},
    }
    contract.write_text(json.dumps(baseline), encoding="utf-8")
    _run_git(repository, "init")
    _run_git(repository, "config", "user.email", "test@example.invalid")
    _run_git(repository, "config", "user.name", "OpenAPI test")
    _run_git(repository, "add", "contracts/openapi-readonly-v1.json")
    _run_git(repository, "commit", "-m", "baseline")
    contract.write_text('{"rewritten": true}', encoding="utf-8")

    assert load_historical_snapshot("HEAD", root=repository) == baseline


def test_historical_baseline_rejects_missing_git_and_invalid_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qualifier.shutil, "which", lambda _name: None)
    with pytest.raises(
        qualifier.HistoricalBaselineError, match="git is required"
    ):
        load_historical_snapshot("HEAD", root=tmp_path)
    monkeypatch.undo()

    repository = tmp_path / "repository"
    contract = repository / "contracts/openapi-readonly-v1.json"
    contract.parent.mkdir(parents=True)
    contract.write_text("not-json", encoding="utf-8")
    _run_git(repository, "init")
    _run_git(repository, "config", "user.email", "test@example.invalid")
    _run_git(repository, "config", "user.name", "OpenAPI test")
    _run_git(repository, "add", "contracts/openapi-readonly-v1.json")
    _run_git(repository, "commit", "-m", "invalid")
    with pytest.raises(qualifier.HistoricalBaselineError, match="invalid JSON"):
        load_historical_snapshot("HEAD", root=repository)
    with pytest.raises(qualifier.HistoricalBaselineError, match="ref is empty"):
        load_historical_snapshot("", root=repository)
    with pytest.raises(qualifier.HistoricalBaselineError, match="git show"):
        load_historical_snapshot(
            "HEAD",
            root=repository,
            snapshot_relative="contracts/missing.json",
        )


def test_qualification_main_writes_checks_and_rejects_stale_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = tmp_path / "openapi.json"
    client = tmp_path / "client.py"
    monkeypatch.setattr(qualifier, "SNAPSHOT", snapshot)
    monkeypatch.setattr(qualifier, "CLIENT", client)
    monkeypatch.setattr(
        qualifier,
        "load_historical_snapshot",
        lambda _reference: _baseline(),
    )
    monkeypatch.setattr(
        qualifier.argparse.ArgumentParser,
        "parse_args",
        lambda _self: qualifier.argparse.Namespace(
            write=True,
            baseline_ref="HEAD",
        ),
    )
    assert qualifier.main() == 0
    first_snapshot = snapshot.read_bytes()
    first_client = client.read_bytes()

    monkeypatch.setattr(
        qualifier.argparse.ArgumentParser,
        "parse_args",
        lambda _self: qualifier.argparse.Namespace(
            write=False,
            baseline_ref="HEAD",
        ),
    )
    assert qualifier.main() == 0
    assert snapshot.read_bytes() == first_snapshot
    assert client.read_bytes() == first_client

    snapshot.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="snapshot is stale"):
        qualifier.main()
    snapshot.write_bytes(first_snapshot)
    client.write_text("# stale\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="client is stale"):
        qualifier.main()


def test_default_baseline_ref_prefers_explicit_ci_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GMA_OPENAPI_BASE_REF", "abc123")
    assert qualifier._default_baseline_ref() == "abc123"


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
