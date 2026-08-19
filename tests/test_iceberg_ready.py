"""Iceberg-ready identities without requiring Iceberg in Python 3.14 core."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_landing import bronze_table_spec
from global_medicines_atlas.iceberg_ready import (
    iceberg_rest_create_body,
    optional_pyiceberg_available,
    register_iceberg_table,
    table_identifier_for,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_core_dependencies_do_not_require_iceberg_or_marquez() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = project["project"]["dependencies"]
    extras = project["project"].get("optional-dependencies", {})

    assert not any("pyiceberg" in item for item in runtime)
    assert not any("marquez" in item for item in runtime)
    assert "iceberg" not in extras
    assert optional_pyiceberg_available() in {True, False}


@pytest.mark.unit
def test_table_identity_is_stable_and_partitioned() -> None:
    identifier = table_identifier_for(
        jurisdiction="USA",
        source_id="us-drugsfda",
    )
    receipt = source_receipt()
    assert identifier == "bronze.usa_us_drugsfda"
    assert receipt.source.source_id != identifier


@pytest.mark.unit
def test_iceberg_rest_catalogue_registration_over_bronze(
    tmp_path: Path,
) -> None:
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    parquet_path = tmp_path / "bronze" / "parquet" / "x.parquet"
    spec = bronze_table_spec(receipt, parquet_path)
    body = iceberg_rest_create_body(spec)
    assert body["name"] == spec.table_name
    assert body["partition-spec"]["fields"]
    assert body["properties"]["gma.evidentiary-truth"] == (
        "payload-and-receipt"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "/v1/namespaces/bronze/tables" in str(request.url)
        return httpx.Response(
            200,
            json={"metadata-location": "s3://bucket/bronze/metadata"},
        )

    result = register_iceberg_table(
        spec,
        rest_uri="https://iceberg.example.test",
        transport=httpx.MockTransport(handler),
    )
    assert result["metadata-location"].endswith("metadata")


@pytest.mark.unit
def test_register_rejects_non_object_and_optional_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    spec = bronze_table_spec(receipt, tmp_path / "table.parquet")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not-an-object"])

    with pytest.raises(TypeError, match="non-object"):
        register_iceberg_table(
            spec,
            rest_uri="https://iceberg.example.test",
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setitem(sys.modules, "pyiceberg", ModuleType("pyiceberg"))
    assert optional_pyiceberg_available() is True
