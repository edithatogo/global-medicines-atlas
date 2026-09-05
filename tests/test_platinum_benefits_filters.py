"""Scalar benefit filters agree across service, HTTP and CLI contracts."""

import builtins
import json
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_platinum_benefits_api import service
from test_platinum_configuration import configuration
from typer.testing import CliRunner

from global_medicines_atlas.api import create_app
from global_medicines_atlas.cli import app
from global_medicines_atlas.platinum_benefits import (
    BenefitsFilter,
    BenefitsQuery,
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


@pytest.mark.parametrize(
    "value", [float("inf"), float("nan"), 2**64, "x" * 1025]
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
