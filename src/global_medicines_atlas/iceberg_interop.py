"""Executable Iceberg REST and v3 interoperability experiments."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field

from .models import FrozenModel

ICEBERG_REST_FIXTURE_IMAGE = (
    "apache/iceberg-rest-fixture@"
    "sha256:db8de90b5b7693d4ac334c336f91d9bbe320d7b19f4f514d26de84cdfbcbfe8d"
)
ICEBERG_RELEASE = "1.11.0"
PYICEBERG_VERSION = "0.11.1"
_BASE_FIELD_COUNT = 5
_FORMAT_VERSION_V3 = 3

V3_CAPABILITY_SYMBOLS: dict[str, frozenset[str]] = {
    "nanosecond_timestamps": frozenset({
        "TimestampNanoType",
        "TimestamptzNanoType",
    }),
    "default_values": frozenset({"NestedFieldDefaults"}),
    "multi_argument_transforms": frozenset({"MultiArgumentTransform"}),
    "row_lineage": frozenset({
        "TableMetadataV3.next_row_id",
        "Snapshot.first_row_id",
    }),
    "deletion_vectors": frozenset({"DataFileContent.DELETION_VECTOR"}),
}


class CapabilityResult(FrozenModel):
    capability: str = Field(min_length=1)
    supported: bool
    required_symbols: tuple[str, ...] = Field(min_length=1)
    missing_symbols: tuple[str, ...] = ()


class IcebergInteropReceipt(FrozenModel):
    schema_id: Literal["global-medicines-atlas.iceberg-interop-receipt"]
    schema_version: Literal[1]
    server_image: Literal[
        "apache/iceberg-rest-fixture@sha256:db8de90b5b7693d4ac334c336f91d9bbe320d7b19f4f514d26de84cdfbcbfe8d"
    ]
    iceberg_release: Literal["1.11.0"]
    pyiceberg_version: Literal["0.11.1"]
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operations: tuple[str, ...] = Field(min_length=1)
    empty_snapshot_observed: bool
    schema_evolution_verified: bool
    partition_evolution_verified: bool
    reconstruction_verified: bool
    v3_table_created: bool
    v3_capabilities: tuple[CapabilityResult, ...]
    core_optional: Literal[True] = True
    production_deployment_claimed: Literal[False] = False
    universal_interoperability_claimed: Literal[False] = False


def assert_disposable_rest_uri(rest_uri: str) -> None:
    """Restrict the executable experiment to a loopback catalogue."""

    parsed = urlsplit(rest_uri)
    has_authority = parsed.username is not None or parsed.password is not None
    has_suffix = bool(parsed.query or parsed.fragment)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or has_authority
        or has_suffix
    ):
        raise ValueError(
            "Iceberg experiment requires an unauthenticated loopback URI"
        )


def assess_v3_capabilities(symbols: set[str]) -> tuple[CapabilityResult, ...]:
    """Assess v3 capabilities without inferring support from format version."""

    results: list[CapabilityResult] = []
    for capability, required in V3_CAPABILITY_SYMBOLS.items():
        missing = tuple(sorted(required - symbols))
        results.append(
            CapabilityResult(
                capability=capability,
                supported=not missing,
                required_symbols=tuple(sorted(required)),
                missing_symbols=missing,
            )
        )
    return tuple(results)


def installed_pyiceberg_v3_symbols() -> set[str]:
    """Return explicit PyIceberg v3 symbols from the optional dependency."""

    types = importlib.import_module("pyiceberg.types")
    metadata = importlib.import_module("pyiceberg.table.metadata")
    snapshots = importlib.import_module("pyiceberg.table.snapshots")
    manifest = importlib.import_module("pyiceberg.manifest")
    transforms = importlib.import_module("pyiceberg.transforms")
    symbols: set[str] = set()
    for name in ("TimestampNanoType", "TimestamptzNanoType"):
        if hasattr(types, name):
            symbols.add(name)
    nested = types.NestedField
    if {"initial_default", "write_default"}.issubset(nested.model_fields):
        symbols.add("NestedFieldDefaults")
    table_v3 = metadata.TableMetadataV3
    if "next_row_id" in table_v3.model_fields:
        symbols.add("TableMetadataV3.next_row_id")
    snapshot = snapshots.Snapshot
    if "first_row_id" in snapshot.model_fields:
        symbols.add("Snapshot.first_row_id")
    contents = manifest.DataFileContent
    if "DELETION_VECTOR" in contents.__members__:
        symbols.add("DataFileContent.DELETION_VECTOR")
    if hasattr(transforms, "MultiArgumentTransform"):
        symbols.add("MultiArgumentTransform")
    return symbols


def run_rest_catalog_interop(  # ruff: ignore[too-many-locals]
    *, rest_uri: str, fixture_path: Path
) -> IcebergInteropReceipt:
    """Exercise a real disposable REST catalogue through PyIceberg."""

    assert_disposable_rest_uri(rest_uri)
    fixture_sha256 = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    pyiceberg_version = importlib.metadata.version("pyiceberg")
    if pyiceberg_version != PYICEBERG_VERSION:
        raise RuntimeError(
            "PyIceberg version does not match the locked experiment"
        )

    catalog_module = importlib.import_module("pyiceberg.catalog")
    schema_module = importlib.import_module("pyiceberg.schema")
    types = importlib.import_module("pyiceberg.types")
    catalog = catalog_module.load_catalog(
        "gma-experiment",
        type="rest",
        uri=rest_uri,
    )
    namespace = ("gma_experiment",)
    identifier = (*namespace, "bronze_records")
    v3_identifier = (*namespace, "bronze_records_v3")
    schema = schema_module.Schema(
        types.NestedField(
            1, "acquisition_id", types.StringType(), required=True
        ),
        types.NestedField(2, "content_id", types.StringType(), required=True),
        types.NestedField(3, "source_id", types.StringType(), required=True),
        types.NestedField(4, "native_id", types.StringType(), required=True),
        types.NestedField(5, "value", types.IntegerType(), required=True),
    )
    operations: list[str] = []
    try:
        catalog.create_namespace(namespace)
        operations.append("create_namespace")
        table = catalog.create_table(
            identifier,
            schema=schema,
            properties={
                "format-version": "2",
                "gma.fixture-sha256": fixture_sha256,
                "gma.acquisition-id": "acq-experiment-001",
            },
        )
        operations.append("create_table")
        empty_snapshot = table.current_snapshot() is None
        with table.update_schema() as update:
            update.add_column("observed_at", types.TimestamptzType())
        operations.append("evolve_schema")
        with table.update_spec() as update:
            update.add_identity("source_id")
        operations.append("evolve_partition_spec")
        loaded = catalog.load_table(identifier)
        schema_evolution = (
            loaded.schema().find_field("observed_at").field_id
            > _BASE_FIELD_COUNT
        )
        partition_evolution = any(
            field.name == "source_id" for field in loaded.spec().fields
        )
        catalog.drop_table(identifier)
        operations.append("drop_table")
        reconstructed = catalog.create_table(
            identifier,
            schema=schema,
            properties={
                "format-version": "2",
                "gma.fixture-sha256": fixture_sha256,
                "gma.acquisition-id": "acq-experiment-001",
                "gma.reconstructed": "true",
            },
        )
        reconstruction_verified = (
            reconstructed.properties.get("gma.fixture-sha256") == fixture_sha256
            and reconstructed.properties.get("gma.reconstructed") == "true"
        )
        operations.append("reconstruct_table")
        v3_table = catalog.create_table(
            v3_identifier,
            schema=schema,
            properties={"format-version": "3"},
        )
        v3_created = v3_table.metadata.format_version == _FORMAT_VERSION_V3
        operations.append("create_v3_table")
    finally:
        for target in (identifier, v3_identifier):
            if catalog.table_exists(target):
                catalog.drop_table(target)
        if catalog.namespace_exists(namespace):
            catalog.drop_namespace(namespace)
    return IcebergInteropReceipt(
        schema_id="global-medicines-atlas.iceberg-interop-receipt",
        schema_version=1,
        server_image=ICEBERG_REST_FIXTURE_IMAGE,
        iceberg_release=ICEBERG_RELEASE,
        pyiceberg_version=pyiceberg_version,
        fixture_sha256=fixture_sha256,
        operations=tuple(operations),
        empty_snapshot_observed=empty_snapshot,
        schema_evolution_verified=schema_evolution,
        partition_evolution_verified=partition_evolution,
        reconstruction_verified=reconstruction_verified,
        v3_table_created=v3_created,
        v3_capabilities=assess_v3_capabilities(
            installed_pyiceberg_v3_symbols()
        ),
    )
