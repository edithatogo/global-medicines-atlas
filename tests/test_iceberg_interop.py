"""Iceberg REST and v3 capability experiment tests."""

from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from global_medicines_atlas import iceberg_interop
from global_medicines_atlas.iceberg_interop import (
    ICEBERG_REST_FIXTURE_IMAGE,
    V3_CAPABILITY_SYMBOLS,
    assert_disposable_rest_uri,
    assess_v3_capabilities,
    installed_pyiceberg_v3_symbols,
    run_rest_catalog_interop,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_rest_fixture_image_is_digest_pinned() -> None:
    assert ICEBERG_REST_FIXTURE_IMAGE.startswith(
        "apache/iceberg-rest-fixture@sha256:"
    )
    assert len(ICEBERG_REST_FIXTURE_IMAGE.rsplit(":", maxsplit=1)[-1]) == 64


@pytest.mark.unit
@pytest.mark.parametrize(
    "uri",
    [
        "https://127.0.0.1:8181",
        "http://catalog.example:8181",
        "http://user:secret@127.0.0.1:8181",
        "http://127.0.0.1:8181?token=secret",
        "http://127.0.0.1:8181/#fragment",
    ],
)
def test_rest_experiment_rejects_non_disposable_or_secret_bearing_uri(
    uri: str,
) -> None:
    with pytest.raises(ValueError, match="loopback"):
        assert_disposable_rest_uri(uri)


@pytest.mark.unit
def test_rest_experiment_accepts_loopback_http() -> None:
    assert_disposable_rest_uri("http://127.0.0.1:8181")
    assert_disposable_rest_uri("http://localhost:8181")


@pytest.mark.unit
def test_v3_capability_assessment_is_explicit_and_does_not_infer() -> None:
    symbols = {
        symbol
        for capability in ("nanosecond_timestamps", "row_lineage")
        for symbol in V3_CAPABILITY_SYMBOLS[capability]
    }

    results = assess_v3_capabilities(symbols)
    by_name = {result.capability: result for result in results}

    assert by_name["nanosecond_timestamps"].supported is True
    assert by_name["row_lineage"].supported is True
    assert by_name["deletion_vectors"].supported is False
    assert by_name["deletion_vectors"].missing_symbols == (
        "DataFileContent.DELETION_VECTOR",
    )
    assert set(by_name) == set(V3_CAPABILITY_SYMBOLS)


@pytest.mark.unit
def test_pyiceberg_remains_an_optional_extra() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert not any(
        "pyiceberg" in dependency
        for dependency in project["project"]["dependencies"]
    )
    assert project["project"]["optional-dependencies"]["iceberg"] == [
        "pyiceberg>=0.10"
    ]


class _Update:
    def __init__(self, table: _Table, kind: str) -> None:
        self.table = table
        self.kind = kind

    def __enter__(self) -> _Update:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def add_column(self, name: str, _type: object) -> None:
        self.table.fields[name] = 6

    def add_identity(self, name: str) -> None:
        self.table.partitions.add(name)


class _Table:
    def __init__(self, properties: dict[str, str]) -> None:
        self.properties = properties
        self.fields = {"observed_at": 6}
        self.partitions = {"source_id"}
        self.metadata = SimpleNamespace(
            format_version=int(properties.get("format-version", "2"))
        )

    def current_snapshot(self) -> None:
        return None

    def update_schema(self) -> _Update:
        return _Update(self, "schema")

    def update_spec(self) -> _Update:
        return _Update(self, "partition")

    def schema(self) -> Any:
        return _SchemaView(self.fields)

    def spec(self) -> Any:
        return SimpleNamespace(
            fields=[SimpleNamespace(name=name) for name in self.partitions]
        )


class _Catalog:
    def __init__(self) -> None:
        self.tables: dict[tuple[str, ...], _Table] = {}
        self.namespace = False

    def create_namespace(self, _namespace: tuple[str, ...]) -> None:
        self.namespace = True

    def create_table(
        self,
        identifier: tuple[str, ...],
        *,
        schema: object,
        properties: dict[str, str],
    ) -> _Table:
        del schema
        table = _Table(properties)
        self.tables[identifier] = table
        return table

    def load_table(self, identifier: tuple[str, ...]) -> _Table:
        return self.tables[identifier]

    def table_exists(self, identifier: tuple[str, ...]) -> bool:
        return identifier in self.tables

    def drop_table(self, identifier: tuple[str, ...]) -> None:
        del self.tables[identifier]

    def namespace_exists(self, _namespace: tuple[str, ...]) -> bool:
        return self.namespace

    def drop_namespace(self, _namespace: tuple[str, ...]) -> None:
        self.namespace = False


def _new_object(*_args: object, **_kwargs: object) -> object:
    return object()


def _empty_symbols() -> set[str]:
    return set()


class _SchemaView:
    def __init__(self, fields: dict[str, int]) -> None:
        self.fields = fields

    def find_field(self, name: str) -> Any:
        return SimpleNamespace(field_id=self.fields[name])


def _locked_version(_name: str) -> str:
    return "0.11.1"


def _unlocked_version(_name: str) -> str:
    return "9.9.9"


@pytest.mark.unit
def test_rest_catalog_lifecycle_receipt_uses_actual_fixture_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = tmp_path / "records.json"
    fixture.write_bytes(b'{"governed":true}\n')
    catalog = _Catalog()
    types = SimpleNamespace(
        NestedField=_new_object,
        StringType=_new_object,
        IntegerType=_new_object,
        TimestamptzType=_new_object,
    )

    def load_catalog(*_args: object, **_kwargs: object) -> _Catalog:
        return catalog

    modules: dict[str, object] = {
        "pyiceberg.catalog": SimpleNamespace(load_catalog=load_catalog),
        "pyiceberg.schema": SimpleNamespace(Schema=_new_object),
        "pyiceberg.types": types,
    }

    def import_module(name: str) -> object:
        return modules[name]

    monkeypatch.setattr(
        iceberg_interop.importlib.metadata, "version", _locked_version
    )
    monkeypatch.setattr(
        iceberg_interop.importlib, "import_module", import_module
    )
    monkeypatch.setattr(
        iceberg_interop, "installed_pyiceberg_v3_symbols", _empty_symbols
    )

    receipt = run_rest_catalog_interop(
        rest_uri="http://127.0.0.1:8181", fixture_path=fixture
    )

    assert receipt.fixture_sha256 == (
        "cb57b6094317ae36e720db24dfab55d34598a70bda7decf0bb2cc64dd071f28d"
    )
    assert receipt.operations == (
        "create_namespace",
        "create_table",
        "evolve_schema",
        "evolve_partition_spec",
        "drop_table",
        "reconstruct_table",
        "create_v3_table",
    )
    assert receipt.empty_snapshot_observed is True
    assert receipt.schema_evolution_verified is True
    assert receipt.partition_evolution_verified is True
    assert receipt.reconstruction_verified is True
    assert receipt.v3_table_created is True
    assert catalog.tables == {}
    assert catalog.namespace is False


@pytest.mark.unit
def test_installed_pyiceberg_v3_symbols_are_observed_not_inferred() -> None:
    symbols = installed_pyiceberg_v3_symbols()

    assert {
        "TimestampNanoType",
        "TimestamptzNanoType",
        "NestedFieldDefaults",
        "TableMetadataV3.next_row_id",
        "Snapshot.first_row_id",
    }.issubset(symbols)


@pytest.mark.unit
def test_rest_catalog_rejects_unlocked_pyiceberg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = tmp_path / "records.json"
    fixture.write_bytes(b"[]")
    monkeypatch.setattr(
        iceberg_interop.importlib.metadata, "version", _unlocked_version
    )

    with pytest.raises(RuntimeError, match="locked experiment"):
        run_rest_catalog_interop(
            rest_uri="http://localhost:8181", fixture_path=fixture
        )
