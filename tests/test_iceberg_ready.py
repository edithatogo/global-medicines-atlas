"""Iceberg-ready identities without requiring Iceberg in Python 3.14 core."""

from __future__ import annotations

import importlib
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import httpx
import pyarrow.parquet as pq
import pytest
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_landing import (
    bronze_table_spec,
    land_bronze_payload,
)
from global_medicines_atlas.iceberg_ready import (
    IcebergReadyTableSpec,
    SnapshotAcquisitionBinding,
    assert_compatible_evolution,
    evolve_table_spec,
    iceberg_capability_notes,
    iceberg_rest_create_body,
    load_optional_rest_catalog,
    optional_pyiceberg_available,
    register_iceberg_table,
    spec_from_create_body,
    table_identifier_for,
)
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    SourceReceipt,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = b'{"application_number":"012345"}'


def _object_map(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    mapped: dict[str, object] = {}
    for key, item in value.items():
        mapped[str(key)] = item
    return mapped


def _landable_receipt() -> SourceReceipt:
    receipt = source_receipt()
    payload = PayloadEvidence.from_bytes(PAYLOAD)
    return receipt.model_copy(
        update={
            "payload": payload,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=receipt.retrieval.retrieved_at,
                source_id=receipt.source.source_id,
                payload_sha256=payload.sha256,
            ),
        }
    )


def _spec(tmp_path: Path) -> IcebergReadyTableSpec:
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    return bronze_table_spec(receipt, tmp_path / "bronze" / "table.parquet")


def _binding(spec: IcebergReadyTableSpec) -> SnapshotAcquisitionBinding:
    acquisition_id = spec.acquisition_id
    content_id = spec.content_id
    parquet_digest = spec.parquet_digest
    assert acquisition_id is not None
    assert content_id is not None
    assert parquet_digest is not None
    return SnapshotAcquisitionBinding(
        snapshot_id=42,
        acquisition_id=acquisition_id,
        content_id=content_id,
        parquet_digest=parquet_digest,
        iceberg_branch="main",
        iceberg_tag="acquisition-alias",
    )


@pytest.mark.unit
def test_core_dependencies_do_not_require_iceberg_or_marquez() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = project["project"]["dependencies"]
    extras = project["project"].get("optional-dependencies", {})

    assert not any("pyiceberg" in item for item in runtime)
    assert not any("marquez" in item for item in runtime)
    assert "iceberg" in extras
    assert any("pyiceberg" in item for item in extras["iceberg"])
    assert optional_pyiceberg_available() in {True, False}


@pytest.mark.unit
def test_iceberg_ready_module_does_not_import_pyiceberg() -> None:
    source = (ROOT / "src/global_medicines_atlas/iceberg_ready.py").read_text()
    assert "import pyiceberg" not in source
    assert (
        "from pyiceberg"
        not in source.split(
            "def load_optional_rest_catalog",
            maxsplit=1,
        )[0]
    )


@pytest.mark.unit
def test_table_identity_is_stable_and_partitioned(tmp_path: Path) -> None:
    identifier = table_identifier_for(
        jurisdiction="USA",
        source_id="us-drugsfda",
    )
    receipt = source_receipt()
    assert identifier == "bronze.usa_us_drugsfda"
    assert receipt.source.source_id != identifier
    spec = bronze_table_spec(
        receipt.model_copy(
            update={"reuse": acquire_new_decision("medsafe-product-register")}
        ),
        tmp_path / "bronze" / "table.parquet",
    )
    properties = _object_map(iceberg_rest_create_body(spec)["properties"])
    assert properties["gma.acquisition-id"] == spec.acquisition_id
    assert "gma.snapshot-id" not in properties


@pytest.mark.unit
def test_iceberg_rest_catalogue_registration_over_bronze(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    binding = _binding(spec)
    body = iceberg_rest_create_body(spec, binding)
    assert body["name"] == spec.table_name
    assert body["namespace"] == "bronze"
    partition_spec = _object_map(body["partition-spec"])
    assert partition_spec["fields"]
    properties = _object_map(body["properties"])
    assert properties["gma.evidentiary-truth"] == "payload-and-receipt"
    assert properties["gma.row-lineage-authority"] == "atlas-receipt"
    assert properties["gma.acquisition-id"] == spec.acquisition_id
    assert properties["gma.snapshot-id"] == "42"
    assert "native_record" not in properties
    encoded = json.dumps(body)
    assert PAYLOAD.decode() not in encoded
    field_ids = spec.field_ids()
    raw_partitions = partition_spec["fields"]
    assert isinstance(raw_partitions, list)
    partitions: dict[str, int] = {}
    for item in raw_partitions:
        field = _object_map(item)
        name = field["name"]
        source_id = field["source-id"]
        assert isinstance(name, str)
        assert isinstance(source_id, int)
        partitions[name] = source_id
    assert partitions["jurisdiction"] == field_ids["jurisdiction"]
    assert partitions["source_id"] == field_ids["source_id"]
    assert partitions["rights_state"] == field_ids["rights_state"]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "/v1/namespaces/bronze/tables" in str(request.url)
        posted = json.loads(request.content)
        assert posted["properties"]["gma.snapshot-id"] == "42"
        return httpx.Response(
            200,
            json={"metadata-location": "s3://bucket/bronze/metadata"},
        )

    result = register_iceberg_table(
        spec,
        rest_uri="https://iceberg.example.test",
        transport=httpx.MockTransport(handler),
        binding=binding,
    )
    metadata_location = result["metadata-location"]
    assert isinstance(metadata_location, str)
    assert metadata_location.endswith("metadata")


@pytest.mark.unit
def test_create_body_round_trips_without_payload_bytes(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    binding = _binding(spec)
    rebuilt = spec_from_create_body(iceberg_rest_create_body(spec, binding))
    assert rebuilt.identifier == spec.identifier
    assert rebuilt.namespace == spec.namespace
    assert rebuilt.schema_fields == spec.schema_fields
    assert rebuilt.partition_fields == spec.partition_fields
    assert rebuilt.acquisition_id == spec.acquisition_id
    assert rebuilt.content_id == spec.content_id
    assert rebuilt.parquet_digest == spec.parquet_digest
    assert rebuilt.schema_id == spec.schema_id
    assert rebuilt.assigned_last_column_id == spec.assigned_last_column_id


@pytest.mark.unit
def test_schema_evolution_is_append_only(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    evolved = evolve_table_spec(spec, (("analyst_note", "string"),))
    assert_compatible_evolution(spec, evolved)
    assert evolved.schema_id == spec.schema_id + 1
    assert evolved.field_ids()["source_id"] == spec.field_ids()["source_id"]
    dropped = spec.model_copy(update={"schema_fields": spec.schema_fields[:-1]})
    with pytest.raises(ValueError, match="cannot drop"):
        assert_compatible_evolution(spec, dropped)
    retyped = spec.model_copy(
        update={
            "schema_fields": (
                ("source_id", "int"),
                *spec.schema_fields[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="cannot change type"):
        assert_compatible_evolution(spec, retyped)
    with pytest.raises(ValueError, match="cannot reuse field name"):
        evolve_table_spec(spec, (("acquisition_id", "string"),))


@pytest.mark.unit
def test_parquet_remains_valid_without_iceberg(tmp_path: Path) -> None:
    landing = land_bronze_payload(
        PAYLOAD,
        _landable_receipt(),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    table = pq.read_table(landing.parquet_path)
    assert "acquisition_id" in table.column_names
    assert landing.table.identifier.startswith("bronze.")
    assert landing.parquet_path.read_bytes() != PAYLOAD
    notes = iceberg_capability_notes()
    assert "authoritative" in notes["row_lineage"]
    assert "not acquisition identity" in notes["branching"]
    assert "do not replace acquisition_id" in notes["tagging"]
    assert "not bronze truth" in notes["metadata"]


@pytest.mark.unit
def test_register_rejects_non_object_and_optional_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(tmp_path)

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


@pytest.mark.unit
def test_optional_rest_catalog_fails_closed_without_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = importlib.import_module

    def blocked(name: str, package: str | None = None) -> ModuleType:
        if name.startswith("pyiceberg"):
            raise ImportError("iceberg extra absent")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", blocked)
    with pytest.raises(RuntimeError, match="optional extra 'iceberg'"):
        load_optional_rest_catalog("https://iceberg.example.test")


@pytest.mark.unit
def test_create_body_rejects_malformed_documents() -> None:
    with pytest.raises(TypeError, match="schema must be an object"):
        spec_from_create_body({"schema": []})
    with pytest.raises(ValueError, match="partition field"):
        IcebergReadyTableSpec(
            identifier="bronze.example",
            location="file://bronze",
            partition_fields=("missing",),
            schema_fields=(("source_id", "string"),),
        )
