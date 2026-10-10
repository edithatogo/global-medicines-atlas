"""Iceberg REST and v3 capability experiment tests."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed interpreter and code
import sys
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


def _fixture_payload() -> bytes:
    return json.dumps(
        _fixture_records(),
        separators=(",", ":"),
    ).encode("utf-8")


def _fixture_records() -> list[dict[str, object]]:
    return [
        {
            "acquisition_id": "acq-1",
            "content_id": "sha256:" + "a" * 64,
            "native_id": "A-001",
            "source_id": "source-1",
            "source_release_date": "2026-08-20",
            "value": 1,
        },
        {
            "acquisition_id": "acq-1",
            "content_id": "sha256:" + "b" * 64,
            "native_id": "A-002",
            "source_id": "source-1",
            "source_release_date": "2026-08-21",
            "value": 2,
        },
    ]


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


@pytest.mark.unit
def test_core_module_import_does_not_load_optional_pyiceberg() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import global_medicines_atlas.iceberg_interop; "
                "assert 'pyiceberg' not in sys.modules"
            ),
        ],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


@pytest.mark.edge
@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b'[{"native_id":"A","native_id":"B"}]', "duplicate contract JSON key"),
        (b"[]", "non-empty row array"),
        (b"[{}]", "row fields do not match schema"),
    ],
)
def test_iceberg_fixture_ingest_rejects_ambiguous_or_incomplete_json(
    payload: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        iceberg_interop.load_fixture_records(payload)


@pytest.mark.edge
def test_iceberg_fixture_ingest_rejects_mixed_acquisition_identity() -> None:
    records = _fixture_records()
    records[1]["acquisition_id"] = "acq-2"
    payload = json.dumps(records).encode("utf-8")

    with pytest.raises(ValueError, match="one acquisition per table"):
        iceberg_interop.load_fixture_records(payload)


class _Update:
    def __init__(self, table: _Table, kind: str) -> None:
        self.table = table
        self.kind = kind

    def __enter__(self) -> _Update:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def add_column(self, name: str, _type: object) -> None:
        self.table.fields[name] = 7

    def add_identity(self, name: str) -> None:
        self.table.partitions.add(name)


class _Table:
    def __init__(self, properties: dict[str, str]) -> None:
        self.properties = properties
        self.fields = {"observed_at": 7}
        self.partitions = {"source_id"}
        self.records: list[dict[str, object]] = []
        self.metadata = SimpleNamespace(
            format_version=int(properties.get("format-version", "2"))
        )

    def current_snapshot(self) -> object | None:
        return object() if self.records else None

    def append(self, arrow_table: _ArrowTable) -> None:
        self.records.extend(arrow_table.to_pylist())

    def scan(self) -> _Scan:
        return _Scan(self.records)

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


class _ArrowTable:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = copy.deepcopy(rows)

    @classmethod
    def from_pylist(cls, rows: list[dict[str, object]]) -> _ArrowTable:
        return cls(rows)

    def to_pylist(self) -> list[dict[str, object]]:
        return copy.deepcopy(self.rows)


class _Scan:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def to_arrow(self) -> _ArrowTable:
        return _ArrowTable(self.rows)


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


def _install_rest_stubs(
    monkeypatch: pytest.MonkeyPatch, catalog: _Catalog
) -> None:
    types = SimpleNamespace(
        NestedField=_new_object,
        StringType=_new_object,
        IntegerType=_new_object,
        TimestamptzType=_new_object,
        DateType=_new_object,
    )

    def load_catalog(*_args: object, **_kwargs: object) -> _Catalog:
        return catalog

    modules: dict[str, object] = {
        "pyiceberg.catalog": SimpleNamespace(load_catalog=load_catalog),
        "pyiceberg.schema": SimpleNamespace(Schema=_new_object),
        "pyiceberg.types": types,
        "pyarrow": SimpleNamespace(Table=_ArrowTable),
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


@pytest.mark.unit
def test_rest_catalog_lifecycle_receipt_uses_actual_fixture_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = tmp_path / "records.json"
    fixture_bytes = _fixture_payload()
    fixture.write_bytes(fixture_bytes)
    catalog = _Catalog()
    _install_rest_stubs(monkeypatch, catalog)

    receipt = run_rest_catalog_interop(
        rest_uri="http://127.0.0.1:8181", fixture_path=fixture
    )

    assert receipt.fixture_sha256 == hashlib.sha256(fixture_bytes).hexdigest()
    assert receipt.schema_version == 2
    assert receipt.fixture_acquisition_id == "acq-1"
    assert receipt.fixture_record_count == 2
    assert receipt.operations == (
        "create_namespace",
        "create_table",
        "evolve_schema",
        "evolve_partition_spec",
        "append_fixture_records",
        "verify_data_roundtrip",
        "drop_table",
        "reconstruct_table",
        "create_v3_table",
    )
    assert receipt.empty_snapshot_observed is True
    assert receipt.populated_snapshot_observed is True
    assert receipt.data_roundtrip_verified is True
    assert receipt.schema_evolution_verified is True
    assert receipt.partition_evolution_verified is True
    assert receipt.reconstruction_verified is True
    assert receipt.v3_table_created is True
    assert catalog.tables == {}
    assert catalog.namespace is False


@pytest.mark.edge
def test_rest_catalog_fails_closed_when_roundtrip_data_differs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = tmp_path / "records.json"
    fixture.write_bytes(_fixture_payload())
    catalog = _Catalog()
    _install_rest_stubs(monkeypatch, catalog)
    original_append = _Table.append

    def corrupt_append(table: _Table, arrow_table: _ArrowTable) -> None:
        original_append(table, arrow_table)
        table.records[0]["value"] = -1

    monkeypatch.setattr(_Table, "append", corrupt_append)

    with pytest.raises(RuntimeError, match="fixture data round-trip"):
        run_rest_catalog_interop(
            rest_uri="http://127.0.0.1:8181", fixture_path=fixture
        )
    assert catalog.tables == {}
    assert catalog.namespace is False


@pytest.mark.unit
def test_installed_pyiceberg_v3_symbols_are_observed_not_inferred() -> None:
    pytest.importorskip("pyiceberg")
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
    fixture.write_bytes(_fixture_payload())
    monkeypatch.setattr(
        iceberg_interop.importlib.metadata, "version", _unlocked_version
    )

    with pytest.raises(RuntimeError, match="locked experiment"):
        run_rest_catalog_interop(
            rest_uri="http://localhost:8181", fixture_path=fixture
        )
