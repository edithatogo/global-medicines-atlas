"""Iceberg-ready identities without requiring Iceberg in Python 3.14 core."""

from __future__ import annotations

import importlib
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import pyarrow.parquet as pq
import pytest
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_landing import (
    bronze_table_spec,
    land_bronze_payload,
)
from global_medicines_atlas.iceberg_ready import (
    IcebergPartitionField,
    IcebergPartitionPolicy,
    IcebergReadyTableSpec,
    SnapshotAcquisitionBinding,
    assert_compatible_evolution,
    evolve_table_spec,
    iceberg_capability_notes,
    iceberg_rest_create_body,
    load_optional_rest_catalog,
    optional_pyiceberg_available,
    plan_iceberg_partitions,
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
LARGE_SCHEMA = (
    ("release_date", "date"),
    ("gma_acquired_at", "timestamptz"),
    ("native_id", "string"),
)


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
    parquet_path = tmp_path / "bronze" / "table.parquet"
    parquet_path.parent.mkdir(parents=True)
    parquet_path.write_bytes(b"parquet-output")
    return bronze_table_spec(receipt, parquet_path)


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
    parquet_path = tmp_path / "bronze" / "table.parquet"
    parquet_path.parent.mkdir(parents=True)
    parquet_path.write_bytes(b"parquet-output")
    spec = bronze_table_spec(
        receipt.model_copy(
            update={"reuse": acquire_new_decision("medsafe-product-register")}
        ),
        parquet_path,
    )
    properties = _object_map(iceberg_rest_create_body(spec)["properties"])
    assert properties["gma.acquisition-id"] == spec.acquisition_id
    assert "gma.snapshot-id" not in properties


@pytest.mark.unit
def test_small_bronze_tables_are_unpartitioned(tmp_path: Path) -> None:
    spec = _spec(tmp_path)

    assert spec.partition_fields == ()
    body = iceberg_rest_create_body(spec)
    partition_spec = _object_map(body["partition-spec"])
    assert partition_spec["fields"] == []


@pytest.mark.unit
def test_large_recurring_sources_use_temporal_and_optional_bucket_transforms(
) -> None:
    policy = IcebergPartitionPolicy(
        recurring=True,
        large_table_min_rows=1_000,
        source_release_field="release_date",
        record_id_field="native_id",
        record_id_buckets=32,
    )

    assert plan_iceberg_partitions(
        LARGE_SCHEMA,
        row_count=999,
        policy=policy,
    ) == ()
    assert plan_iceberg_partitions(
        LARGE_SCHEMA,
        row_count=1_000,
        policy=policy,
    ) == (
        IcebergPartitionField(
            source_field="release_date",
            name="release_date_month",
            transform="month",
        ),
        IcebergPartitionField(
            source_field="native_id",
            name="native_id_bucket_32",
            transform="bucket[32]",
        ),
    )


@pytest.mark.unit
def test_large_recurring_source_falls_back_to_acquisition_month() -> None:
    policy = IcebergPartitionPolicy(
        recurring=True,
        large_table_min_rows=10,
    )

    assert plan_iceberg_partitions(
        LARGE_SCHEMA,
        row_count=10,
        policy=policy,
    ) == (
        IcebergPartitionField(
            source_field="gma_acquired_at",
            name="gma_acquired_at_month",
            transform="month",
        ),
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "field",
    [
        "jurisdiction",
        "source_id",
        "rights_state",
        "admission_state",
        "review_status",
    ],
)
def test_constant_and_mutable_governance_partition_keys_are_rejected(
    field: str,
) -> None:
    with pytest.raises(ValueError, match="physical partition key"):
        IcebergReadyTableSpec(
            identifier="bronze.example",
            location="file://bronze",
            partition_fields=(
                IcebergPartitionField(
                    source_field=field,
                    name=field,
                    transform="identity",
                ),
            ),
            schema_fields=((field, "string"),),
        )


@pytest.mark.unit
def test_partition_transforms_round_trip_through_rest_body() -> None:
    fields = plan_iceberg_partitions(
        LARGE_SCHEMA,
        row_count=10,
        policy=IcebergPartitionPolicy(
            recurring=True,
            large_table_min_rows=10,
            source_release_field="release_date",
            record_id_field="native_id",
            record_id_buckets=16,
        ),
    )
    spec = IcebergReadyTableSpec(
        identifier="bronze.example",
        location="file://bronze",
        partition_fields=fields,
        schema_fields=LARGE_SCHEMA,
    )

    body = iceberg_rest_create_body(spec)
    raw_partition_spec = _object_map(body["partition-spec"])
    raw_fields = raw_partition_spec["fields"]
    assert isinstance(raw_fields, list)
    transforms = [_object_map(item)["transform"] for item in raw_fields]
    assert transforms == ["month", "bucket[16]"]
    assert spec_from_create_body(body).partition_fields == fields


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
    with pytest.raises(ValueError, match="schema_fields must not be empty"):
        IcebergReadyTableSpec(
            identifier="bronze.example",
            location="file://bronze",
            partition_fields=(),
            schema_fields=(),
        )
    with pytest.raises(ValueError, match="last_column_id is below"):
        IcebergReadyTableSpec(
            identifier="bronze.example",
            location="file://bronze",
            partition_fields=(),
            schema_fields=(("source_id", "string"), ("jurisdiction", "string")),
            last_column_id=1,
        )


@pytest.mark.unit
def test_catalogue_properties_cover_optional_identity_branches(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    untagged = SnapshotAcquisitionBinding(
        snapshot_id=7,
        acquisition_id=spec.acquisition_id or ("a" * 64),
        content_id=spec.content_id or ("b" * 64),
        parquet_digest=spec.parquet_digest or ("c" * 64),
        iceberg_branch="main",
    )
    tagged_out = _object_map(
        iceberg_rest_create_body(spec, untagged)["properties"]
    )
    assert "gma.iceberg-tag" not in tagged_out
    assert tagged_out["gma.iceberg-branch"] == "main"

    digest_only = spec.model_copy(update={"acquisition_id": None})
    digest_props = _object_map(
        iceberg_rest_create_body(digest_only)["properties"]
    )
    assert digest_props["gma.content-id"] == spec.content_id
    assert "gma.acquisition-id" not in digest_props

    identity_free = spec.model_copy(
        update={
            "acquisition_id": None,
            "content_id": None,
            "parquet_digest": None,
        }
    )
    free_props = _object_map(
        iceberg_rest_create_body(identity_free)["properties"]
    )
    assert "gma.acquisition-id" not in free_props
    assert "gma.content-id" not in free_props


@pytest.mark.unit
def test_evolution_rejects_evidentiary_drop_and_reused_field_ids(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    dropped_evidentiary = spec.model_copy(
        update={
            "schema_fields": tuple(
                (name, typ)
                for name, typ in spec.schema_fields
                if name != "content_id"
            )
        }
    )
    with pytest.raises(ValueError, match="cannot drop evidentiary field"):
        assert_compatible_evolution(spec, dropped_evidentiary)
    reordered = spec.model_copy(
        update={"schema_fields": tuple(reversed(spec.schema_fields))}
    )
    with pytest.raises(ValueError, match="is immutable"):
        assert_compatible_evolution(spec, reordered)


@pytest.mark.unit
def test_spec_from_create_body_rejects_non_string_members(
    tmp_path: Path,
) -> None:
    body = iceberg_rest_create_body(_spec(tmp_path))
    schema = _object_map(body["schema"])
    with pytest.raises(TypeError, match="fields must be an array"):
        spec_from_create_body({**body, "schema": {**schema, "fields": "nope"}})
    with pytest.raises(TypeError, match="name and type must be strings"):
        spec_from_create_body({
            **body,
            "schema": {**schema, "fields": [{"name": 1, "type": "string"}]},
        })
    properties = _object_map(body["properties"])
    with pytest.raises(TypeError, match="location must be a string"):
        spec_from_create_body({
            **body,
            "properties": {**properties, "location": 1},
        })
    with pytest.raises(TypeError, match="namespace must be a string"):
        spec_from_create_body({**body, "namespace": 1})
    with pytest.raises(TypeError, match="table name must be a string"):
        spec_from_create_body({**body, "name": 1})
    with pytest.raises(TypeError, match="schema ids must be integers"):
        spec_from_create_body({
            **body,
            "schema": {**schema, "last-column-id": "x"},
        })


@pytest.mark.unit
def test_optional_rest_catalog_loads_when_extra_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = ModuleType("pyiceberg.catalog.rest")

    def rest_catalog(name: str, uri: str) -> SimpleNamespace:
        return SimpleNamespace(name=name, uri=uri)

    module.RestCatalog = rest_catalog
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None) -> ModuleType:
        if name == "pyiceberg.catalog.rest":
            return module
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    catalog = load_optional_rest_catalog("https://iceberg.example.test")
    assert isinstance(catalog, SimpleNamespace)
    assert catalog.name == "gma-bronze"
    assert catalog.uri == "https://iceberg.example.test"
