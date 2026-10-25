"""Scalar benefit filters agree across service, HTTP and CLI contracts."""

import builtins
import json
from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_platinum_benefits_api import service
from test_platinum_configuration import configuration
from test_platinum_query import (
    date_parquet_payload,
    decimal_parquet_payload,
    nested_native_parquet_payload,
)
from typer.testing import CliRunner

from global_medicines_atlas.api import create_app
from global_medicines_atlas.cli import app
from global_medicines_atlas.generated.openapi_client import (
    ClientTransport,
    GlobalMedicinesAtlasClient,
)
from global_medicines_atlas.platinum_benefits import (
    BenefitsFilter,
    BenefitsPage,
    BenefitsQuery,
    BenefitsService,
    benefits_page_payload,
    parse_benefits_filters,
)
from global_medicines_atlas.query_service import ReadOnlyQueryService


def test_filter_changes_rows_and_binds_cursor_even_if_result_same():
    backend = service()
    query = BenefitsQuery(
        columns=("item_code",),
        limit=1,
        filters=(
            BenefitsFilter(column="item_code", operator=">=", value="200"),
        ),
    )
    first = backend.query("au.mbs.service-items", query)
    assert first.rows == ({"item_code": "200"},)
    assert first.applied_filters == query.filters
    assert first.query_sha256
    changed = query.model_copy(
        update={
            "filters": (
                BenefitsFilter(column="item_code", operator=">", value="100"),
            ),
            "cursor": first.next_cursor,
        }
    )
    with pytest.raises(ValueError, match="cursor"):
        backend.query("au.mbs.service-items", changed)


@pytest.mark.parametrize(
    "encoded",
    [
        '[{"column":"item_code","operator":"=","value":[]}]',
        '[{"column":"item_code","operator":"=","value":NaN}]',
        '[{"column":"item_code","operator":"=","value":"x","extra":1}]',
        '[{"column":"item_code","operator":"LIKE","value":"x"}]',
        '[{"column":"item_code","operator":"=","value":1,"value":2}]',
        "{}",
        "null",
        "[" + ",".join(["{}"] * 17) + "]",
    ],
)
def test_malformed_filters_rejected(encoded):
    with pytest.raises(ValueError, match=r"filter|validation|JSON"):
        parse_benefits_filters(encoded)


def test_copied_invalid_model_rejected():
    backend = service()
    invalid = BenefitsFilter(
        column="item_code", operator="=", value="200"
    ).model_copy(update={"value": {"nested": "bad"}})
    with pytest.raises(ValueError, match=r"filter|validation"):
        backend.query(
            "au.mbs.service-items",
            BenefitsQuery.model_construct(
                columns=("item_code",), filters=(invalid,)
            ),
        )


def test_http_filter_and_unknown_source_column():
    client = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), benefits=service())
    )
    filters = '[{"column":"item_code","operator":"=","value":"200"}]'
    response = client.get(
        "/api/v1/benefits/au.mbs.service-items",
        params={"columns": "item_code", "filters": filters},
    )
    assert response.status_code == 200
    assert response.json()["rows"] == [{"item_code": "200"}]
    response = client.get(
        "/api/v1/benefits/au.mbs.service-items",
        params={
            "columns": "item_code",
            "filters": filters.replace("item_code", "unknown"),
        },
    )
    assert response.status_code == 422


def test_native_struct_component_is_available_through_api_and_cli(
    tmp_path, monkeypatch
):
    backend = service(payload=nested_native_parquet_payload())
    configuration(tmp_path)
    monkeypatch.setattr(
        "global_medicines_atlas.platinum_configuration.load_benefits_resolver",
        lambda **_: backend._resolver,
    )
    expected = [
        {"ItemNum.native_value": "MBS-A"},
        {"ItemNum.native_value": None},
    ]

    client = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), benefits=backend)
    )
    response = client.get(
        "/api/v1/benefits/au.mbs.service-items",
        params={"columns": "ItemNum.native_value", "limit": 2},
    )
    assert response.status_code == 200
    assert response.json()["rows"] == expected

    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.service-items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "ItemNum.native_value",
            "--limit",
            "2",
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["rows"] == expected


def test_generated_client_carries_filters_and_pagination_to_service():
    http = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), benefits=service())
    )
    client = GlobalMedicinesAtlasClient(ClientTransport(http))
    filters = '[{"column":"item_code","operator":">=","value":"200"}]'
    first = client.benefits_route_api_v1_benefits__resource_id__get(
        resource_id="au.mbs.service-items",
        columns=("item_code",),
        filters=filters,
        limit=1,
        offline=False,
    )
    assert first["rows"] == [{"item_code": "200"}]
    second = client.benefits_route_api_v1_benefits__resource_id__get(
        resource_id="au.mbs.service-items",
        columns=("item_code",),
        filters=filters,
        limit=1,
        cursor=first["next_cursor"],
        offline=True,
    )
    assert second["rows"] == [{"item_code": "300"}]
    assert second["applied_filters"] == json.loads(filters)


def test_cli_offline_attempt_preserves_filter_evidence(tmp_path):
    configuration(tmp_path)
    filters = '[{"column":"item_code","operator":"=","value":"200"}]'
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--offline",
            "--filters-json",
            filters,
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )
    assert result.exit_code == 3, result.output
    response = json.loads(result.stdout)
    assert response["status"] == "unavailable"
    assert response["applied_filters"] == json.loads(filters)
    assert len(response["query_sha256"]) == 64


def test_cli_benefits_jsonl_traverses_pages_and_emits_receipt_summary(
    tmp_path,
    monkeypatch,
):
    configuration(tmp_path)
    backend = service()
    monkeypatch.setattr(
        "global_medicines_atlas.platinum_configuration.load_benefits_resolver",
        lambda **_: backend._resolver,
    )
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.service-items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--limit",
            "1",
            "--format",
            "jsonl",
            "--max-rows",
            "3",
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )

    assert result.exit_code == 0, (result.output, repr(result.exception))
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    records, summary = lines[:-1], lines[-1]
    assert [line["record"]["item_code"] for line in records] == [
        "100",
        "200",
        "300",
    ]
    assert all(line["type"] == "record" for line in records)
    assert all(line["identity"]["source_id"] == "au-mbs" for line in records)
    assert all(len(line["receipt_sha256"]) == 64 for line in records)
    assert summary["type"] == "summary"
    assert summary["status"] == "available"
    assert summary["row_count"] == 3
    assert summary["page_count"] == 3
    assert summary["source_completeness"] == "not_established"
    assert summary["truncated"] is False
    assert summary["window_complete"] is True


def test_cli_benefits_jsonl_max_rows_returns_cursor_and_never_partial_summary(
    tmp_path,
    monkeypatch,
):
    configuration(tmp_path)
    backend = service()
    monkeypatch.setattr(
        "global_medicines_atlas.platinum_configuration.load_benefits_resolver",
        lambda **_: backend._resolver,
    )
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.service-items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--limit",
            "1",
            "--format",
            "jsonl",
            "--max-rows",
            "2",
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )

    assert result.exit_code == 0, (result.output, repr(result.exception))
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(lines) == 3
    assert lines[-1]["row_count"] == 2
    assert lines[-1]["truncated"] is True
    assert lines[-1]["next_cursor"]


def test_cli_benefits_jsonl_keeps_cursor_page_size_when_row_cap_is_not_multiple(
    tmp_path, monkeypatch
):
    configuration(tmp_path)
    backend = service()
    monkeypatch.setattr(
        "global_medicines_atlas.platinum_configuration.load_benefits_resolver",
        lambda **_: backend._resolver,
    )
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.service-items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--limit",
            "2",
            "--format",
            "jsonl",
            "--max-rows",
            "3",
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )

    assert result.exit_code == 0, (result.output, repr(result.exception))
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(lines) == 3
    assert [line["record"]["item_code"] for line in lines[:-1]] == [
        "100",
        "200",
    ]
    assert lines[-1]["row_count"] == 2
    assert lines[-1]["page_size"] == 2
    assert lines[-1]["truncated"] is True
    assert lines[-1]["next_cursor"]


def test_cli_benefits_jsonl_rejects_cursor_loop_without_partial_output(
    tmp_path, monkeypatch
):
    configuration(tmp_path)
    backend = service()
    monkeypatch.setattr(
        "global_medicines_atlas.platinum_configuration.load_benefits_resolver",
        lambda **_: backend._resolver,
    )
    original_query = BenefitsService.query
    first_pages: list[BenefitsPage] = []

    def repeating_query(
        self: BenefitsService,
        resource_id: str,
        query: BenefitsQuery,
        *,
        consumer_id: str = "anonymous",
    ) -> BenefitsPage:
        if not first_pages:
            first_pages.append(
                original_query(
                    self, resource_id, query, consumer_id=consumer_id
                ).model_copy(update={"next_cursor": "repeat"})
            )
        return first_pages[0]

    monkeypatch.setattr(BenefitsService, "query", repeating_query)
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.service-items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--limit",
            "1",
            "--format",
            "jsonl",
            "--max-rows",
            "3",
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )

    assert result.exit_code == 2
    assert not result.stdout
    assert json.loads(result.stderr)["error"] == "invalid_request"


def test_cli_benefits_jsonl_byte_limit_fails_before_output(
    tmp_path, monkeypatch
):
    configuration(tmp_path)
    backend = service()
    monkeypatch.setattr(
        "global_medicines_atlas.platinum_configuration.load_benefits_resolver",
        lambda **_: backend._resolver,
    )
    monkeypatch.setattr(
        "global_medicines_atlas.cli._BENEFITS_EXPORT_MAX_BYTES", 1
    )
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.service-items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--format",
            "jsonl",
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )

    assert result.exit_code == 2
    assert not result.stdout
    assert json.loads(result.stderr)["error"] == "invalid_request"


@pytest.mark.parametrize(
    ("mutation", "max_rows", "limit"),
    [
        ("identity", 3, 1),
        ("rows_type", 3, 1),
        ("row_type", 3, 1),
        ("row_bound", 1, 1),
    ],
)
def test_cli_benefits_jsonl_rejects_invalid_page_payload_without_partial_output(
    tmp_path, monkeypatch, mutation: str, max_rows: int, limit: int
):
    configuration(tmp_path)
    backend = service()
    monkeypatch.setattr(
        "global_medicines_atlas.platinum_configuration.load_benefits_resolver",
        lambda **_: backend._resolver,
    )
    original_payload = benefits_page_payload
    payload_count = 0

    def corrupt_payload(page: BenefitsPage) -> dict[str, object]:
        nonlocal payload_count
        payload_count += 1
        payload = original_payload(page)
        if mutation == "identity" and payload_count == 2:
            identity = payload["identity"]
            assert isinstance(identity, dict)
            identity["revision"] = "b" * 40
        elif mutation == "rows_type":
            payload["rows"] = "not-a-list"
        elif mutation == "row_type":
            payload["rows"] = ["not-a-record"]
        elif mutation == "row_bound":
            payload["rows"] = [{"item_code": "100"}, {"item_code": "200"}]
        return payload

    monkeypatch.setattr(
        "global_medicines_atlas.platinum_benefits.benefits_page_payload",
        corrupt_payload,
    )
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.service-items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--limit",
            str(limit),
            "--format",
            "jsonl",
            "--max-rows",
            str(max_rows),
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )

    assert result.exit_code == 2
    assert not result.stdout
    assert json.loads(result.stderr)["error"] == "invalid_request"


def test_cli_benefits_jsonl_offline_miss_has_explicit_unavailable_summary(
    tmp_path, monkeypatch
):
    configuration(tmp_path)
    backend = service()
    monkeypatch.setattr(
        "global_medicines_atlas.platinum_configuration.load_benefits_resolver",
        lambda **_: backend._resolver,
    )
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.service-items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--format",
            "jsonl",
            "--offline",
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )

    assert result.exit_code == 3
    summary = json.loads(result.stdout)
    assert summary["status"] == "unavailable"
    assert summary["source_completeness"] == "not_established"


@pytest.mark.parametrize(
    "value",
    [
        float("inf"),
        float("nan"),
        Decimal("NaN"),
        Decimal("1e39"),
        Decimal("0." + "0" * 38 + "1"),
        2**64,
        "x" * 1025,
    ],
)
def test_scalar_bounds(value):
    with pytest.raises(ValueError, match="bounded finite scalar"):
        BenefitsFilter(column="item_code", operator="=", value=value)


def test_parser_limit_and_boolean_type():
    with pytest.raises(ValueError, match="input bound"):
        parse_benefits_filters(" " * 16385)
    result = parse_benefits_filters(
        '[{"column":"flag","operator":"=","value":true}]'
    )
    assert result[0].value is True


def test_filter_parser_preserves_exact_json_decimal():
    parsed = parse_benefits_filters(
        '[{"column":"benefit","operator":">=","value":10.25}]'
    )
    assert parsed[0].value == Decimal("10.25")
    assert type(parsed[0].value) is Decimal


def test_filter_parser_requires_explicit_canonical_date_value():
    parsed = parse_benefits_filters(
        '[{"column":"start_date","operator":">=","value":'
        '{"type":"date","value":"2025-08-01"}}]'
    )
    assert parsed[0].value == date(2025, 8, 1)
    with pytest.raises(ValueError, match="canonical ISO"):
        parse_benefits_filters(
            '[{"column":"start_date","operator":">=","value":'
            '{"type":"date","value":"01.08.2025"}}]'
        )


def test_api_applies_exact_decimal_filters_to_typed_benefit_column():
    backend = service(payload=decimal_parquet_payload())
    client = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), benefits=backend)
    )
    response = client.get(
        "/api/v1/benefits/au.mbs.service-items",
        params=[
            ("columns", "item_code"),
            ("columns", "benefit"),
            ("filters", '[{"column":"benefit","operator":">=","value":9.99}]'),
        ],
    )
    assert response.status_code == 200
    assert response.json()["rows"] == [
        {"item_code": "200", "benefit": "10.000000000"},
        {"item_code": "300", "benefit": "25.000000000"},
    ]


def test_api_applies_explicit_date_filter_to_typed_date_column():
    backend = service(payload=date_parquet_payload())
    client = TestClient(
        create_app(cast("ReadOnlyQueryService", object()), benefits=backend)
    )
    response = client.get(
        "/api/v1/benefits/au.mbs.service-items",
        params=[
            ("columns", "item_code"),
            ("columns", "start_date"),
            (
                "filters",
                (
                    '[{"column":"start_date","operator":">=","value":'
                    '{"type":"date","value":"2025-08-01"}}]'
                ),
            ),
        ],
    )
    assert response.status_code == 200
    assert response.json()["rows"] == [
        {"item_code": "200", "start_date": "2025-08-01"},
        {"item_code": "300", "start_date": "2025-09-01"},
    ]


@pytest.mark.parametrize("value", [None, -(2**63), 2**63 - 1, 1.25])
def test_scalar_native_types_are_not_coerced(value):
    predicate = BenefitsFilter(column="benefit", operator="=", value=value)
    assert predicate.value == value
    assert type(predicate.value) is type(value)


@pytest.mark.parametrize("filters", [[], ({"column": "benefit"},)])
def test_unchecked_filter_containers_rejected_before_resolution(filters):
    query = BenefitsQuery(columns=("item_code",)).model_copy(
        update={"filters": filters}
    )
    with pytest.raises(ValueError, match="copied filters"):
        service().query("au.mbs.service-items", query)


def test_deeply_nested_filter_input_has_bounded_error():
    with pytest.raises(
        ValueError, match=r"nesting exceeds input bound|validation error"
    ):
        parse_benefits_filters("[" * 2000 + "]" * 2000)


def test_unknown_copied_fields_cannot_be_silently_dropped():
    query = BenefitsQuery(columns=("item_code",))
    with pytest.raises(ValueError, match="unknown copied query"):
        service().query(
            "au.mbs.service-items",
            query.model_copy(update={"ignored": "unsafe"}),
        )
    predicate = BenefitsFilter(column="item_code", operator="=", value="200")
    query = query.model_copy(
        update={
            "filters": (predicate.model_copy(update={"ignored": "unsafe"}),)
        }
    )
    with pytest.raises(ValueError, match="unknown copied filter"):
        service().query("au.mbs.service-items", query)


@pytest.mark.parametrize("missing", ["jsonschema", "unrelated_bug"])
def test_cli_missing_optional_dependency_is_actionable(
    tmp_path, monkeypatch, missing
):
    configuration(tmp_path)
    original = builtins.__import__

    def missing_import(name, *args, **kwargs):
        if name == "platinum_configuration":
            raise ModuleNotFoundError("missing module", name=missing)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_import)
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--offline",
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )
    if missing == "jsonschema":
        assert "global-medicines-atlas[federation]" in result.output
        assert "SERVICE_UNAVAILABLE" in result.output.upper()
    else:
        assert isinstance(result.exception, ModuleNotFoundError)
